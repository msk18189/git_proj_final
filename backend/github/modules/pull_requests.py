"""
github/modules/pull_requests.py

Enhanced Pull Request Intelligence sync.

Features:
- GraphQL paginated PR sync
- Incremental synchronization
- PR reviews sync
- PR commits sync
- PR changed files sync
- Telemetry logging
"""

from datetime import datetime, timezone, timedelta
import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from database.models import (
    Repository,
    PullRequest,
    PRReview,
    PRCommit,
    PRFile,
)

async def sync_pull_requests(
    owner: str,
    repo_name: str,
    db: AsyncSession,
    rest_client,
    gql_client,
    repo: Repository,
    since: Optional[datetime] = None,
    progress=None,
    batch_size: int = 500,
    lightweight_mode: bool = False,
) -> int:

    cursor = None
    has_next = True
    total_synced = 0
    stop_incremental = False

    repo_id = repo.id
    total_prs_val = repo.total_prs or 0
    sync_cursors_val = repo.sync_cursors
    rate_limit_limit_val = repo.rate_limit_limit
    rate_limit_remaining_val = repo.rate_limit_remaining

    # Initialize synced count from database count
    initial_synced = (await db.execute(select(func.count(PullRequest.id)).where(PullRequest.repo_id == repo_id))).scalar() or 0
    repo.synced_prs = initial_synced
    await db.commit()

    records_fetched = 0
    records_inserted = 0
    records_updated = 0
    records_skipped = 0
    api_response_count = 0

    since_cutoff = None

    if since:
        since_cutoff = since.replace(tzinfo=timezone.utc)
        since_cutoff = since_cutoff - timedelta(days=1)
        print(f"[Telemetry][PRs] Incremental sync mode: {since_cutoff}")
    else:
        print(f"[PRs] Full sync mode for {owner}/{repo_name}")

    use_graphql = gql_client.token is not None and not lightweight_mode

    if use_graphql:
        while has_next and not stop_incremental:
            try:
                raw_prs, page_info, rate_limit = gql_client.fetch_pull_requests(
                    owner,
                    repo_name,
                    first=100,
                    cursor=cursor,
                )
                api_response_count += 1
                if raw_prs:
                    records_fetched += len(raw_prs)
            
                # Persist rate limit and cursor info for resume in memory
                try:
                    if rate_limit:
                        rate_limit_limit_val = int(rate_limit.get("limit") or rate_limit_limit_val or 0)
                        rate_limit_remaining_val = int(rate_limit.get("remaining") or rate_limit_remaining_val or 0)
                    # store cursor
                    cursors = json.loads(sync_cursors_val) if sync_cursors_val else {}
                    cursors["pull_requests"] = page_info.get("endCursor") if page_info else None
                    sync_cursors_val = json.dumps(cursors)
                except Exception:
                    pass
            except Exception as e:
                print(f"[PRs] Page fetch failed: {e}")
                break

            if not raw_prs:
                break

            for raw_pr in raw_prs:
                try:
                    parsed = gql_client.parse_pr_data(raw_pr)
                except Exception as e:
                    print(f"[PRs] Parse error: {e}")
                    continue

                pr_updated_at = parsed.get("updated_at")

                if pr_updated_at and pr_updated_at.tzinfo is None:
                    pr_updated_at = pr_updated_at.replace(tzinfo=timezone.utc)

                # Incremental cutoff
                if since_cutoff and pr_updated_at and pr_updated_at < since_cutoff:
                    existing = (await db.execute(select(PullRequest).filter(
                        PullRequest.repo_id == repo_id,
                        PullRequest.pr_number == parsed["number"]
                    ))).scalars().first()

                    if existing:
                        stop_incremental = True
                        print(f"[PRs] Incremental cutoff reached")
                        break

                is_skipped = False
                existing = (await db.execute(select(PullRequest).filter(
                    PullRequest.repo_id == repo_id,
                    PullRequest.pr_number == parsed["number"]
                ))).scalars().first()

                if existing:
                    existing_updated = existing.updated_at
                    if existing_updated and pr_updated_at and existing_updated.replace(tzinfo=timezone.utc) == pr_updated_at:
                        records_skipped += 1
                        pr_obj = existing
                        is_skipped = True
                    else:
                        _update_pr(existing, owner, repo_name, parsed)
                        pr_obj = existing
                        records_updated += 1
                        print(f"[Telemetry][PRs] Incremental Decision: Updating PR #{parsed['number']}.")
                else:
                    pr_obj = _create_pr(repo_id, owner, repo_name, parsed)
                    db.add(pr_obj)
                    await db.flush()
                    records_inserted += 1
                    print(f"[Telemetry][PRs] Incremental Decision: Inserting brand new PR #{parsed['number']}.")

                # Reviews
                has_reviews = False
                if existing:
                    has_reviews = (await db.execute(select(PRReview).filter(PRReview.pr_id == pr_obj.id))).scalars().first() is not None

                if not (is_skipped and has_reviews) and not lightweight_mode:
                    await _upsert_reviews(
                        db,
                        pr_obj.id,
                        repo_id,
                        parsed.get("reviews", []),
                    )

                # Commits
                has_commits = False
                if existing:
                    has_commits = (await db.execute(select(PRCommit).filter(PRCommit.pr_id == pr_obj.id))).scalars().first() is not None

                if not (is_skipped and has_commits) and not lightweight_mode:
                    try:
                        commit_nodes = rest_client.fetch_pull_request_commits(
                            owner,
                            repo_name,
                            parsed["number"],
                        )
                        await _upsert_commits(
                            db,
                            pr_obj.id,
                            repo_id,
                            commit_nodes,
                        )
                        print(
                            f"[Telemetry][Commits] PR #{parsed['number']}: "
                            f"fetched={len(commit_nodes)}, db_records={len(commit_nodes)}"
                        )
                    except Exception as e:
                        print(f"[Telemetry][Commits] Failed for PR #{parsed['number']}: {e}")

                # Files
                has_files = False
                if existing:
                    has_files = (await db.execute(select(PRFile).filter(PRFile.pr_id == pr_obj.id))).scalars().first() is not None

                if not (is_skipped and has_files) and not lightweight_mode:
                    try:
                        file_nodes = rest_client.fetch_pull_request_files(
                            owner,
                            repo_name,
                            parsed["number"],
                        )
                        await _upsert_files(
                            db,
                            pr_obj.id,
                            repo_id,
                            file_nodes,
                        )
                        print(
                            f"[Telemetry][Files] PR #{parsed['number']}: "
                            f"fetched={len(file_nodes)}, db_records={len(file_nodes)}"
                        )
                    except Exception as e:
                        print(f"[Telemetry][Files] Failed for PR #{parsed['number']}: {e}")

                total_synced += 1

                if progress and total_synced % 10 == 0:
                    await progress.update(
                        f"Syncing {owner}/{repo_name} Pull Requests",
                        module="pull_requests",
                        processed=total_synced,
                        discovered=max(total_synced, total_prs_val),
                    )

                if total_synced % batch_size == 0:
                    await db.commit()

            has_next = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

        await db.commit()
    else:
        # Lightweight REST-based PR sync
        print(f"[PRs] Using lightweight REST-based sync for {owner}/{repo_name}")
        pages_generator = rest_client.get_pull_requests(owner, repo_name)
        for raw_prs in pages_generator:
            if stop_incremental:
                break
            api_response_count += 1
            if raw_prs:
                records_fetched += len(raw_prs)

            for raw_pr in raw_prs:
                try:
                    parsed = rest_client.parse_rest_pr_data(raw_pr)
                except Exception as e:
                    print(f"[PRs] REST parse error: {e}")
                    continue

                pr_updated_at = parsed.get("updated_at")

                if pr_updated_at and pr_updated_at.tzinfo is None:
                    pr_updated_at = pr_updated_at.replace(tzinfo=timezone.utc)

                # Incremental cutoff
                if since_cutoff and pr_updated_at and pr_updated_at < since_cutoff:
                    existing = (await db.execute(select(PullRequest).filter(
                        PullRequest.repo_id == repo_id,
                        PullRequest.pr_number == parsed["number"]
                    ))).scalars().first()
                    if existing:
                        stop_incremental = True
                        print(f"[PRs] Incremental cutoff reached")
                        break

                is_skipped = False
                existing = (await db.execute(select(PullRequest).filter(
                    PullRequest.repo_id == repo_id,
                    PullRequest.pr_number == parsed["number"]
                ))).scalars().first()

                if existing:
                    existing_updated = existing.updated_at
                    if existing_updated and pr_updated_at and existing_updated.replace(tzinfo=timezone.utc) == pr_updated_at:
                        records_skipped += 1
                        pr_obj = existing
                        is_skipped = True
                    else:
                        _update_pr(existing, owner, repo_name, parsed)
                        pr_obj = existing
                        records_updated += 1
                        print(f"[Telemetry][PRs] Incremental Decision: Updating PR #{parsed['number']}.")
                else:
                    pr_obj = _create_pr(repo_id, owner, repo_name, parsed)
                    db.add(pr_obj)
                    await db.flush()
                    records_inserted += 1
                    print(f"[Telemetry][PRs] Incremental Decision: Inserting brand new PR #{parsed['number']}.")

                # Reviews
                has_reviews = False
                if existing:
                    has_reviews = (await db.execute(select(PRReview).filter(PRReview.pr_id == pr_obj.id))).scalars().first() is not None

                if not (is_skipped and has_reviews) and not lightweight_mode:
                    try:
                        review_nodes = rest_client.get_pr_reviews(owner, repo_name, parsed["number"])
                        await _upsert_reviews(db, pr_obj.id, repo_id, review_nodes)
                        pr_obj.review_count = len(review_nodes)
                    except Exception as e:
                        print(f"[Telemetry][Reviews] Failed for PR #{parsed['number']}: {e}")

                # Commits
                has_commits = False
                if existing:
                    has_commits = (await db.execute(select(PRCommit).filter(PRCommit.pr_id == pr_obj.id))).scalars().first() is not None

                if not (is_skipped and has_commits) and not lightweight_mode:
                    try:
                        commit_nodes = rest_client.fetch_pull_request_commits(
                            owner,
                            repo_name,
                            parsed["number"],
                        )
                        await _upsert_commits(
                            db,
                            pr_obj.id,
                            repo_id,
                            commit_nodes,
                        )
                        pr_obj.commit_count = len(commit_nodes)
                    except Exception as e:
                        print(f"[Telemetry][Commits] Failed for PR #{parsed['number']}: {e}")

                # Files
                has_files = False
                if existing:
                    has_files = (await db.execute(select(PRFile).filter(PRFile.pr_id == pr_obj.id))).scalars().first() is not None

                if not (is_skipped and has_files) and not lightweight_mode:
                    try:
                        file_nodes = rest_client.fetch_pull_request_files(
                            owner,
                            repo_name,
                            parsed["number"],
                        )
                        await _upsert_files(
                            db,
                            pr_obj.id,
                            repo_id,
                            file_nodes,
                        )
                        pr_obj.files_changed = len(file_nodes)
                        pr_obj.lines_added = sum(f.get("additions", 0) for f in file_nodes if f)
                        pr_obj.lines_deleted = sum(f.get("deletions", 0) for f in file_nodes if f)
                    except Exception as e:
                        print(f"[Telemetry][Files] Failed for PR #{parsed['number']}: {e}")

                total_synced += 1

                if progress and total_synced % 10 == 0:
                    await progress.update(
                        f"Syncing {owner}/{repo_name} Pull Requests",
                        module="pull_requests",
                        processed=total_synced,
                        discovered=max(total_synced, total_prs_val),
                    )

                if total_synced % batch_size == 0:
                    await db.commit()

            if lightweight_mode:
                print(f"[PRs] Lightweight mode active: processed one page of PRs. Breaking pagination.")
                break

        await db.commit()

    repo = await db.get(Repository, repo_id)
    repo.total_prs = (await db.execute(select(func.count(PullRequest.id)).where(PullRequest.repo_id == repo_id))).scalar() or 0
    repo.synced_prs = repo.total_prs
    repo.sync_cursors = sync_cursors_val
    if rate_limit_limit_val:
        repo.rate_limit_limit = rate_limit_limit_val
    if rate_limit_remaining_val:
        repo.rate_limit_remaining = rate_limit_remaining_val

    total_prs_final = repo.total_prs
    await db.commit()

    print(f"[Telemetry][PRs] Sync complete. Stats: fetched={records_fetched}, inserted={records_inserted}, updated={records_updated}, skipped={records_skipped}, api_responses={api_response_count}")
    print(f"[PRs] Sync complete. Synced: {total_synced}, Total in DB: {total_prs_final}")

    return total_synced


