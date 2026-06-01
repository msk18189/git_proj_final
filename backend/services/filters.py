from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import PullRequest


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class PRFilterParams:
    days: Optional[int] = None
    author: Optional[str] = None
    state: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


def get_filtered_prs_query(
    repo_id: int,
    filters: Optional[PRFilterParams] = None,
):
    """Build a select statement for filtered PRs (without executing it)."""
    filters = filters or PRFilterParams()
    stmt = select(PullRequest).where(PullRequest.repo_id == repo_id)

    if filters.state and filters.state.upper() != "ALL":
        if filters.state.upper() == "STALE":
            stmt = stmt.where(PullRequest.state == "OPEN")
            cutoff = datetime.utcnow() - timedelta(days=30)
            stmt = stmt.where(PullRequest.created_at < cutoff)
        else:
            stmt = stmt.where(PullRequest.state == filters.state.upper())
            
    if filters.author and filters.author.lower() != "all":
        stmt = stmt.where(PullRequest.author == filters.author)

    if filters.start_date:
        try:
            start_date_str = filters.start_date
            if len(start_date_str) == 10:
                start_date_str += "T00:00:00"
            start_dt = datetime.fromisoformat(start_date_str)
            stmt = stmt.where(PullRequest.created_at >= start_dt)
        except Exception:
            pass

    if filters.end_date:
        try:
            end_date_str = filters.end_date
            if len(end_date_str) == 10:
                end_date_str += "T23:59:59"
            end_dt = datetime.fromisoformat(end_date_str)
            stmt = stmt.where(PullRequest.created_at <= end_dt)
        except Exception:
            pass

    if not filters.start_date and not filters.end_date and filters.days and filters.days > 0:
        cutoff = datetime.utcnow() - timedelta(days=filters.days)
        stmt = stmt.where(PullRequest.created_at >= cutoff)

    return stmt


async def get_filtered_prs(
    db: AsyncSession,
    repo_id: int,
    filters: Optional[PRFilterParams] = None,
) -> List[PullRequest]:
    stmt = get_filtered_prs_query(repo_id, filters)
    result = await db.execute(stmt)
    return result.scalars().all()


def pr_cycle_hours(pr: PullRequest) -> Optional[float]:
    if pr.merged_at and pr.created_at:
        return (
            ensure_utc(pr.merged_at) - ensure_utc(pr.created_at)
        ).total_seconds() / 3600
    if pr.cycle_time_days is not None:
        return pr.cycle_time_days * 24
    return None


def format_duration(hours: Optional[float]) -> dict:
    """Return display-friendly duration (hours when under 1 day)."""
    if hours is None or hours <= 0:
        return {"value": 0, "unit": "hrs", "raw_hours": 0.0}

    if hours < 24:
        rounded = round(hours, 1)
        if rounded == int(rounded):
            rounded = int(rounded)
        return {"value": rounded, "unit": "hrs", "raw_hours": hours}

    days = round(hours / 24, 1)
    if days == int(days):
        days = int(days)
    return {"value": days, "unit": "days", "raw_hours": hours}
async def list_authors(db: AsyncSession, repo_id: int) -> List[str]:
    stmt = select(PullRequest.author).where(
        PullRequest.repo_id == repo_id, 
        PullRequest.author.isnot(None)
    ).distinct()
    result = await db.execute(stmt)
    rows = result.all()
    return sorted({r[0] for r in rows if r[0]})
