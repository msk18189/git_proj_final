from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, or_
from database.models import PullRequest, Contributor, Repository, PRReview, PRCommit


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _month_key(dt: datetime) -> str:
    return _ensure_utc(dt).strftime("%Y-%m")


def _month_range(months: int) -> List[str]:
    """Last N calendar months including current, oldest first."""
    now = _ensure_utc(datetime.utcnow())
    year, month = now.year, now.month
    keys: List[str] = []
    for _ in range(months):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(keys))


def _month_range_from_filters(
    months: int,
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
) -> List[str]:
    if start_date_str and end_date_str:
        try:
            start_dt = datetime.fromisoformat(
                start_date_str if len(start_date_str) > 10 else start_date_str + "T00:00:00"
            )
            end_dt = datetime.fromisoformat(
                end_date_str if len(end_date_str) > 10 else end_date_str + "T23:59:59"
            )
            keys: List[str] = []
            y, m = start_dt.year, start_dt.month
            end_ym = (end_dt.year, end_dt.month)
            while (y, m) <= end_ym:
                keys.append(f"{y:04d}-{m:02d}")
                m += 1
                if m > 12:
                    m = 1
                    y += 1
            return keys
        except Exception:
            pass  # fallback to default
    return _month_range(months)


def _format_month_label(ym: str) -> str:
    y, m = ym.split("-")
    return datetime(int(y), int(m), 1).strftime("%b %Y")


def _iso_week_key(dt: datetime) -> Tuple[int, int]:
    iso = _ensure_utc(dt).isocalendar()
    return (iso[0], iso[1])


def _week_label(year: int, week: int) -> str:
    monday = date.fromisocalendar(year, week, 1)
    return monday.strftime("%b %d")


