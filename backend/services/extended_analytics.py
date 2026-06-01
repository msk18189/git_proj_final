import csv
import io
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, case, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import MLPrediction, PullRequest, Repository, PRReview, PRCommit, Contributor
from services.filters import (
    PRFilterParams,
    ensure_utc,
    format_duration,
    get_filtered_prs,
    get_filtered_prs_query,
    list_authors,
    pr_cycle_hours,
)
from services.analytics import AnalyticsService, _ensure_utc, _iso_week_key, _month_key
from services.analytics import _month_range, _format_month_label, _week_range, _week_label

def _filters_from_params(
    days: Optional[int] = None,
    author: Optional[str] = None,
    state: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> PRFilterParams:
    return PRFilterParams(days=days, author=author, state=state, start_date=start_date, end_date=end_date)

class ExtendedAnalytics:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.base = AnalyticsService(db)

    async def _get_latest_activity_timestamp(self, pr: PullRequest) -> Optional[datetime]:
        timestamps = []
        
        if pr.updated_at:
            timestamps.append(ensure_utc(pr.updated_at))
        
        result = await self.db.execute(select(func.max(PRReview.submitted_at)).where(PRReview.pr_id == pr.id))
        latest_review = result.scalar()
        if latest_review:
            timestamps.append(ensure_utc(latest_review))
        
        result = await self.db.execute(select(func.max(PRCommit.committed_at)).where(PRCommit.pr_id == pr.id))
        latest_commit = result.scalar()
        if latest_commit:
            timestamps.append(ensure_utc(latest_commit))
        
        if pr.created_at:
            timestamps.append(ensure_utc(pr.created_at))
        
        return max(timestamps) if timestamps else None

    async def _get_inactivity_days(self, pr: PullRequest) -> int:
        latest_activity = await self._get_latest_activity_timestamp(pr)
        if not latest_activity:
            return 0
        now = ensure_utc(datetime.utcnow())
        return (now - latest_activity).days

    def _get_stale_severity(self, inactivity_days: int) -> str:
        if inactivity_days < 7:
            return "healthy"
        elif inactivity_days < 30:
            return "warning"
        elif inactivity_days < 60:
            return "stale"
        else:
            return "critical"

    async def get_kpi_with_duration(
        self,
        repo_id: int,
        days: Optional[int] = None,
        author: Optional[str] = None,
        state: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        filters = _filters_from_params(days, author, state, start_date, end_date)
        query = get_filtered_prs_query(repo_id, filters)
        
        subq = query.subquery()
        
        result = await self.db.execute(select(func.count(subq.c.id)))
        total_count = result.scalar() or 0
        
        result = await self.db.execute(select(func.count(subq.c.id)).where(subq.c.state == "OPEN"))
        open_count = result.scalar() or 0
        
        result = await self.db.execute(query.where(PullRequest.state == "OPEN"))
        open_prs = result.scalars().all()
        
        stale_count = 0
        for pr in open_prs:
            inactivity_days = await self._get_inactivity_days(pr)
            if inactivity_days >= 30:
                stale_count += 1
        
        result = await self.db.execute(select(func.count(subq.c.id)).where(subq.c.state == "MERGED"))
        merged_count = result.scalar() or 0
        
        result = await self.db.execute(select(func.count(subq.c.id)).where(subq.c.state.in_(["MERGED", "CLOSED"])))
        closed_count = result.scalar() or 0

        result = await self.db.execute(select(func.avg(subq.c.cycle_time_days)).where(subq.c.state == "MERGED"))
        avg_cycle_days_result = result.scalar()
        avg_cycle = float(avg_cycle_days_result) * 24 if avg_cycle_days_result is not None else None

        result = await self.db.execute(select(subq.c.cycle_time_days).where(subq.c.state == "MERGED", subq.c.cycle_time_days.isnot(None)).order_by(subq.c.cycle_time_days))
        cycle_times = [float(r) for r in result.scalars().all()]
        if cycle_times:
            n = len(cycle_times)
            median_cycle = (cycle_times[n // 2] if n % 2 == 1 else (cycle_times[n // 2 - 1] + cycle_times[n // 2]) / 2) * 24
        else:
            median_cycle = None

        result = await self.db.execute(select(func.avg(subq.c.wait_for_review_hours)).where(subq.c.wait_for_review_hours.isnot(None), subq.c.wait_for_review_hours >= 0))
        avg_wait_result = result.scalar()
        avg_wait = float(avg_wait_result) if avg_wait_result is not None else None
        
        result = await self.db.execute(select(func.avg(subq.c.review_duration_hours)).where(subq.c.review_duration_hours.isnot(None), subq.c.review_duration_hours >= 0))
        avg_review_result = result.scalar()
        avg_review = float(avg_review_result) if avg_review_result is not None else None

        merge_rate = round((merged_count / closed_count * 100) if closed_count else 0, 2)
        
        result = await self.db.execute(select(func.avg(subq.c.review_count)))
        avg_reviews = float(result.scalar() or 0.0)

        result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one_or_none()

        result = await self.db.execute(select(func.count(subq.c.id)).where(subq.c.state == "CLOSED"))
        closed_not_merged_count = result.scalar() or 0

        return {
            "total_prs": total_count,
            "open_prs": open_count,
            "merged_prs": merged_count,
            "closed_not_merged_prs": closed_not_merged_count,
            "stale_prs": stale_count,
            "avg_cycle_time": round(avg_cycle / 24, 2) if avg_cycle is not None else None,
            "median_cycle_time": round(median_cycle / 24, 1) if median_cycle is not None else None,
            "avg_wait_for_review": round(avg_wait / 24, 2) if avg_wait is not None else None,
            "avg_review_duration": round(avg_review / 24, 2) if avg_review is not None else None,
            "merge_rate": merge_rate,
            "avg_reviews_per_pr": round(avg_reviews, 1),
            "avg_cycle_time_display": format_duration(avg_cycle),
            "median_cycle_time_display": format_duration(median_cycle),
            "avg_wait_for_review_display": format_duration(avg_wait),
            "avg_review_duration_display": format_duration(avg_review),
            "expected_prs": repo.expected_prs if repo else 0,
            "synced_prs": repo.synced_prs if repo else 0,
            "expected_issues": repo.expected_issues if repo else 0,
            "synced_issues": repo.synced_issues if repo else 0,
            "expected_forks": repo.expected_forks if repo else 0,
            "synced_forks": repo.synced_forks if repo else 0,
            "expected_workflows": repo.expected_workflows if repo else 0,
            "synced_workflows": repo.synced_workflows if repo else 0,
        }

    async def get_monthly_flow_filtered(
        self, repo_id: int, months: int = 6, **filter_kw
    ) -> List[Dict[str, Any]]:
        filters = _filters_from_params(**filter_kw)
        query = get_filtered_prs_query(repo_id, filters)
        month_keys = _month_range(months)
        flow = {
            ym: {"month": _format_month_label(ym), "created": 0, "merged": 0, "closed": 0, "open_at_end": 0}
            for ym in month_keys
        }
        
        result = await self.db.execute(query.with_only_columns(
            PullRequest.created_at,
            PullRequest.merged_at,
            PullRequest.closed_at,
            PullRequest.state
        ))
        rows = result.all()
        
        for created_at, merged_at, closed_at, state in rows:
            if created_at:
                m = _month_key(created_at)
                if m in flow:
                    flow[m]["created"] += 1
            if merged_at:
                m = _month_key(merged_at)
                if m in flow:
                    flow[m]["merged"] += 1
            if state == "CLOSED" and closed_at:
                m = _month_key(closed_at)
                if m in flow:
                    flow[m]["closed"] += 1
                    
        for ym in month_keys:
            y, m_ = map(int, ym.split("-"))
            if m_ == 12:
                next_y, next_m = y + 1, 1
            else:
                next_y, next_m = y, m_ + 1
            end_of_month = datetime(next_y, next_m, 1)
            
            open_count = 0
            for created_at, merged_at, closed_at, state in rows:
                if not created_at:
                    continue
                c_at = created_at.replace(tzinfo=None) if created_at.tzinfo else created_at
                m_at = merged_at.replace(tzinfo=None) if merged_at and merged_at.tzinfo else merged_at
                cl_at = closed_at.replace(tzinfo=None) if closed_at and closed_at.tzinfo else closed_at
                
                if c_at < end_of_month:
                    is_merged_before = m_at and m_at < end_of_month
                    is_closed_before = cl_at and cl_at < end_of_month and state == "CLOSED"
                    
                    if not is_merged_before and not is_closed_before:
                        open_count += 1
            flow[ym]["open_at_end"] = open_count
            
        return [flow[ym] for ym in month_keys]

    async def get_throughput_filtered(
        self, repo_id: int, weeks: int = 8, **filter_kw
    ) -> List[Dict[str, Any]]:
        filters = _filters_from_params(**filter_kw)
        query = get_filtered_prs_query(repo_id, filters)
        week_keys = _week_range(weeks)
        counts = {k: 0 for k in week_keys}
        
        result = await self.db.execute(query.where(PullRequest.state == "MERGED", PullRequest.merged_at.isnot(None))\
            .with_only_columns(PullRequest.merged_at))
        rows = result.all()
            
        for (merged_at,) in rows:
            key = _iso_week_key(merged_at)
            if key in counts:
                counts[key] += 1
        return [{"week": _week_label(y, w), "prs": counts[(y, w)]} for y, w in week_keys]

    async def get_contributors_filtered(self, repo_id: int, page: int = 1, limit: int = 10, **filter_kw) -> Dict[str, Any]:
        filters = _filters_from_params(**filter_kw)
        
        # Query all contributors from database table first
        contrib_result = await self.db.execute(select(Contributor).where(Contributor.repo_id == repo_id))
        db_contribs = contrib_result.scalars().all()
        
        total_commits = sum(c.contributions for c in db_contribs)
        
        # Get PR stats filtered by time range/author
        prs_query = get_filtered_prs_query(repo_id, filters)
        prs_result = await self.db.execute(prs_query)
        all_prs = prs_result.scalars().all()
        
        # Aggregate filtered PR stats in memory
        author_stats = {}
        for pr in all_prs:
            author = pr.author
            if not author:
                continue
            if author not in author_stats:
                author_stats[author] = {
                    "total_prs": 0,
                    "merged_prs": 0,
                    "open_prs": 0,
                    "stale_prs": 0,
                    "cycle_times": [],
                    "wait_times": [],
                }
            author_stats[author]["total_prs"] += 1
            if pr.state == "MERGED":
                author_stats[author]["merged_prs"] += 1
                if pr.cycle_time_days is not None:
                    author_stats[author]["cycle_times"].append(pr.cycle_time_days)
            elif pr.state == "OPEN":
                author_stats[author]["open_prs"] += 1
                inactivity_days = await self._get_inactivity_days(pr)
                if inactivity_days >= 30:
                    author_stats[author]["stale_prs"] += 1
            if pr.wait_for_review_hours is not None and pr.wait_for_review_hours >= 0:
                author_stats[author]["wait_times"].append(pr.wait_for_review_hours)

        # Build list of all contributors
        formatted_results = []
        processed_usernames = set()
        
        for c in db_contribs:
            username = c.username
            processed_usernames.add(username)
            
            # Get filtered PR stats for this user, if any
            stats = author_stats.get(username)
            
            if stats:
                total_prs = stats["total_prs"]
                merged_prs = stats["merged_prs"]
                open_prs = stats["open_prs"]
                stale_prs = stats["stale_prs"]
                avg_cycle_days = (sum(stats["cycle_times"]) / len(stats["cycle_times"])) if stats["cycle_times"] else None
                avg_wait_h = (sum(stats["wait_times"]) / len(stats["wait_times"])) if stats["wait_times"] else None
            else:
                has_date_filters = any(filter_kw.get(k) is not None for k in ["days", "start_date", "end_date"])
                total_prs = 0 if has_date_filters else c.total_prs
                merged_prs = 0 if has_date_filters else c.merged_prs
                open_prs = 0 if has_date_filters else (c.total_prs - c.merged_prs)
                stale_prs = 0 if has_date_filters else c.stale_pr_count
                avg_cycle_days = None if has_date_filters else c.avg_cycle_time
                avg_wait_h = None
            
            avg_cycle_h = avg_cycle_days * 24 if avg_cycle_days is not None else None
            avg_wait_days = avg_wait_h / 24 if avg_wait_h is not None else None
            
            formatted_results.append({
                "username": username,
                "total_prs": total_prs,
                "merged_prs": merged_prs,
                "open_prs": open_prs,
                "stale_prs": stale_prs,
                "avg_cycle_time": round(avg_cycle_days, 2) if avg_cycle_days is not None else None,
                "avg_cycle_time_display": format_duration(avg_cycle_h),
                "avg_wait_for_review": round(avg_wait_days, 2) if avg_wait_days is not None else None,
                "merge_rate": round((merged_prs / total_prs * 100) if total_prs else 0, 2),
                "contributions": c.contributions,
                "type": c.type,
                "contribution_percentage": round((c.contributions / total_commits * 100), 2) if total_commits > 0 else 0.0,
            })

        formatted_results.sort(key=lambda x: (x["contributions"], x["total_prs"]), reverse=True)
        total_contributors = len(formatted_results)
        offset = (page - 1) * limit
        paginated_results = formatted_results[offset:offset+limit]
            
        return {
            "data": paginated_results,
            "total": total_contributors,
            "page": page,
            "limit": limit,
            "pages": (total_contributors + limit - 1) // limit if limit else 1
        }

    async def get_oldest_open_filtered(self, repo_id: int, page: int = 1, limit: int = 10, **filter_kw) -> Dict[str, Any]:
        filters = _filters_from_params(**filter_kw)
        filters.state = "OPEN"
        query = get_filtered_prs_query(repo_id, filters)
        
        query = query.order_by(PullRequest.created_at.asc())
        
        result_count = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = result_count.scalar() or 0
        
        offset = (page - 1) * limit
        result = await self.db.execute(query.offset(offset).limit(limit))
        prs = result.scalars().all()
        
        now = ensure_utc(datetime.utcnow())
        data = [
            {
                "number": pr.pr_number,
                "title": pr.title,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
                "age_days": (now - ensure_utc(pr.created_at)).days if pr.created_at else 0,
                "author": pr.author,
                "review_count": pr.review_count,
            }
            for pr in prs
        ]
        return {
            "data": data,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit else 1
        }

    async def get_slowest_merged_filtered(self, repo_id: int, page: int = 1, limit: int = 10, **filter_kw) -> Dict[str, Any]:
        filters = _filters_from_params(**filter_kw)
        filters.state = "MERGED"
        query = get_filtered_prs_query(repo_id, filters)
        
        query = query.where(PullRequest.cycle_time_days.isnot(None))\
            .order_by(PullRequest.cycle_time_days.desc())
            
        result_count = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = result_count.scalar() or 0
        
        offset = (page - 1) * limit
        result = await self.db.execute(query.offset(offset).limit(limit))
        prs = result.scalars().all()
        
        data = [
            {
                "number": pr.pr_number,
                "title": pr.title,
                "cycle_time_days": round(pr.cycle_time_days, 2) if pr.cycle_time_days is not None else None,
                "cycle_time_display": format_duration(pr.cycle_time_days * 24 if pr.cycle_time_days is not None else None),
                "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                "author": pr.author,
                "review_count": pr.review_count,
                "files_changed": pr.files_changed,
            }
            for pr in prs
        ]
        return {
            "data": data,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit else 1
        }

    async def get_authors(self, repo_id: int) -> List[str]:
        return await list_authors(self.db, repo_id)

    async def get_pr_risk_panel(self, repo_id: int, page: int = 1, limit: int = 15) -> Dict[str, Any]:
        open_prs_query = select(PullRequest)\
            .where(PullRequest.repo_id == repo_id, PullRequest.state == "OPEN")
            
        result_count = await self.db.execute(select(func.count()).select_from(open_prs_query.subquery()))
        total = result_count.scalar() or 0
        
        query = select(PullRequest, MLPrediction)\
            .outerjoin(MLPrediction, PullRequest.id == MLPrediction.pr_id)\
            .where(
                PullRequest.repo_id == repo_id,
                PullRequest.state == "OPEN"
            )\
            .order_by(
                case(
                    (MLPrediction.risk_score == None, 1),
                    else_=0
                ),
                MLPrediction.risk_score.desc(),
                PullRequest.created_at.asc()
            )
        offset = (page - 1) * limit
        result = await self.db.execute(query.offset(offset).limit(limit))
        results = result.all()
        
        data = []
        for pr, pred in results:
            if pred:
                score_source = "ml"
                risk_score = round((pred.risk_score or 0) * 100, 1)
                bottleneck_probability = round((pred.bottleneck_probability or 0) * 100, 1)
                predicted_delay_days = pred.predicted_delay_days
                predicted_delay_display = (
                    format_duration(predicted_delay_days * 24)
                    if predicted_delay_days is not None
                    else None
                )
                predicted_review_wait_hours = (
                    round(pred.predicted_review_wait, 1)
                    if pred.predicted_review_wait is not None
                    else None
                )
            else:
                now = ensure_utc(datetime.utcnow())
                pr_created = ensure_utc(pr.created_at) if pr.created_at else now
                age_days = (now - pr_created).days

                score_source = "heuristic"
                
                files_cnt = pr.files_changed or 0
                lines_added = pr.lines_added or 0
                lines_deleted = pr.lines_deleted or 0
                total_lines = lines_added + lines_deleted
                size_risk = min(40, (files_cnt * 2) + int(total_lines * 0.04))
                
                age_risk = min(30, age_days * 1.5)
                
                comment_cnt = pr.comment_count or 0
                rev_cnt = pr.review_count or 0
                activity_risk = 0
                if rev_cnt == 0:
                    activity_risk += 20
                elif comment_cnt > 10 and rev_cnt < 2:
                    activity_risk += 15
                activity_risk = min(30, activity_risk + min(10, comment_cnt * 1))
                
                risk_score = float(size_risk + age_risk + activity_risk)
                
                base_bottleneck = 0
                if rev_cnt == 0:
                    if age_days > 14:
                        base_bottleneck = 70.0
                    elif age_days > 7:
                        base_bottleneck = 50.0
                    elif age_days > 3:
                        base_bottleneck = 30.0
                    else:
                        base_bottleneck = 15.0
                else:
                    if age_days > 30:
                        base_bottleneck = 60.0
                    elif age_days > 14:
                        base_bottleneck = 40.0
                    elif age_days > 7:
                        base_bottleneck = 20.0
                    else:
                        base_bottleneck = 5.0
                        
                size_factor = min(30.0, files_cnt * 1.5)
                bottleneck_probability = round(min(100.0, base_bottleneck + size_factor), 1)
                
                predicted_delay_days = max(1.0, float(files_cnt * 0.2 + total_lines * 0.005 + age_days * 0.1))
                predicted_delay_display = format_duration(predicted_delay_days * 24)
                
                if rev_cnt == 0:
                    predicted_review_wait_hours = float(max(24.0, age_days * 24.0))
                else:
                    predicted_review_wait_hours = 12.0
                
            data.append({
                "number": pr.pr_number,
                "title": pr.title,
                "author": pr.author,
                "review_count": pr.review_count or 0,
                "files_changed": pr.files_changed or 0,
                "predicted_delay_days": predicted_delay_days,
                "predicted_delay_display": predicted_delay_display,
                "bottleneck_probability": bottleneck_probability,
                "risk_score": risk_score,
                "predicted_review_wait_hours": predicted_review_wait_hours,
                "score_source": score_source,
            })
            
        return {
            "data": data,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit else 1
        }

    async def get_stale_recommendations(self, repo_id: int, page: int = 1, limit: int = 10, stale_days: int = 30) -> Dict[str, Any]:
        now = ensure_utc(datetime.utcnow())
        
        result = await self.db.execute(select(PullRequest).where(
            PullRequest.repo_id == repo_id,
            PullRequest.state == "OPEN",
            PullRequest.draft == False
        ))
        open_prs = result.scalars().all()
        
        stale_alerts = []
        
        for pr in open_prs:
            inactivity_days = await self._get_inactivity_days(pr)
            severity = self._get_stale_severity(inactivity_days)
            
            if severity not in ["warning", "stale", "critical"]:
                continue
            
            reasons: List[str] = []
            actions: List[str] = []
            
            if inactivity_days >= 60:
                reasons.append(f"No activity for {inactivity_days} days (CRITICAL)")
                actions.append("Prioritize review immediately or close if abandoned")
                actions.append("Consider reaching out to author for status")
            elif inactivity_days >= 30:
                reasons.append(f"No activity for {inactivity_days} days (STALE)")
                actions.append("Review or close PR to reduce technical debt")
                actions.append("Ping author if PR is still relevant")
            elif inactivity_days >= 7:
                reasons.append(f"No activity for {inactivity_days} days (WARNING)")
                actions.append("Monitor progress and request review if needed")
            
            if pr.review_count == 0:
                reasons.append("No reviews received yet")
                actions.append("Assign reviewer or request feedback")
            elif pr.review_count > 0 and inactivity_days > 14:
                reasons.append(f"Received {pr.review_count} review(s) but stalled")
                actions.append("Address review feedback or discuss blockers")
            
            if pr.files_changed and pr.files_changed > 30:
                reasons.append(f"Large changeset ({pr.files_changed} files) may be complex")
                actions.append("Consider breaking into smaller PRs for faster review")
            
            if not reasons:
                reasons.append(f"Inactive for {inactivity_days} days")
                actions.append("Review PR status and current relevance")
            
            stale_alerts.append({
                "number": pr.pr_number,
                "title": pr.title,
                "author": pr.author,
                "age_days": inactivity_days,
                "severity": severity,
                "reasons": reasons,
                "recommended_actions": actions,
            })
        
        severity_order = {"critical": 0, "stale": 1, "warning": 2}
        stale_alerts.sort(
            key=lambda x: (
                severity_order.get(x["severity"], 3),
                -x["age_days"]
            )
        )
        
        offset = (page - 1) * limit
        paginated_alerts = stale_alerts[offset:offset+limit]
        
        return {
            "data": paginated_alerts,
            "total": len(stale_alerts),
            "page": page,
            "limit": limit,
            "pages": (len(stale_alerts) + limit - 1) // limit if limit else 1
        }

    async def compare_repos(self, repo_id_a: int, repo_id_b: int) -> Dict[str, Any]:
        result_a = await self.db.execute(select(Repository).where(Repository.id == repo_id_a))
        repo_a = result_a.scalar_one_or_none()
        
        result_b = await self.db.execute(select(Repository).where(Repository.id == repo_id_b))
        repo_b = result_b.scalar_one_or_none()
        
        if not repo_a or not repo_b:
            raise ValueError("One or both repositories not found")

        kpi_a = await self.get_kpi_with_duration(repo_id_a)
        kpi_b = await self.get_kpi_with_duration(repo_id_b)

        def delta(key: str) -> Optional[float]:
            a, b = kpi_a.get(key), kpi_b.get(key)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                return round(b - a, 2)
            return None

        return {
            "repo_a": {
                "repo_id": repo_id_a,
                "owner": repo_a.owner,
                "name": repo_a.name,
                "kpi": kpi_a,
            },
            "repo_b": {
                "repo_id": repo_id_b,
                "owner": repo_b.owner,
                "name": repo_b.name,
                "kpi": kpi_b,
            },
            "comparison": {
                "open_prs_delta": delta("open_prs"),
                "merge_rate_delta": delta("merge_rate"),
                "avg_cycle_time_delta": delta("avg_cycle_time"),
                "stale_prs_delta": delta("stale_prs"),
            },
        }

    async def build_export_csv(
        self,
        repo_id: int,
        days: Optional[int] = None,
        author: Optional[str] = None,
        state: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one_or_none()
        if not repo:
            raise ValueError("Repository not found")

        kpi = await self.get_kpi_with_duration(repo_id, days, author, state, start_date, end_date)
        contributors_res = await self.get_contributors_filtered(repo_id, limit=50, days=days, author=author, state=state, start_date=start_date, end_date=end_date)
        contributors = contributors_res["data"]
        oldest_res = await self.get_oldest_open_filtered(repo_id, limit=20, days=days, author=author, state=state, start_date=start_date, end_date=end_date)
        oldest = oldest_res["data"]
        stale_res = await self.get_stale_recommendations(repo_id)
        stale = stale_res["data"]
        risks_res = await self.get_pr_risk_panel(repo_id, limit=20)
        risks = risks_res["data"]

        buf = io.StringIO()
        w = csv.writer(buf)

        w.writerow(["GitHub PR Intelligence Report"])
        w.writerow(["Repository", f"{repo.owner}/{repo.name}"])
        w.writerow(["Generated", datetime.now(timezone.utc).isoformat()])
        w.writerow([])

        w.writerow(["KPI Summary"])
        for key, val in kpi.items():
            if not key.endswith("_display"):
                w.writerow([key, val])
        w.writerow([])

        w.writerow(["Contributors"])
        w.writerow(["username", "total_prs", "merged_prs", "merge_rate", "avg_cycle_time"])
        for c in contributors:
            w.writerow([c["username"], c["total_prs"], c["merged_prs"], c["merge_rate"], c["avg_cycle_time"]])
        w.writerow([])

        w.writerow(["Stale PR Alerts"])
        w.writerow(["number", "title", "author", "age_days", "severity", "actions"])
        for s in stale:
            w.writerow([s["number"], s["title"], s["author"], s["age_days"], s["severity"], "; ".join(s["recommended_actions"])])
        w.writerow([])

        w.writerow(["PR Risk Panel"])
        w.writerow(["number", "title", "author", "risk_score", "bottleneck_probability", "predicted_delay_days"])
        for r in risks:
            w.writerow([r["number"], r["title"], r["author"], r["risk_score"], r["bottleneck_probability"], r["predicted_delay_days"]])
        w.writerow([])

        w.writerow(["Oldest Open PRs"])
        w.writerow(["number", "title", "author", "age_days", "review_count"])
        for o in oldest:
            w.writerow([o["number"], o["title"], o["author"], o["age_days"], o["review_count"]])

        return buf.getvalue()
