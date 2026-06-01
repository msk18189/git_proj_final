"""
services/module_analytics.py

Analytics queries for all 9 PRISM intelligence modules.
All analytics read from MySQL — never from GitHub API directly.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import json

from sqlalchemy import func, case, and_, desc, asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Repository, PullRequest, PRReview, Issue, Branch, Fork,
    Workflow, WorkflowRun, Discussion, Project, ProjectItem, AnalyticsSnapshot
)

def _now_utc():
    return datetime.now(timezone.utc)


def _cutoff(days: int) -> datetime:
    return _now_utc() - timedelta(days=days)


class IssueAnalytics:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, repo_id: int) -> Dict[str, Any]:
        base = select(Issue).where(Issue.repo_id == repo_id)
        
        result = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(Issue.state == "open").subquery()))
        open_count = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(Issue.state == "closed").subquery()))
        closed_count = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(Issue.is_bug == True).subquery()))
        bug_count = result.scalar() or 0

        stale_cutoff = _cutoff(30)
        result = await self.db.execute(select(func.count()).select_from(base.where(
            Issue.state == "open",
            Issue.created_at < stale_cutoff
        ).subquery()))
        stale_count = result.scalar() or 0

        result = await self.db.execute(
            select(func.avg(Issue.resolution_hours)).where(
                Issue.repo_id == repo_id,
                Issue.resolution_hours.isnot(None),
                Issue.resolution_hours > 0
            )
        )
        avg_resolution = float(result.scalar() or 0.0)

        result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one_or_none()

        return {
            "total_issues": total,
            "open_issues": open_count,
            "closed_issues": closed_count,
            "stale_issues": stale_count,
            "bug_count": bug_count,
            "avg_resolution_hours": round(avg_resolution, 1),
            "avg_resolution_days": round(avg_resolution / 24, 1) if avg_resolution else 0,
            "closure_rate": round((closed_count / total * 100) if total else 0, 1),
            "expected_prs": repo.expected_prs if repo else 0,
            "synced_prs": repo.synced_prs if repo else 0,
            "expected_issues": repo.expected_issues if repo else 0,
            "synced_issues": repo.synced_issues if repo else 0,
            "expected_forks": repo.expected_forks if repo else 0,
            "synced_forks": repo.synced_forks if repo else 0,
            "expected_workflows": repo.expected_workflows if repo else 0,
            "synced_workflows": repo.synced_workflows if repo else 0,
        }

    async def get_issues_list(self, repo_id: int, state: str = "all", page: int = 1,
                        limit: int = 20, label: str = None,
                        search: str = None, sort: str = "created_at", sort_dir: str = "desc") -> Dict[str, Any]:
        query = select(Issue).where(Issue.repo_id == repo_id)
        if state != "all":
            query = query.where(Issue.state == state)
        if label:
            query = query.where(Issue.labels.contains(label))
        if search:
            search_term = f"%{search}%"
            query = query.where(Issue.title.ilike(search_term))

        result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = result.scalar() or 0

        sort_col = getattr(Issue, sort, Issue.created_at)
        if sort_dir == "desc":
            query = query.order_by(desc(sort_col), desc(Issue.id))
        else:
            query = query.order_by(asc(sort_col), asc(Issue.id))

        result = await self.db.execute(query.offset((page - 1) * limit).limit(limit))
        issues = result.scalars().all()

        now = _now_utc()
        data = []
        for iss in issues:
            ca = iss.created_at
            if ca and ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            age_days = (now - ca).days if ca else 0

            try:
                labels = json.loads(iss.labels) if iss.labels else []
            except Exception:
                labels = []

            data.append({
                "number": iss.issue_number,
                "title": iss.title,
                "state": iss.state,
                "state_reason": iss.state_reason,
                "author": iss.author,
                "labels": labels,
                "is_bug": iss.is_bug,
                "age_days": age_days,
                "created_at": iss.created_at.isoformat() if iss.created_at else None,
                "closed_at": iss.closed_at.isoformat() if iss.closed_at else None,
                "comment_count": iss.comment_count,
                "resolution_hours": round(iss.resolution_hours, 1) if iss.resolution_hours else None,
            })

        return {
            "data": data,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": max(1, (total + limit - 1) // limit),
        }

    async def get_resolution_velocity(self, repo_id: int, months: int = 6) -> List[Dict[str, Any]]:
        """Monthly issue opened vs closed trend."""
        cutoff = _cutoff(months * 31)
        result = await self.db.execute(select(Issue).where(
            Issue.repo_id == repo_id,
            Issue.created_at >= cutoff
        ))
        issues = result.scalars().all()

        from collections import defaultdict
        opened: Dict[str, int] = defaultdict(int)
        closed: Dict[str, int] = defaultdict(int)

        for iss in issues:
            if iss.created_at:
                key = iss.created_at.strftime("%Y-%m")
                opened[key] += 1
            if iss.closed_at:
                key = iss.closed_at.strftime("%Y-%m")
                closed[key] += 1

        keys = sorted(set(list(opened.keys()) + list(closed.keys())))
        return [{"month": k, "opened": opened[k], "closed": closed[k]} for k in keys]

    async def get_stale_issues(self, repo_id: int, stale_days: int = 30, page: int = 1, limit: int = 20,
                         search: str = None, sort: str = "created_at", sort_dir: str = "asc") -> Dict[str, Any]:
        cutoff = _cutoff(stale_days)
        query = select(Issue).where(
            Issue.repo_id == repo_id,
            Issue.state == "open",
            Issue.created_at < cutoff
        )
        if search:
            search_term = f"%{search}%"
            query = query.where(Issue.title.ilike(search_term))
            
        sort_col = getattr(Issue, sort, Issue.created_at)
        if sort_dir == "desc":
            query = query.order_by(desc(sort_col), desc(Issue.id))
        else:
            query = query.order_by(asc(sort_col), asc(Issue.id))

        result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = result.scalar() or 0
        
        result = await self.db.execute(query.offset((page - 1) * limit).limit(limit))
        issues = result.scalars().all()
        now = _now_utc()
        data = []
        for iss in issues:
            ca = iss.created_at.replace(tzinfo=timezone.utc) if iss.created_at and iss.created_at.tzinfo is None else iss.created_at
            age = (now - ca).days if ca else 0
            data.append({
                "number": iss.issue_number,
                "title": iss.title,
                "author": iss.author,
                "age_days": age,
                "comment_count": iss.comment_count,
                "created_at": iss.created_at.isoformat() if iss.created_at else None,
            })

        return {"data": data, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}

    async def get_heatmap(self, repo_id: int) -> List[int]:
        now = _now_utc()
        end_date = now
        while end_date.weekday() != 5:
            end_date += timedelta(days=1)
            
        start_date = end_date - timedelta(days=370)
        
        result = await self.db.execute(select(Issue.created_at).where(
            Issue.repo_id == repo_id,
            Issue.created_at >= start_date,
            Issue.created_at <= end_date + timedelta(days=1)
        ))
        issues = result.all()
        
        from collections import defaultdict
        daily_counts = defaultdict(int)
        for (created_at,) in issues:
            if created_at:
                daily_counts[created_at.strftime("%Y-%m-%d")] += 1
                
        heatmap = []
        for i in range(371):
            d = start_date + timedelta(days=i)
            count = daily_counts[d.strftime("%Y-%m-%d")]
            if count == 0: level = 0
            elif count <= 1: level = 1
            elif count <= 3: level = 2
            elif count <= 5: level = 3
            else: level = 4
            heatmap.append(level)
        return heatmap
        
    async def get_priority_distribution(self, repo_id: int) -> List[Dict[str, Any]]:
        query = select(Issue.labels, Issue.comment_count, Issue.is_bug).where(
            Issue.repo_id == repo_id,
            Issue.state == "open"
        )
        result = await self.db.execute(query)
        issues = result.all()

        counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for (labels_json, comment_count, is_bug) in issues:
            try:
                labels = json.loads(labels_json) if labels_json else []
            except Exception:
                labels = []
            labels_lower = [l.lower() for l in labels]
            
            if any(l in labels_lower for l in ["critical", "p0", "priority: critical", "severity: critical"]):
                counts["Critical"] += 1
            elif any(l in labels_lower for l in ["high", "p1", "priority: high", "severity: high", "bug"]):
                counts["High"] += 1
            elif any(l in labels_lower for l in ["medium", "p2", "priority: medium", "severity: medium", "enhancement"]):
                counts["Medium"] += 1
            elif is_bug and (comment_count or 0) > 5:
                counts["Critical"] += 1
            elif is_bug:
                counts["High"] += 1
            elif (comment_count or 0) > 2:
                counts["Medium"] += 1
            else:
                counts["Low"] += 1

        return [
            {"name": "Critical", "value": counts["Critical"], "color": "#ef4444"},
            {"name": "High", "value": counts["High"], "color": "#f97316"},
            {"name": "Medium", "value": counts["Medium"], "color": "#f59e0b"},
            {"name": "Low", "value": counts["Low"], "color": "#10b981"},
        ]

    async def get_issue_heatmap(self, repo_id: int) -> List[Dict[str, Any]]:
        cutoff = _cutoff(371)
        result = await self.db.execute(select(Issue.created_at).where(
            Issue.repo_id == repo_id, 
            Issue.created_at >= cutoff
        ))
        issues = result.all()
        
        from collections import defaultdict
        daily = defaultdict(int)
        for (ca,) in issues:
            if ca:
                ca_utc = ca.replace(tzinfo=timezone.utc) if ca.tzinfo is None else ca
                daily[ca_utc.strftime("%Y-%m-%d")] += 1
                
        now = _now_utc()
        data = []
        for i in range(371, -1, -1):
            dt = now - timedelta(days=i)
            dstr = dt.strftime("%Y-%m-%d")
            data.append({
                "date": dstr,
                "count": daily[dstr]
            })
        return data

# ---------------------------------------------------------------------------
# MODULE 3 — Branch Analytics
# ---------------------------------------------------------------------------

class BranchAnalytics:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, repo_id: int) -> Dict[str, Any]:
        base = select(Branch).where(Branch.repo_id == repo_id)
        
        result = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(Branch.protected == True).subquery()))
        protected_count = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(
            Branch.staleness_days != None,
            Branch.staleness_days <= 30
        ).subquery()))
        active_count = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(
            Branch.staleness_days != None,
            Branch.staleness_days >= 90
        ).subquery()))
        stale_count = result.scalar() or 0
        
        inactive_count = total - active_count - stale_count

        return {
            "total_branches": total,
            "protected_branches": protected_count,
            "active_branches": active_count,     # <= 30 days
            "inactive_branches": inactive_count,  # > 30 and < 90 days (+ NULL)
            "stale_branches": stale_count,        # >= 90 days
        }

    async def get_branches_list(self, repo_id: int, page: int = 1, limit: int = 20,
                          filter_type: str = "all") -> Dict[str, Any]:
        query = select(Branch).where(Branch.repo_id == repo_id)
        if filter_type == "stale":
            query = query.where(Branch.staleness_days >= 90)
        elif filter_type == "protected":
            query = query.where(Branch.protected == True)
        elif filter_type == "active":
            query = query.where(Branch.staleness_days != None, Branch.staleness_days <= 30)
        elif filter_type == "inactive":
            # inactive = not active and not stale: (NULL or > 30) and (< 90 or NULL)
            query = query.where(
                ~(
                    (Branch.staleness_days != None) & (Branch.staleness_days <= 30)
                ),
                ~(
                    (Branch.staleness_days != None) & (Branch.staleness_days >= 90)
                ),
            )

        result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = result.scalar() or 0
        
        result = await self.db.execute(query.order_by(desc(Branch.last_commit_at)).offset((page - 1) * limit).limit(limit))
        branches = result.scalars().all()

        data = [{
            "name": b.name,
            "protected": b.protected,
            "last_commit_sha": b.last_commit_sha,
            "last_commit_author": b.last_commit_author,
            "last_commit_message": (b.last_commit_message or "")[:100],
            "last_commit_at": b.last_commit_at.isoformat() if b.last_commit_at else None,
            "staleness_days": b.staleness_days,
            "status": _branch_health(b.staleness_days),
        } for b in branches]

        return {"data": data, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}


def _branch_health(days: Optional[int]) -> str:
    """Return the mutually exclusive activity status for a branch.

    Active:   staleness_days <= 30
    Inactive: staleness_days  > 30 and < 90  (also used for NULL — conservative default)
    Stale:    staleness_days  >= 90
    """
    if days is None:
        return "inactive"
    if days <= 30:
        return "active"
    if days < 90:
        return "inactive"
    return "stale"


# ---------------------------------------------------------------------------
# MODULE 5 — Fork Analytics
# ---------------------------------------------------------------------------

class ForkAnalytics:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, repo_id: int) -> Dict[str, Any]:
        base = select(Fork).where(Fork.repo_id == repo_id)
        
        result = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(Fork.staleness_days <= 30).subquery()))
        active_count = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(Fork.staleness_days > 90).subquery()))
        stale_count = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(Fork.stars > 0).subquery()))
        starred_forks = result.scalar() or 0
        
        result = await self.db.execute(select(func.avg(Fork.stars)).where(Fork.repo_id == repo_id))
        avg_stars = float(result.scalar() or 0.0)

        result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one_or_none()

        return {
            "total_forks": total,
            "active_forks": active_count,
            "stale_forks": stale_count,
            "starred_forks": starred_forks,
            "avg_fork_stars": round(avg_stars, 1),
            "adoption_rate": round((active_count / total * 100) if total else 0, 1),
            "expected_prs": repo.expected_prs if repo else 0,
            "synced_prs": repo.synced_prs if repo else 0,
            "expected_issues": repo.expected_issues if repo else 0,
            "synced_issues": repo.synced_issues if repo else 0,
            "expected_forks": repo.expected_forks if repo else 0,
            "synced_forks": repo.synced_forks if repo else 0,
            "expected_workflows": repo.expected_workflows if repo else 0,
            "synced_workflows": repo.synced_workflows if repo else 0,
        }

    async def get_forks_list(self, repo_id: int, page: int = 1, limit: int = 20,
                       filter_type: str = "all") -> Dict[str, Any]:
        query = select(Fork).where(Fork.repo_id == repo_id)
        if filter_type == "active":
            query = query.where(Fork.staleness_days <= 30)
        elif filter_type == "stale":
            query = query.where(Fork.staleness_days > 90)

        result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = result.scalar() or 0
        
        result = await self.db.execute(query.order_by(desc(Fork.pushed_at)).offset((page - 1) * limit).limit(limit))
        forks = result.scalars().all()

        data = [{
            "full_name": f.full_name,
            "owner": f.owner,
            "stars": f.stars,
            "forks": f.forks,
            "language": f.language,
            "description": (f.description or "")[:200],
            "pushed_at": f.pushed_at.isoformat() if f.pushed_at else None,
            "staleness_days": f.staleness_days,
            "activity": "active" if (f.staleness_days or 999) <= 30 else "inactive",
        } for f in forks]

        return {"data": data, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}

    async def get_growth_trend(self, repo_id: int, months: int = 6) -> List[Dict[str, Any]]:
        cutoff = _cutoff(months * 31)
        result = await self.db.execute(select(Fork).where(
            Fork.repo_id == repo_id,
            Fork.created_at >= cutoff
        ))
        forks = result.scalars().all()

        from collections import defaultdict
        monthly: Dict[str, int] = defaultdict(int)
        for f in forks:
            if f.created_at:
                monthly[f.created_at.strftime("%Y-%m")] += 1

        return [{"month": k, "new_forks": v} for k, v in sorted(monthly.items())]


# ---------------------------------------------------------------------------
# MODULE 8 — CI/CD Analytics
# ---------------------------------------------------------------------------

class CICDAnalytics:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, repo_id: int) -> Dict[str, Any]:
        base = select(WorkflowRun).where(WorkflowRun.repo_id == repo_id)
        
        result = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total_runs = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(WorkflowRun.conclusion == "success").subquery()))
        successful = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(WorkflowRun.conclusion == "failure").subquery()))
        failed = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(WorkflowRun.conclusion == "cancelled").subquery()))
        cancelled = result.scalar() or 0

        result = await self.db.execute(
            select(func.avg(WorkflowRun.duration_seconds)).where(
                WorkflowRun.repo_id == repo_id,
                WorkflowRun.duration_seconds.isnot(None),
                WorkflowRun.conclusion == "success"
            )
        )
        avg_duration = float(result.scalar() or 0.0)

        success_rate = round((successful / total_runs * 100) if total_runs else 0, 1)

        # Flaky workflow detection: workflows with >20% failure rate
        result = await self.db.execute(select(
            WorkflowRun.workflow_id,
            func.count(WorkflowRun.id).label("total"),
            func.sum(case((WorkflowRun.conclusion == "failure", 1), else_=0)).label("failures")
        ).where(WorkflowRun.repo_id == repo_id).group_by(WorkflowRun.workflow_id))
        workflow_stats = result.all()

        flaky_workflows = sum(
            1 for ws in workflow_stats
            if ws.total > 5 and (ws.failures / ws.total) > 0.2
        )

        result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one_or_none()

        return {
            "total_runs": total_runs,
            "successful_runs": successful,
            "failed_runs": failed,
            "cancelled_runs": cancelled,
            "success_rate": success_rate,
            "avg_duration_seconds": int(avg_duration),
            "avg_duration_minutes": round(avg_duration / 60, 1) if avg_duration else 0,
            "flaky_workflows": flaky_workflows,
            "expected_prs": repo.expected_prs if repo else 0,
            "synced_prs": repo.synced_prs if repo else 0,
            "expected_issues": repo.expected_issues if repo else 0,
            "synced_issues": repo.synced_issues if repo else 0,
            "expected_forks": repo.expected_forks if repo else 0,
            "synced_forks": repo.synced_forks if repo else 0,
            "expected_workflows": repo.expected_workflows if repo else 0,
            "synced_workflows": repo.synced_workflows if repo else 0,
        }

    async def get_runs_list(self, repo_id: int, page: int = 1, limit: int = 20,
                      conclusion: str = None, branch: str = None) -> Dict[str, Any]:
        query = select(WorkflowRun).where(WorkflowRun.repo_id == repo_id)
        if conclusion:
            query = query.where(WorkflowRun.conclusion == conclusion)
        if branch:
            query = query.where(WorkflowRun.head_branch == branch)

        result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = result.scalar() or 0
        
        result = await self.db.execute(query.order_by(desc(WorkflowRun.created_at)).offset((page - 1) * limit).limit(limit))
        runs = result.scalars().all()

        data = [{
            "id": r.github_run_id,
            "name": r.name,
            "branch": r.head_branch,
            "event": r.event,
            "status": r.status,
            "conclusion": r.conclusion,
            "actor": r.actor,
            "duration_seconds": r.duration_seconds,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in runs]

        return {"data": data, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}

    async def get_success_trend(self, repo_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Daily success/failure trend for the last N days."""
        cutoff = _cutoff(days)
        result = await self.db.execute(select(WorkflowRun).where(
            WorkflowRun.repo_id == repo_id,
            WorkflowRun.created_at >= cutoff,
            WorkflowRun.conclusion.isnot(None)
        ))
        runs = result.scalars().all()

        from collections import defaultdict
        daily: Dict[str, Dict[str, int]] = defaultdict(lambda: {"success": 0, "failure": 0, "other": 0})
        for r in runs:
            if r.created_at:
                key = r.created_at.strftime("%Y-%m-%d")
                if r.conclusion == "success":
                    daily[key]["success"] += 1
                elif r.conclusion == "failure":
                    daily[key]["failure"] += 1
                else:
                    daily[key]["other"] += 1

        return [{"date": k, **v} for k, v in sorted(daily.items())]

    async def get_workflow_breakdown(self, repo_id: int) -> List[Dict[str, Any]]:
        """Per-workflow success/failure breakdown."""
        result = await self.db.execute(select(
            Workflow.name,
            func.count(WorkflowRun.id).label("total"),
            func.sum(case((WorkflowRun.conclusion == "success", 1), else_=0)).label("success"),
            func.sum(case((WorkflowRun.conclusion == "failure", 1), else_=0)).label("failure"),
            func.avg(WorkflowRun.duration_seconds).label("avg_duration"),
        ).join(WorkflowRun, WorkflowRun.workflow_id == Workflow.id, isouter=True)\
         .where(Workflow.repo_id == repo_id)\
         .group_by(Workflow.id, Workflow.name))
        stats = result.all()

        result_list = []
        for s in stats:
            total = s.total or 0
            success = int(s.success or 0)
            failure = int(s.failure or 0)
            result_list.append({
                "name": s.name,
                "total_runs": total,
                "success": success,
                "failure": failure,
                "success_rate": round((success / total * 100) if total else 0, 1),
                "avg_duration_minutes": round(float(s.avg_duration or 0) / 60, 1),
                "is_flaky": total > 5 and failure / total > 0.2 if total else False,
            })

        return sorted(result_list, key=lambda x: x["total_runs"], reverse=True)