def _create_pr(repo_id: int, owner: str, repo_name: str, parsed: dict):

    return PullRequest(
        repo_id=repo_id,
        repo_owner=owner,
        repo_name=repo_name,
        pr_number=parsed["number"],
        github_node_id=parsed.get("github_node_id"),
        title=(parsed.get("title") or "")[:200],
        body=parsed.get("body"),
        state=parsed["state"],
        draft=parsed.get("draft", False),
        merge_state=parsed.get("merge_state"),
        labels=parsed.get("labels", ""),
        base_branch=parsed.get("base_branch"),
        head_branch=parsed.get("head_branch"),
        author=parsed.get("author", "unknown")[:100],
        created_at=parsed["created_at"],
        updated_at=parsed.get("updated_at"),
        merged_at=parsed.get("merged_at"),
        closed_at=parsed.get("closed_at"),
        commit_count=parsed.get("commit_count", 0),
        files_changed=parsed.get("files_changed", 0),
        lines_added=parsed.get("lines_added", 0),
        lines_deleted=parsed.get("lines_deleted", 0),
        review_count=parsed.get("review_count", 0),
        comment_count=parsed.get("comment_count", 0),
        cycle_time_days=parsed.get("cycle_time_days"),
        wait_for_review_hours=parsed.get("wait_for_review_hours"),
        review_duration_hours=parsed.get("review_duration_hours"),
    )


