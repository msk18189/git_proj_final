from typing import List, Dict, Any, Optional
from datetime import datetime, timezone,timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import PullRequest, Repository, Contributor, MLPrediction, TotalAnalysis
from github.client import GitHubClient
import numpy as np

def parse_github_repo_url(repo_url: str) -> tuple[str, str]:
    """Parse owner/repo from various GitHub URL formats."""
    url = repo_url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    if "github.com" in url:
        path = url.split("github.com/", 1)[-1]
    else:
        path = url
        
    # Strict validation: exactly two parts (owner/repo). Rejects /issues, /pulls, etc.
    parts = [p for p in path.split("/") if p]
    if len(parts) != 2:
        raise ValueError(
            "Invalid GitHub URL. Use https://github.com/owner/repo or owner/repo"
        )
    return parts[0], parts[1]


def normalize_github_url(owner: str, repo_name: str) -> str:
    """Return a canonical GitHub repository URL for the repo."""
    return f"https://github.com/{owner}/{repo_name}"


class DataProcessor:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ml_models = None  # Lazy load ML models
    
    def _get_ml_models(self):
        """Lazy load ML models to avoid import errors"""
        if self.ml_models is None:
            try:
                from ml.models import MLModels
                self.ml_models = MLModels()
                print("[ML] ML models loaded successfully")
            except Exception as e:
                print(f"[ML WARNING] Could not load ML models: {str(e)}")
                self.ml_models = False  # Mark as failed
        return self.ml_models if self.ml_models else None
    
    async def process_repository(self, repo_url: str, github_token: Optional[str] = None) -> Dict[str, Any]:
        """Process GitHub repository and extract PR data.

        github_token: optional PAT from the user (for private repos or higher limits).
        Uses anonymous access when omitted (public repos only).
        """
        try:
            # Parse URL
            owner, repo_name = parse_github_repo_url(repo_url)
            print(f"Starting repository ingestion: {owner}/{repo_name}")
            
            # Check if repo exists in DB
            canonical_url = normalize_github_url(owner, repo_name)
            repo = (await self.db.execute(select(Repository).filter(Repository.owner == owner, Repository.name == repo_name))).scalar_one_or_none()
            
            if not repo:
                full_name = f"{owner}/{repo_name}"
                repo = Repository(
                    owner=owner,
                    name=repo_name,
                    full_name=full_name,
                    url=canonical_url,
                    source_url=repo_url,
                    stars=0,
                    last_synced=datetime.utcnow(),
                    sync_status="SYNCING",
                    sync_progress="Initializing sync...",
                )
                self.db.add(repo)
                await self.db.commit()
                print(f"Created new repository record: {repo.id}")
            else:
                repo.full_name = repo.full_name or f"{owner}/{repo_name}"
                repo.url = canonical_url
                repo.source_url = repo_url
                repo.sync_status = "SYNCING"
                repo.sync_progress = "Initializing sync..."
                await self.db.commit()
                print(f"Using existing repository record: {repo.id}")
                
            # Initialize GitHub client
            client = GitHubClient(token=github_token.strip() if github_token else None)
            
            # Pagination loop
            cursor = None
            has_next = True
            total_fetched = 0
            new_prs_stored = 0
            updated_prs_stored = 0
            
            last_successful_sync = repo.last_successful_sync
            if last_successful_sync:
                # Ensure UTC timezone info
                if last_successful_sync.tzinfo is None:
                    last_successful_sync = last_successful_sync.replace(tzinfo=timezone.utc)
                print(f"Incremental sync active. Last successful sync: {last_successful_sync}")
                
            stop_incremental = False
            
            # We fetch pages in a loop
            while has_next and not stop_incremental:
                repo.sync_progress = f"Fetching PRs (Fetched {total_fetched} so far)..."
                await self.db.commit()
                
                print(f"Fetching page with cursor: {cursor}")
                import asyncio
                raw_prs, page_info, rate_limit = await asyncio.to_thread(client.fetch_pull_requests, 
                    owner, repo_name, first=100, cursor=cursor
                )
                
                # Update rate limits on repo
                if rate_limit:
                    repo.rate_limit_remaining = rate_limit.get("remaining")
                    repo.rate_limit_limit = rate_limit.get("limit")
                    reset_at_str = rate_limit.get("resetAt")
                    if reset_at_str:
                        repo.rate_limit_reset = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
                
                if not raw_prs:
                    print("No PRs returned in page.")
                    break
                    
                total_fetched += len(raw_prs)
                print(f"Fetched {len(raw_prs)} PRs. Total fetched in this run: {total_fetched}")
                
                # Process PRs in the current page
                for raw_pr in raw_prs:
                    parsed_pr = client.parse_pr_data(raw_pr)
                    
                    # Incremental sync check
                    pr_updated_at = parsed_pr.get("updated_at")
                    if pr_updated_at and pr_updated_at.tzinfo is None:
                        pr_updated_at = pr_updated_at.replace(tzinfo=timezone.utc)
                        
                    # Check if PR exists
                    existing_pr = (await self.db.execute(select(PullRequest).filter(PullRequest.repo_id == repo.id, PullRequest.pr_number == parsed_pr["number"]))).scalar_one_or_none()
                    
                    # Stop condition:
                    # If we are doing incremental sync, and the current PR has an updated_at
                    # older than last_successful_sync - 1 day, AND we already have it in the DB,
                    # we can stop pagination!
                    if last_successful_sync and pr_updated_at:
                        if pr_updated_at < (last_successful_sync - timedelta(days=1)) and existing_pr:
                            print(f"Incremental sync threshold reached at PR #{parsed_pr['number']} (updated at {pr_updated_at}). Stopping sync loop.")
                            stop_incremental = True
                            break
                            
                    if existing_pr:
                        # Update existing PR
                        existing_pr.repo_owner = owner
                        existing_pr.repo_name = repo_name
                        existing_pr.title = parsed_pr["title"][:200]
                        existing_pr.state = parsed_pr["state"]
                        existing_pr.merged_at = parsed_pr["merged_at"]
                        existing_pr.closed_at = parsed_pr["closed_at"]
                        existing_pr.commit_count = parsed_pr["commit_count"]
                        existing_pr.files_changed = parsed_pr["files_changed"]
                        existing_pr.lines_added = parsed_pr["lines_added"]
                        existing_pr.lines_deleted = parsed_pr["lines_deleted"]
                        existing_pr.review_count = parsed_pr["review_count"]
                        existing_pr.comment_count = parsed_pr["comment_count"]
                        existing_pr.cycle_time_days = parsed_pr["cycle_time_days"]
                        existing_pr.wait_for_review_hours = parsed_pr["wait_for_review_hours"]
                        existing_pr.review_duration_hours = parsed_pr["review_duration_hours"]
                        existing_pr.updated_at = parsed_pr["updated_at"]
                        updated_prs_stored += 1
                    else:
                        # Create new PR
                        pr = PullRequest(
                            repo_id=repo.id,
                            repo_owner=owner,
                            repo_name=repo_name,
                            pr_number=parsed_pr["number"],
                            title=parsed_pr["title"][:200],
                            state=parsed_pr["state"],
                            created_at=parsed_pr["created_at"],
                            merged_at=parsed_pr["merged_at"],
                            closed_at=parsed_pr["closed_at"],
                            commit_count=parsed_pr["commit_count"],
                            files_changed=parsed_pr["files_changed"],
                            lines_added=parsed_pr["lines_added"],
                            lines_deleted=parsed_pr["lines_deleted"],
                            review_count=parsed_pr["review_count"],
                            comment_count=parsed_pr["comment_count"],
                            author=parsed_pr["author"][:100],
                            cycle_time_days=parsed_pr["cycle_time_days"],
                            wait_for_review_hours=parsed_pr["wait_for_review_hours"],
                            review_duration_hours=parsed_pr["review_duration_hours"],
                            updated_at=parsed_pr["updated_at"],
                        )
                        self.db.add(pr)
                        await self.db.flush()  # get the PR id
                        existing_pr = pr
                        new_prs_stored += 1
                        
                    # Generate predictions
                    await self._generate_predictions_safe(existing_pr, parsed_pr)
                    
                # Commit page database transactions to save progress
                await self.db.commit()
                
                # Setup for next page
                has_next = page_info.get("hasNextPage", False)
                cursor = page_info.get("endCursor")
                
            # Once all PRs are processed/fetched:
            repo.sync_status = "COMPLETED"
            repo.sync_progress = f"Successfully synced {total_fetched} PRs. (New: {new_prs_stored}, Updated: {updated_prs_stored})"
            repo.last_synced_at = datetime.utcnow()
            repo.last_successful_sync = datetime.utcnow()
            repo.total_prs = (await self.db.execute(select(PullRequest).filter(PullRequest.repo_id == repo.id))).scalar()
            repo.error_message = None
            await self.db.commit()
            
            # Update contributor statistics and total analysis
            print("Updating contributor stats and overall analysis metrics...")
            repo.sync_progress = "Updating statistics & analysis..."
            await self.db.commit()
            
            await self._update_contributor_stats(repo.id, repo)
            await self._update_total_analysis(repo)
            
            repo.sync_progress = f"Sync completed. Total PRs: {repo.total_prs}."
            await self.db.commit()
            
            print(f"Sync successfully completed for {owner}/{repo_name}")
            return {
                "owner": owner,
                "repo": repo_name,
                "prs_processed": new_prs_stored + updated_prs_stored,
                "repo_id": repo.id,
                "total_prs": repo.total_prs
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error processing repository: {error_msg}")
            await self.db.rollback()
            
            # Update repository record to mark as failed
            try:
                owner, repo_name = parse_github_repo_url(repo_url)
                repo = (await self.db.execute(select(Repository).filter(Repository.owner == owner, Repository.name == repo_name))).scalar_one_or_none()
                if repo:
                    repo.sync_status = "FAILED"
                    repo.error_message = error_msg
                    await self.db.commit()
            except Exception as inner:
                print(f"Failed to update repository error state: {inner}")
                
            raise
    
    async def _update_total_analysis(self, repo: Repository):
        """Store or update aggregated analysis metrics for the repository."""
        prs_result = await self.db.execute(select(PullRequest).filter(PullRequest.repo_id == repo.id))
        prs = prs_result.scalars().all()
        total_prs = len(prs)
        open_prs = sum(1 for pr in prs if pr.state == "OPEN")
        merged_prs = sum(1 for pr in prs if pr.state == "MERGED")
        closed_prs = sum(1 for pr in prs if pr.state in ("MERGED", "CLOSED"))

        cycle_times = [pr.cycle_time_days for pr in prs if pr.cycle_time_days is not None]
        avg_cycle_time = round(sum(cycle_times) / len(cycle_times), 2) if cycle_times else None

        review_durations = [pr.review_duration_hours for pr in prs if pr.review_duration_hours is not None]
        avg_review_duration = (
            round(sum(review_durations) / len(review_durations) / 24, 2)
            if review_durations
            else None
        )

        wait_hours = [pr.wait_for_review_hours for pr in prs if pr.wait_for_review_hours is not None]
        avg_wait_for_review = (
            round(sum(wait_hours) / len(wait_hours) / 24, 2)
            if wait_hours
            else None
        )

        merge_rate = round((merged_prs / closed_prs * 100) if closed_prs else 0, 2)

        now = datetime.now(timezone.utc)
        stale_pr_count = 0
        for pr in prs:
            if pr.state == "OPEN" and pr.created_at:
                created = pr.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                stale_pr_count += 1 if (now - created).days > 30 else 0

        analysis = (await self.db.execute(select(TotalAnalysis).filter(TotalAnalysis.repo_id == repo.id))).scalar_one_or_none()

        if analysis:
            analysis.repo_owner = repo.owner
            analysis.repo_name = repo.name
            analysis.total_prs = total_prs
            analysis.open_prs = open_prs
            analysis.merged_prs = merged_prs
            analysis.closed_prs = closed_prs
            analysis.avg_cycle_time = avg_cycle_time
            analysis.merge_rate = merge_rate
            analysis.avg_review_duration = avg_review_duration
            analysis.avg_wait_for_review = avg_wait_for_review
            analysis.stale_pr_count = stale_pr_count
        else:
            analysis = TotalAnalysis(
                repo_id=repo.id,
                repo_owner=repo.owner,
                repo_name=repo.name,
                total_prs=total_prs,
                open_prs=open_prs,
                merged_prs=merged_prs,
                closed_prs=closed_prs,
                avg_cycle_time=avg_cycle_time,
                merge_rate=merge_rate,
                avg_review_duration=avg_review_duration,
                avg_wait_for_review=avg_wait_for_review,
                stale_pr_count=stale_pr_count,
            )
            self.db.add(analysis)

    def _compute_pr_ml_features(self, pr: PullRequest) -> Dict[str, list[float]]:
        """Create ML feature vectors from a stored PullRequest record."""
        age_days = 0.0
        if pr.created_at:
            created = pr.created_at
            if created.tzinfo is None:
                from datetime import timezone
                created = created.replace(tzinfo=timezone.utc)
            age_days = float((datetime.now(timezone.utc) - created).days)

        return {
            "delay_features": [
                float(pr.files_changed or 0),
                float(pr.commit_count or 0),
                float(pr.review_count or 0),
                float(pr.lines_added or 0),
                float(pr.lines_deleted or 0),
                float(pr.review_count or 0),
            ],
            "bottleneck_features": [
                float(pr.wait_for_review_hours or 0),
                float(pr.review_duration_hours or 0),
                float(pr.comment_count or 0),
                float(pr.commit_count or 0),
                float(age_days),
            ],
            "risk_features": [
                float(pr.comment_count or 0),
                float(pr.review_count or 0),
                float(pr.files_changed or 0),
                float((pr.lines_added or 0) + (pr.lines_deleted or 0)),
                0.5,
            ],
            "review_wait_features": [
                float(pr.review_count or 0),
                1.0,
                float(pr.files_changed or 0),
                0.0,
                1.0,
            ],
        }

    async def _score_pr_with_ml(self, pr: PullRequest):
        """Create or refresh ML predictions for a stored PR."""
        ml_models = self._get_ml_models()
        if not ml_models:
            print(f"[ML SKIP] No ML models available for PR {pr.pr_number}")
            return None

        features = self._compute_pr_ml_features(pr)
        try:
            predicted_delay = float(ml_models.predict_delay(features["delay_features"]))
            bottleneck_prob = float(ml_models.predict_bottleneck(features["bottleneck_features"]))
            risk_score = float(ml_models.predict_risk(features["risk_features"]))
            predicted_review_wait = float(
                ml_models.predict_review_wait(features["review_wait_features"])
            )
        except Exception as exc:
            print(f"[ML ERROR] Prediction failed for PR {pr.pr_number}: {exc}")
            return None

        # Do not fall back to heuristic scores here. Use only ML model outputs.
        # If the ML models are unavailable or prediction fails, no prediction is stored.

        from sqlalchemy import delete
        await self.db.execute(delete(MLPrediction).where(MLPrediction.pr_id == pr.id))
        prediction = MLPrediction(
            pr_id=pr.id,
            repo_owner=pr.repo_owner,
            repo_name=pr.repo_name,
            predicted_delay_days=predicted_delay,
            bottleneck_probability=bottleneck_prob,
            risk_score=risk_score,
            predicted_review_wait=predicted_review_wait,
        )
        self.db.add(prediction)
        print(f"[ML] Refreshed predictions for PR {pr.pr_number}")
        return prediction

    async def refresh_ml_predictions(self, repo_id: int = None, only_open_prs: bool = True) -> int:
        """Refresh stored ML predictions for existing PRs in the database."""
        query = select(PullRequest)
        if repo_id is not None:
            query = query.filter(PullRequest.repo_id == repo_id)
        if only_open_prs:
            query = query.filter(PullRequest.state == "OPEN")
        prs = (await self.db.execute(query)).scalars().all()

        if not prs:
            print("[ML] No PRs found for prediction refresh.")
            return 0

        refreshed = 0
        for pr in prs:
            try:
                if await self._score_pr_with_ml(pr) is not None:
                    refreshed += 1
            except Exception as exc:
                print(f"[ML WARNING] Could not refresh PR {pr.pr_number}: {exc}")
                continue

        await self.db.commit()
        print(f"[ML] Refreshed predictions for {refreshed} PR(s)")
        return refreshed

    async def _generate_predictions_safe(self, pr: PullRequest, parsed_pr: Dict):
        """Generate ML predictions safely - won't crash if ML fails.

        Feature engineering reads from both parsed_pr (fresh API values) and
        the pr ORM object (already committed values), preferring parsed_pr.
        Timezone-aware age computation is always applied regardless of PR state.
        """
        try:
            ml_models = self._get_ml_models()
            if not ml_models:
                print(f"Skipping ML predictions for PR {pr.pr_number}")
                return

            # Prepare features with validation
            try:
                # ── Age computation (timezone-safe) ──────────────────────────
                from datetime import timezone as _tz
                now = datetime.now(_tz.utc)
                pr_created = pr.created_at
                if pr_created is not None:
                    if pr_created.tzinfo is None:
                        pr_created = pr_created.replace(tzinfo=_tz.utc)
                    age_days = float(max(0, (now - pr_created).days))
                else:
                    age_days = 0.0

                # ── Pull feature values: prefer parsed_pr, fallback to pr ORM ─
                files_changed     = float(parsed_pr.get("files_changed")    or pr.files_changed    or 0)
                commit_count      = float(parsed_pr.get("commit_count")     or pr.commit_count     or 0)
                review_count      = float(parsed_pr.get("review_count")     or pr.review_count     or 0)
                lines_added       = float(parsed_pr.get("lines_added")      or pr.lines_added      or 0)
                lines_deleted     = float(parsed_pr.get("lines_deleted")    or pr.lines_deleted    or 0)
                comment_count     = float(parsed_pr.get("comment_count")    or pr.comment_count    or 0)
                wait_hours        = float(parsed_pr.get("wait_for_review_hours") or pr.wait_for_review_hours or 0)
                review_dur_hours  = float(parsed_pr.get("review_duration_hours") or pr.review_duration_hours or 0)
                # reviewer_count may come from GraphQL; fall back to review_count
                reviewer_count    = float(parsed_pr.get("reviewer_count")   or review_count)

                # ── Feature vectors (must match training schema in ml/models.py) ──
                delay_features = [
                    files_changed,
                    commit_count,
                    review_count,
                    lines_added,
                    lines_deleted,
                    reviewer_count,         # position 5 — reviewer count (or review_count)
                ]

                bottleneck_features = [
                    wait_hours,
                    review_dur_hours,
                    comment_count,
                    commit_count,
                    age_days,
                ]

                risk_features = [
                    comment_count,
                    review_count,
                    files_changed,
                    lines_added + lines_deleted,
                    0.5,                    # constant merge-probability prior (matches training)
                ]

                review_wait_features = [
                    review_count,
                    1.0,                    # intercept constant (matches training)
                    files_changed,
                    0.0,                    # placeholder (matches training)
                    1.0,                    # intercept constant (matches training)
                ]

                # ── Run inference ──────────────────────────────────────────────
                predicted_delay        = ml_models.predict_delay(delay_features)
                bottleneck_prob        = ml_models.predict_bottleneck(bottleneck_features)
                risk_score             = ml_models.predict_risk(risk_features)
                predicted_review_wait  = ml_models.predict_review_wait(review_wait_features)

                # Convert to float; ml model methods already return 0.0 on failure.
                predicted_delay       = float(predicted_delay)       if predicted_delay       is not None else 0.0
                bottleneck_prob       = float(bottleneck_prob)       if bottleneck_prob       is not None else 0.0
                risk_score            = float(risk_score)            if risk_score            is not None else 0.0
                predicted_review_wait = float(predicted_review_wait) if predicted_review_wait is not None else 0.0

                # Guard: skip storing when all outputs are effectively zero.
                # IsolationForest sigmoid can never output exactly 0.0, so if
                # bottleneck_prob is 0.0 the model itself failed or is absent.
                # Use a small epsilon threshold to catch genuine untrained returns.
                _EPSILON = 1e-6
                all_zero = (
                    predicted_delay       < _EPSILON and
                    bottleneck_prob       < _EPSILON and
                    risk_score            < _EPSILON and
                    predicted_review_wait < _EPSILON
                )
                if all_zero:
                    print(
                        f"[ML SKIP] All-near-zero prediction for PR {pr.pr_number} "
                        f"(delay={predicted_delay:.6f}, bottleneck={bottleneck_prob:.6f}, "
                        f"risk={risk_score:.6f}, wait={predicted_review_wait:.6f}) "
                        f"— model likely untrained or features all-zero. Skipping storage."
                    )
                    return

                # ── Upsert: remove any stale prediction, then insert new one ──
                from sqlalchemy import delete
                await self.db.execute(delete(MLPrediction).where(MLPrediction.pr_id == pr.id))
                prediction = MLPrediction(
                    pr_id=pr.id,
                    repo_owner=pr.repo_owner,
                    repo_name=pr.repo_name,
                    predicted_delay_days=predicted_delay,
                    bottleneck_probability=bottleneck_prob,
                    risk_score=risk_score,
                    predicted_review_wait=predicted_review_wait,
                )
                self.db.add(prediction)
                print(
                    f"[ML] Prediction stored for PR #{pr.pr_number}: "
                    f"risk={risk_score:.3f} bottleneck={bottleneck_prob:.3f} "
                    f"delay={predicted_delay:.1f}d wait={predicted_review_wait:.1f}h"
                )

            except Exception as e:
                print(f"[ML ERROR] Error preparing features for PR {pr.pr_number}: {str(e)}")
                # Continue without predictions

        except Exception as e:
            print(f"[ML ERROR] Error generating predictions: {str(e)}")
            # Don't crash - continue processing

    
    async def _update_contributor_stats(self, repo_id: int, repo: Repository = None):
        """Update contributor statistics"""
        try:
            # Get repository if not provided
            if not repo:
                repo = (await self.db.execute(select(Repository).filter(Repository.id == repo_id))).scalar_one_or_none()
                if not repo:
                    print(f"[WARN] Repository {repo_id} not found for contributor stats")
                    return
            
            now = datetime.now(timezone.utc)
            
            prs_result = await self.db.execute(select(PullRequest).filter(PullRequest.repo_id == repo_id))
            prs = prs_result.scalars().all()
            
            print(f"[STATS] Processing {len(prs)} PRs for contributor stats...")
            
            contributor_stats = {}
            for pr in prs:
                if not pr.author:
                    continue
                    
                if pr.author not in contributor_stats:
                    contributor_stats[pr.author] = {
                        "total_prs": 0,
                        "merged_prs": 0,
                        "cycle_times": [],
                        "review_times": [],
                        "stale_count": 0,
                    }
                
                contributor_stats[pr.author]["total_prs"] += 1
                
                if pr.state == "MERGED":
                    contributor_stats[pr.author]["merged_prs"] += 1
                    if pr.cycle_time_days and pr.cycle_time_days > 0:
                        contributor_stats[pr.author]["cycle_times"].append(pr.cycle_time_days)
                
                # Check if PR is stale (open for 30+ days)
                if pr.state == "OPEN" and pr.created_at:
                    created = pr.created_at
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    else:
                        created = created.astimezone(timezone.utc)
                    age_days = (now - created).days
                    if age_days > 30:
                        contributor_stats[pr.author]["stale_count"] += 1
                
                if pr.review_duration_hours and pr.review_duration_hours > 0:
                    contributor_stats[pr.author]["review_times"].append(pr.review_duration_hours)
            
            # Store or update contributors
            for username, stats in contributor_stats.items():
                try:
                    contributor = (await self.db.execute(select(Contributor).filter(Contributor.repo_id == repo_id, Contributor.username == username))).scalar_one_or_none()
                    
                    avg_cycle = np.mean(stats["cycle_times"]) if stats["cycle_times"] else 0.0
                    avg_review = np.mean(stats["review_times"]) if stats["review_times"] else 0.0
                    
                    if contributor:
                        contributor.repo_owner = repo.owner
                        contributor.repo_name = repo.name
                        contributor.total_prs = stats["total_prs"]
                        contributor.merged_prs = stats["merged_prs"]
                        contributor.avg_cycle_time = float(avg_cycle)
                        contributor.avg_review_time = float(avg_review)
                        contributor.stale_pr_count = stats["stale_count"]
                    else:
                        contributor = Contributor(
                            repo_id=repo_id,
                            repo_owner=repo.owner,
                            repo_name=repo.name,
                            username=username[:100],
                            total_prs=stats["total_prs"],
                            merged_prs=stats["merged_prs"],
                            avg_cycle_time=float(avg_cycle),
                            avg_review_time=float(avg_review),
                            stale_pr_count=stats["stale_count"],
                        )
                        self.db.add(contributor)
                except Exception as e:
                    print(f"[WARN] Error updating contributor {username}: {str(e)}")
                    continue
            
            print(f"[STATS] Updated {len(contributor_stats)} contributors")
        except Exception as e:
            print(f"[WARN] Error updating contributor stats: {str(e)}")