# ---------------------------------------------------------------------------
# MODULE 6 — Discussion Analytics
# ---------------------------------------------------------------------------

class DiscussionAnalytics:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, repo_id: int) -> Dict[str, Any]:
        base = select(Discussion).where(Discussion.repo_id == repo_id)
        
        result = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(Discussion.state == "OPEN").subquery()))
        open_count = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(Discussion.answer_chosen == True).subquery()))
        answered_count = result.scalar() or 0
        
        result = await self.db.execute(select(func.avg(Discussion.comment_count)).where(Discussion.repo_id == repo_id))
        avg_comments = float(result.scalar() or 0.0)
        
        result = await self.db.execute(select(func.avg(Discussion.reaction_count)).where(Discussion.repo_id == repo_id))
        avg_reactions = float(result.scalar() or 0.0)

        return {
            "total_discussions": total,
            "open_discussions": open_count,
            "answered_discussions": answered_count,
            "answer_rate": round((answered_count / total * 100) if total else 0, 1),
            "avg_comments": round(avg_comments, 1),
            "avg_reactions": round(avg_reactions, 1),
        }

    async def get_discussions_list(self, repo_id: int, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        query = select(Discussion).where(Discussion.repo_id == repo_id)
        result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = result.scalar() or 0
        
        result = await self.db.execute(query.order_by(desc(Discussion.created_at)).offset((page - 1) * limit).limit(limit))
        items = result.scalars().all()

        data = [{
            "number": d.discussion_number,
            "title": d.title,
            "category": d.category,
            "author": d.author,
            "state": d.state,
            "answer_chosen": d.answer_chosen,
            "comment_count": d.comment_count,
            "reaction_count": d.reaction_count,
            "participant_count": d.participant_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        } for d in items]

        return {"data": data, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}

    async def get_activity_timeline(self, repo_id: int) -> Dict[str, Any]:
        """Get discussion activity over time (monthly distribution)."""
        from datetime import datetime, timedelta
        
        result = await self.db.execute(select(Discussion).where(
            Discussion.repo_id == repo_id,
            Discussion.created_at != None
        ).order_by(Discussion.created_at))
        discussions = result.scalars().all()
        
        if not discussions:
            return {"timeline": []}
        
        # Group by month
        activity_by_month = {}
        for disc in discussions:
            month_key = disc.created_at.strftime('%b %y')
            activity_by_month[month_key] = activity_by_month.get(month_key, 0) + 1
        
        # Sort chronologically and format
        from datetime import datetime as dt
        sorted_months = sorted(activity_by_month.items(), 
                              key=lambda x: dt.strptime(x[0], '%b %y'))
        
        timeline = [
            {"date": month, "activity": count}
            for month, count in sorted_months
        ]
        
        return {"timeline": timeline}


# ---------------------------------------------------------------------------
# MODULE 7 — Project Analytics
# ---------------------------------------------------------------------------

class ProjectAnalytics:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, repo_id: int) -> Dict[str, Any]:
        base = select(Project).where(Project.repo_id == repo_id)
        
        result = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total = result.scalar() or 0
        
        result = await self.db.execute(select(func.count()).select_from(base.where(Project.state == "open").subquery()))
        open_count = result.scalar() or 0
        
        # Completion Rate
        # Sum of items_count vs sum of closed_items across all projects in the repo
        total_items_res = await self.db.execute(select(func.sum(Project.items_count)).where(Project.repo_id == repo_id))
        total_items = int(total_items_res.scalar() or 0)
        
        closed_items_res = await self.db.execute(select(func.sum(Project.closed_items)).where(Project.repo_id == repo_id))
        closed_items = int(closed_items_res.scalar() or 0)
        
        completion_rate = round((closed_items / total_items * 100) if total_items > 0 else 0.0, 1)
        
        # Item Counts by type
        item_types_res = await self.db.execute(
            select(ProjectItem.content_type, func.count(ProjectItem.id))
            .where(ProjectItem.repo_id == repo_id)
            .group_by(ProjectItem.content_type)
        )
        item_counts = {str(row[0]): int(row[1]) for row in item_types_res.all() if row[0] is not None}
        
        # Status Distribution
        status_dist_res = await self.db.execute(
            select(ProjectItem.status, func.count(ProjectItem.id))
            .where(ProjectItem.repo_id == repo_id)
            .group_by(ProjectItem.status)
        )
        status_distribution = {str(row[0] or "No Status"): int(row[1]) for row in status_dist_res.all()}
        
        return {
            "total_projects": total,
            "open_projects": open_count,
            "closed_projects": total - open_count,
            "active_projects": open_count,
            "completion_rate": completion_rate,
            "total_items": total_items,
            "item_counts": item_counts,
            "status_distribution": status_distribution
        }

    async def get_projects_list(self, repo_id: int, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        query = select(Project).where(Project.repo_id == repo_id)
        
        result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = result.scalar() or 0
        
        result = await self.db.execute(query.order_by(desc(Project.updated_at)).offset((page - 1) * limit).limit(limit))
        items = result.scalars().all()

        data = [{
            "number": p.number,
            "name": p.name,
            "state": p.state,
            "creator": p.creator,
            "project_type": p.project_type,
            "items_count": p.items_count,
            "open_items": p.open_items,
            "closed_items": p.closed_items,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        } for p in items]

        return {"data": data, "total": total, "page": page, "limit": limit, "pages": max(1, (total + limit - 1) // limit)}


# ---------------------------------------------------------------------------
# MODULE 9 — Visibility & Repository Health
# ---------------------------------------------------------------------------

class RepoHealthAnalytics:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_health_score(self, repo_id: int) -> Dict[str, Any]:
        """Compute an aggregate repository health score (0-100) across all modules."""
        result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one_or_none()
        
        if not repo:
            return {"score": 0, "components": {}}

        scores = {}

        # PR health (20 pts)
        total_prs = await db_count_filter(self.db, PullRequest, PullRequest.repo_id == repo_id)
        if total_prs > 0:
            open_prs = await db_count_filter(self.db, PullRequest, PullRequest.repo_id == repo_id, PullRequest.state == "OPEN")
            stale_cutoff = _cutoff(30)
            stale_prs = await db_count_filter(self.db, PullRequest, PullRequest.repo_id == repo_id,
                                         PullRequest.state == "OPEN", PullRequest.created_at < stale_cutoff)
            stale_rate = stale_prs / max(open_prs, 1)
            pr_score = max(0, 20 - int(stale_rate * 20))
        else:
            pr_score = 0  # No PR data yet — do not award neutral points
        scores["pull_requests"] = pr_score

        # CI health (25 pts)
        total_runs = await db_count_filter(self.db, WorkflowRun, WorkflowRun.repo_id == repo_id)
        if total_runs > 0:
            recent_cutoff = _cutoff(14)
            recent_runs = await db_count_filter(self.db, WorkflowRun, WorkflowRun.repo_id == repo_id,
                                           WorkflowRun.created_at >= recent_cutoff)
            successful = await db_count_filter(self.db, WorkflowRun, WorkflowRun.repo_id == repo_id,
                                          WorkflowRun.created_at >= recent_cutoff,
                                          WorkflowRun.conclusion == "success")
            success_rate = successful / max(recent_runs, 1)
            ci_score = int(success_rate * 25)
        else:
            ci_score = 0  # No CI data yet — do not award neutral points
        scores["ci_cd"] = ci_score

        # Branch health (15 pts)
        total_branches = await db_count_filter(self.db, Branch, Branch.repo_id == repo_id)
        if total_branches > 0:
            stale_branches = await db_count_filter(self.db, Branch, Branch.repo_id == repo_id, Branch.staleness_days >= 90)
            stale_rate = stale_branches / total_branches
            branch_score = max(0, 15 - int(stale_rate * 15))
        else:
            branch_score = 0  # No branch data yet
        scores["branches"] = branch_score

        # Issue health (20 pts)
        total_issues = await db_count_filter(self.db, Issue, Issue.repo_id == repo_id)
        if total_issues > 0:
            stale_issues = await db_count_filter(self.db, Issue, Issue.repo_id == repo_id,
                                            Issue.state == "open", Issue.created_at < _cutoff(60))
            open_issues = await db_count_filter(self.db, Issue, Issue.repo_id == repo_id, Issue.state == "open")
            stale_rate = stale_issues / max(open_issues, 1)
            issue_score = max(0, 20 - int(stale_rate * 20))
        else:
            issue_score = 0  # No issue data yet
        scores["issues"] = issue_score

        # Community health: discussions + forks (10 pts)
        has_discussions = (await db_count_filter(self.db, Discussion, Discussion.repo_id == repo_id)) > 0
        has_forks = (await db_count_filter(self.db, Fork, Fork.repo_id == repo_id)) > 0
        community_score = (5 if has_discussions else 0) + (5 if has_forks else 0)
        scores["community"] = community_score

        # Visibility (10 pts)
        visibility = repo.visibility or "public"
        scores["visibility"] = 10 if visibility == "public" else 5

        total_score = sum(scores.values())
        grade = _score_grade(total_score)

        # Expose which modules had real data so the frontend can mark incomplete modules
        data_available = {
            "pull_requests": total_prs > 0,
            "ci_cd": total_runs > 0,
            "branches": total_branches > 0,
            "issues": total_issues > 0,
            "community": has_discussions or has_forks,
            "visibility": True,
        }

        return {
            "score": total_score,
            "max_score": 100,
            "grade": grade,
            "components": scores,
            "data_available": data_available,
            "visibility": repo.visibility,
            "sync_status": repo.sync_status,
            "last_synced": repo.last_synced_at.isoformat() if repo.last_synced_at else None,
        }


async def db_count_filter(db: AsyncSession, model, *conditions):
    q = select(func.count(model.id))
    for cond in conditions:
        q = q.where(cond)
    result = await db.execute(q)
    return result.scalar() or 0


def _score_grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"