def _update_pr(existing: PullRequest, owner: str, repo_name: str, parsed: dict):

    existing.repo_owner = owner
    existing.repo_name = repo_name
    existing.title = (parsed.get("title") or "")[:200]
    existing.body = parsed.get("body")
    existing.state = parsed["state"]
    existing.draft = parsed.get("draft", False)
    existing.merge_state = parsed.get("merge_state")
    existing.labels = parsed.get("labels", "")
    existing.base_branch = parsed.get("base_branch")
    existing.head_branch = parsed.get("head_branch")
    existing.updated_at = parsed.get("updated_at")
    existing.merged_at = parsed.get("merged_at")
    existing.closed_at = parsed.get("closed_at")
    existing.commit_count = parsed.get("commit_count", 0)
    existing.files_changed = parsed.get("files_changed", 0)
    existing.lines_added = parsed.get("lines_added", 0)
    existing.lines_deleted = parsed.get("lines_deleted", 0)
    existing.review_count = parsed.get("review_count", 0)
    existing.comment_count = parsed.get("comment_count", 0)
    existing.cycle_time_days = parsed.get("cycle_time_days")
    existing.wait_for_review_hours = parsed.get("wait_for_review_hours")
    existing.review_duration_hours = parsed.get("review_duration_hours")


async def _upsert_reviews(db, pr_id, repo_id, review_nodes):

    for rev in review_nodes:

        reviewer = "unknown"
        if "author" in rev:
            reviewer = (rev.get("author") or {}).get("login", "unknown")
        elif "user" in rev:
            reviewer = (rev.get("user") or {}).get("login", "unknown")

        submitted_at = None
        submitted_at_str = rev.get("submittedAt") or rev.get("submitted_at")
        if submitted_at_str:
            submitted_at = datetime.fromisoformat(
                submitted_at_str.replace("Z", "+00:00")
            )

        existing = (await db.execute(select(PRReview).filter(
            PRReview.pr_id == pr_id,
            PRReview.reviewer == reviewer,
            PRReview.submitted_at == submitted_at,
        ))).scalars().first()

        if existing:
            existing.state = rev.get("state", "COMMENTED")

        else:
            comment_count = 0
            if isinstance(rev.get("comments"), dict):
                comment_count = rev.get("comments", {}).get("totalCount", 0)
            db.add(
                PRReview(
                    pr_id=pr_id,
                    repo_id=repo_id,
                    reviewer=reviewer,
                    state=rev.get("state", "COMMENTED"),
                    submitted_at=submitted_at,
                    comment_count=comment_count,
                )
            )