def _week_range(weeks: int) -> List[Tuple[int, int]]:
    """Last N ISO weeks ending this week, oldest first."""
    today = _ensure_utc(datetime.utcnow()).date()
    year, week, _ = today.isocalendar()
    keys: List[Tuple[int, int]] = [(year, week)]
    for _ in range(weeks - 1):
        prev_monday = date.fromisocalendar(year, week, 1) - timedelta(days=7)
        year, week, _ = prev_monday.isocalendar()
        keys.append((year, week))
    return list(reversed(keys))


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def _get_latest_activity_timestamp(self, pr: PullRequest) -> Optional[datetime]:
        timestamps = []
        
        if pr.updated_at:
            timestamps.append(_ensure_utc(pr.updated_at))
        
        result = await self.db.execute(select(func.max(PRReview.submitted_at)).where(PRReview.pr_id == pr.id))
        latest_review = result.scalar()
        if latest_review:
            timestamps.append(_ensure_utc(latest_review))
        
        result = await self.db.execute(select(func.max(PRCommit.committed_at)).where(PRCommit.pr_id == pr.id))
        latest_commit = result.scalar()
        if latest_commit:
            timestamps.append(_ensure_utc(latest_commit))
        
        if pr.created_at:
            timestamps.append(_ensure_utc(pr.created_at))
        
        return max(timestamps) if timestamps else None

    async def _get_inactivity_days(self, pr: PullRequest) -> int:
        latest_activity = await self._get_latest_activity_timestamp(pr)
        if not latest_activity:
            return 0
        now = _ensure_utc(datetime.utcnow())
        return (now - latest_activity).days
    
    async def get_open_pr_count(self, repo_id: int) -> int:
        result = await self.db.execute(select(func.count(PullRequest.id)).where(
            PullRequest.repo_id == repo_id,
            PullRequest.state == "OPEN"
        ))
        return result.scalar() or 0
    
    async def get_stale_pr_count(self, repo_id: int, days: int = 30) -> int:
        result = await self.db.execute(select(PullRequest).where(
            PullRequest.repo_id == repo_id,
            PullRequest.state == "OPEN",
        ))
        open_prs = result.scalars().all()
        
        stale_count = 0
        for pr in open_prs:
            inactivity_days = await self._get_inactivity_days(pr)
            if inactivity_days >= days:
                stale_count += 1
        
        return stale_count
    
    async def get_avg_cycle_time(self, repo_id: int) -> Optional[float]:
        result = await self.db.execute(select(func.avg(PullRequest.cycle_time_days)).where(
            PullRequest.repo_id == repo_id,
            PullRequest.cycle_time_days.isnot(None)
        ))
        val = result.scalar()
        return round(float(val), 2) if val is not None else None
    
    async def get_median_cycle_time(self, repo_id: int) -> Optional[float]:
        result = await self.db.execute(select(PullRequest.cycle_time_days).where(
            PullRequest.repo_id == repo_id,
            PullRequest.cycle_time_days.isnot(None)
        ))
        prs = result.scalars().all()
        
        if not prs:
            return None
        
        values = sorted(prs)
        n = len(values)
        return values[n // 2] if n % 2 == 1 else (values[n // 2 - 1] + values[n // 2]) / 2
    
    async def get_merge_rate(self, repo_id: int) -> float:
        result = await self.db.execute(select(func.count(PullRequest.id)).where(
            PullRequest.repo_id == repo_id,
            PullRequest.state == "MERGED"
        ))
        merged = result.scalar() or 0
        
        result = await self.db.execute(select(func.count(PullRequest.id)).where(
            PullRequest.repo_id == repo_id,
            PullRequest.state.in_(["MERGED", "CLOSED"])
        ))
        closed = result.scalar() or 0
        
        return round((merged / closed * 100) if closed > 0 else 0, 2)
    
    async def get_avg_review_duration(self, repo_id: int) -> Optional[float]:
        result = await self.db.execute(select(func.avg(PullRequest.review_duration_hours)).where(
            PullRequest.repo_id == repo_id,
            PullRequest.review_duration_hours.isnot(None)
        ))
        val = result.scalar()
        return round(float(val) / 24, 2) if val is not None else None
    
    async def get_avg_wait_for_review(self, repo_id: int) -> Optional[float]:
        result = await self.db.execute(select(func.avg(PullRequest.wait_for_review_hours)).where(
            PullRequest.repo_id == repo_id,
            PullRequest.wait_for_review_hours.isnot(None)
        ))
        val = result.scalar()
        return round(float(val) / 24, 2) if val is not None else None
    
    async def get_pr_throughput(self, repo_id: int, weeks: int = 8) -> List[Dict[str, Any]]:
        week_keys = _week_range(weeks)
        counts = {k: 0 for k in week_keys}

        result = await self.db.execute(select(PullRequest).where(
            PullRequest.repo_id == repo_id,
            PullRequest.merged_at.isnot(None),
        ))
        prs = result.scalars().all()

        for pr in prs:
            key = _iso_week_key(pr.merged_at)
            if key in counts:
                counts[key] += 1

        return [
            {"week": _week_label(y, w), "prs": counts[(y, w)]}
            for y, w in week_keys
        ]

    async def get_monthly_pr_flow(self, repo_id: int, months: int = 6) -> List[Dict[str, Any]]:
        month_keys = _month_range(months)
        first_month = month_keys[0]
        last_month = month_keys[-1]

        first_y, first_m = int(first_month[:4]), int(first_month[5:])
        last_y, last_m = int(last_month[:4]), int(last_month[5:])
        range_start = datetime(first_y, first_m, 1, tzinfo=timezone.utc)
        if last_m == 12:
            range_end = datetime(last_y + 1, 1, 1, tzinfo=timezone.utc)
        else:
            range_end = datetime(last_y, last_m + 1, 1, tzinfo=timezone.utc)

        result = await self.db.execute(select(
            PullRequest.created_at,
            PullRequest.merged_at,
            PullRequest.closed_at,
            PullRequest.state,
        ).where(
            PullRequest.repo_id == repo_id,
            or_(
                PullRequest.created_at.between(range_start, range_end),
                PullRequest.merged_at.between(range_start, range_end),
                PullRequest.closed_at.between(range_start, range_end),
            )
        ))
        prs = result.all()

        flow = {
            ym: {"month": _format_month_label(ym), "created": 0, "merged": 0, "closed": 0}
            for ym in month_keys
        }

        for created_at, merged_at, closed_at, state in prs:
            if created_at:
                m = _month_key(created_at)
                if m in flow:
                    flow[m]["created"] += 1

            if merged_at:
                m = _month_key(merged_at)
                if m in flow:
                    flow[m]["merged"] += 1
            elif state and state.upper() == "CLOSED" and closed_at:
                m = _month_key(closed_at)
                if m in flow:
                    flow[m]["closed"] += 1

        result_flow = [flow[ym] for ym in month_keys]

        return result_flow
    
    async def get_oldest_open_prs(self, repo_id: int, limit: int = 10) -> List[Dict]:
        result = await self.db.execute(select(PullRequest).where(
            PullRequest.repo_id == repo_id,
            PullRequest.state == "OPEN"
        ).order_by(PullRequest.created_at.asc()).limit(limit))
        prs = result.scalars().all()
        
        return [
            {
                "number": pr.pr_number,
                "title": pr.title,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
                "age_days": (datetime.utcnow() - pr.created_at).days if pr.created_at else 0,
                "author": pr.author,
                "review_count": pr.review_count
            }
            for pr in prs
        ]
    
    async def get_slowest_merged_prs(self, repo_id: int, limit: int = 10) -> List[Dict]:
        result = await self.db.execute(select(PullRequest).where(
            PullRequest.repo_id == repo_id,
            PullRequest.state == "MERGED",
            PullRequest.cycle_time_days.isnot(None)
        ).order_by(PullRequest.cycle_time_days.desc()).limit(limit))
        prs = result.scalars().all()
        
        return [
            {
                "number": pr.pr_number,
                "title": pr.title,
                "cycle_time_days": pr.cycle_time_days,
                "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                "author": pr.author,
                "review_count": pr.review_count,
                "files_changed": pr.files_changed
            }
            for pr in prs
        ]
    
    async def get_contributor_activity(self, repo_id: int, limit: int = 15) -> List[Dict]:
        result = await self.db.execute(select(PullRequest).where(
            PullRequest.repo_id == repo_id,
        ))
        prs = result.scalars().all()

        now = _ensure_utc(datetime.utcnow())
        stats: Dict[str, Dict[str, Any]] = {}

        for pr in prs:
            if not pr.author:
                continue

            if pr.author not in stats:
                stats[pr.author] = {
                    "username": pr.author,
                    "total_prs": 0,
                    "merged_prs": 0,
                    "open_prs": 0,
                    "cycle_times": [],
                    "wait_hours": [],
                    "stale_pr_count": 0,
                }

            entry = stats[pr.author]
            entry["total_prs"] += 1

            if pr.state == "MERGED":
                entry["merged_prs"] += 1
                if pr.cycle_time_days is not None and pr.cycle_time_days >= 0:
                    entry["cycle_times"].append(pr.cycle_time_days)
            elif pr.state == "OPEN":
                entry["open_prs"] += 1
                if pr.created_at:
                    age_days = (now - _ensure_utc(pr.created_at)).days
                    if age_days > 30:
                        entry["stale_pr_count"] += 1

            if pr.wait_for_review_hours is not None and pr.wait_for_review_hours >= 0:
                entry["wait_hours"].append(pr.wait_for_review_hours)

        result_list = []
        for entry in stats.values():
            total = entry["total_prs"]
            result_list.append({
                "username": entry["username"],
                "total_prs": total,
                "merged_prs": entry["merged_prs"],
                "open_prs": entry["open_prs"],
                "avg_cycle_time": round(
                    sum(entry["cycle_times"]) / len(entry["cycle_times"]), 2
                ) if entry["cycle_times"] else None,
                "avg_wait_for_review": round(
                    (sum(entry["wait_hours"]) / len(entry["wait_hours"])) / 24, 2
                ) if entry["wait_hours"] else None,
                "merge_rate": round((entry["merged_prs"] / total * 100) if total > 0 else 0, 2),
                "stale_pr_count": entry["stale_pr_count"],
            })

        result_list.sort(key=lambda x: x["total_prs"], reverse=True)
        return result_list[:limit]
    
    async def get_median_cycle_time_rounded(self, repo_id: int) -> Optional[float]:
        median = await self.get_median_cycle_time(repo_id)
        return round(median, 1) if median is not None else None
    
    async def get_avg_reviews_per_pr(self, repo_id: int) -> float:
        result = await self.db.execute(select(func.avg(PullRequest.review_count)).where(
            PullRequest.repo_id == repo_id,
            PullRequest.review_count.isnot(None)
        ))
        val = result.scalar()
        return round(float(val or 0), 1)
    
    async def get_kpi_summary(self, repo_id: int) -> Dict[str, Any]:
        return {
            "open_prs": await self.get_open_pr_count(repo_id),
            "stale_prs": await self.get_stale_pr_count(repo_id),
            "avg_cycle_time": await self.get_avg_cycle_time(repo_id),
            "median_cycle_time": await self.get_median_cycle_time_rounded(repo_id),
            "avg_wait_for_review": await self.get_avg_wait_for_review(repo_id),
            "avg_review_duration": await self.get_avg_review_duration(repo_id),
            "merge_rate": await self.get_merge_rate(repo_id),
            "avg_reviews_per_pr": await self.get_avg_reviews_per_pr(repo_id),
        }