async def _upsert_commits(db, pr_id, repo_id, commit_nodes):

    for commit in commit_nodes:

        sha = commit.get("sha")

        if not sha:
            continue

        existing = (await db.execute(select(PRCommit).filter(
            PRCommit.pr_id == pr_id,
            PRCommit.sha == sha,
        ))).scalars().first()

        if existing:
            continue

        commit_info = commit.get("commit", {})
        author_info = commit_info.get("author", {})

        committed_at = None

        if author_info.get("date"):
            committed_at = datetime.fromisoformat(
                author_info["date"].replace("Z", "+00:00")
            )

        db.add(
            PRCommit(
                pr_id=pr_id,
                repo_id=repo_id,
                sha=sha,
                message=commit_info.get("message"),
                author=author_info.get("name"),
                committed_at=committed_at,
                additions=0,
                deletions=0,
            )
        )


async def _upsert_files(db, pr_id, repo_id, file_nodes):

    for file in file_nodes:
        filename = file.get("filename")
        if not filename:
            continue
        existing = (await db.execute(select(PRFile).filter(
            PRFile.pr_id == pr_id,
            PRFile.filename == filename,
        ))).scalars().first()

        if existing:
            existing.status = file.get("status")
            existing.additions = file.get("additions", 0)
            existing.deletions = file.get("deletions", 0)

        else:
            db.add(
                PRFile(
                    pr_id=pr_id,
                    repo_id=repo_id,
                    filename=filename,
                    status=file.get("status"),
                    additions=file.get("additions", 0),
                    deletions=file.get("deletions", 0),
                    changes=file.get("changes", 0),
                )
            )