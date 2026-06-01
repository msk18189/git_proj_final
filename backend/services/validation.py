"""
services/validation.py

PRISM Enterprise System — Integrity Verification & Health Diagnostics Service.
Implements runtime validation checks for all 12 modules.
Checks for:
- Orphan records
- Duplicate rows
- Empty synced objects
- Invalid repo mappings
- Incorrect counts (Repository totals vs DB counts)
- Tri-count comparison (GitHub vs Dashboard vs DB)
- Ingestion/sync errors
- REST Endpoint responsiveness
"""
import sys
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any
import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    Repository, PullRequest, PRReview, PRFile, PRCommit,
    Issue, IssueComment, Branch, Fork, Workflow, WorkflowRun,
    WorkflowJob, Discussion, DiscussionComment, Project, ProjectItem,
    Contributor
)

from services.extended_analytics import ExtendedAnalytics
from services.module_analytics import (
    IssueAnalytics, BranchAnalytics, ForkAnalytics,
    CICDAnalytics, DiscussionAnalytics, ProjectAnalytics, RepoHealthAnalytics
)


class SystemIntegrityValidator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_all(self, repo_id: int = None) -> Dict[str, Any]:
        """Run all data integrity checks and return a unified report."""
        print("[Validation] Running full system integrity validation suite...")
        
        orphans = await self.validate_orphan_records()
        duplicates = await self.validate_duplicate_rows()
        empty_objects = await self.validate_empty_synced_objects()
        repo_mappings = await self.validate_repo_mappings()
        count_consistency = await self.validate_counts_consistency(repo_id)
        failed_syncs = await self.validate_failed_syncs()
        
        tri_compare = {}
        if repo_id:
            tri_compare = await self.compare_tri_counts(repo_id)
        else:
            result = await self.db.execute(select(Repository))
            first_repo = result.scalars().first()
            if first_repo:
                tri_compare = await self.compare_tri_counts(first_repo.id)

        total_orphans = sum(orphans.values())
        total_duplicates = sum(duplicates.values())
        total_empty = sum(empty_objects.values())
        total_invalid_mappings = sum(repo_mappings.values())
        
        print(f"[Validation] Integrity Report Summary:")
        print(f"  * Orphan Records: {total_orphans}")
        print(f"  * Duplicate Rows: {total_duplicates}")
        print(f"  * Empty Objects: {total_empty}")
        print(f"  * Invalid Repo Mappings: {total_invalid_mappings}")
        print(f"  * Failed Sync Repos: {failed_syncs['failed_repos_count']}")

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "healthy" if (total_orphans + total_duplicates + total_empty + total_invalid_mappings + failed_syncs["failed_repos_count"] == 0) else "warnings",
            "orphans": orphans,
            "duplicates": duplicates,
            "empty_objects": empty_objects,
            "repo_mappings": repo_mappings,
            "count_consistency": count_consistency,
            "failed_syncs": failed_syncs,
            "tri_counts_comparison": tri_compare
        }

    async def validate_orphan_records(self) -> Dict[str, int]:
        report = {}
        
        def _q(model, col, parent_model, parent_col):
            return select(func.count(model.id)).where(~col.in_(select(parent_col)))

        res = await self.db.execute(_q(PRReview, PRReview.pr_id, PullRequest, PullRequest.id))
        report["pr_reviews"] = res.scalar() or 0
        
        res = await self.db.execute(_q(PRFile, PRFile.pr_id, PullRequest, PullRequest.id))
        report["pr_files"] = res.scalar() or 0
        
        res = await self.db.execute(_q(PRCommit, PRCommit.pr_id, PullRequest, PullRequest.id))
        report["pr_commits"] = res.scalar() or 0
        
        res = await self.db.execute(_q(IssueComment, IssueComment.issue_id, Issue, Issue.id))
        report["issue_comments"] = res.scalar() or 0
        
        res = await self.db.execute(_q(DiscussionComment, DiscussionComment.discussion_id, Discussion, Discussion.id))
        report["discussion_comments"] = res.scalar() or 0
        
        res = await self.db.execute(_q(ProjectItem, ProjectItem.project_id, Project, Project.id))
        report["project_items"] = res.scalar() or 0
        
        res = await self.db.execute(_q(WorkflowRun, WorkflowRun.workflow_id, Workflow, Workflow.id))
        report["workflow_runs"] = res.scalar() or 0
        
        res = await self.db.execute(_q(WorkflowJob, WorkflowJob.run_id, WorkflowRun, WorkflowRun.id))
        report["workflow_jobs"] = res.scalar() or 0
        
        return report

    async def validate_duplicate_rows(self) -> Dict[str, int]:
        report = {}
        
        res = await self.db.execute(select(func.count()).select_from(select(Repository.full_name).group_by(Repository.full_name).having(func.count(Repository.id) > 1).subquery()))
        report["repositories"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count()).select_from(select(PullRequest.repo_id, PullRequest.pr_number).group_by(PullRequest.repo_id, PullRequest.pr_number).having(func.count(PullRequest.id) > 1).subquery()))
        report["pull_requests"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count()).select_from(select(Issue.repo_id, Issue.issue_number).group_by(Issue.repo_id, Issue.issue_number).having(func.count(Issue.id) > 1).subquery()))
        report["issues"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count()).select_from(select(Branch.repo_id, Branch.name).group_by(Branch.repo_id, Branch.name).having(func.count(Branch.id) > 1).subquery()))
        report["branches"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count()).select_from(select(Fork.repo_id, Fork.github_id).group_by(Fork.repo_id, Fork.github_id).having(func.count(Fork.id) > 1).subquery()))
        report["forks"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count()).select_from(select(Discussion.repo_id, Discussion.discussion_number).group_by(Discussion.repo_id, Discussion.discussion_number).having(func.count(Discussion.id) > 1).subquery()))
        report["discussions"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count()).select_from(select(Project.repo_id, Project.github_node_id).group_by(Project.repo_id, Project.github_node_id).having(func.count(Project.id) > 1).subquery()))
        report["projects"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count()).select_from(select(Workflow.repo_id, Workflow.path).group_by(Workflow.repo_id, Workflow.path).having(func.count(Workflow.id) > 1).subquery()))
        report["workflows"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count()).select_from(select(WorkflowRun.repo_id, WorkflowRun.github_run_id).group_by(WorkflowRun.repo_id, WorkflowRun.github_run_id).having(func.count(WorkflowRun.id) > 1).subquery()))
        report["workflow_runs"] = res.scalar() or 0

        res = await self.db.execute(select(func.count()).select_from(
            select(Contributor.repo_id, Contributor.github_user_id)
            .where(Contributor.github_user_id.isnot(None))
            .group_by(Contributor.repo_id, Contributor.github_user_id)
            .having(func.count(Contributor.id) > 1)
            .subquery()
        ))
        report["contributors_by_github_user_id"] = res.scalar() or 0

        # 2. By username
        res = await self.db.execute(select(func.count()).select_from(
            select(Contributor.repo_id, Contributor.username)
            .group_by(Contributor.repo_id, Contributor.username)
            .having(func.count(Contributor.id) > 1)
            .subquery()
        ))
        report["contributors_by_username"] = res.scalar() or 0
        
        return report

    async def validate_empty_synced_objects(self) -> Dict[str, int]:
        report = {}
        
        res = await self.db.execute(select(func.count(Repository.id)).where(or_(Repository.name == None, Repository.name == "", Repository.owner == None, Repository.owner == "")))
        report["repositories_empty_name_or_owner"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count(PullRequest.id)).where(or_(PullRequest.title == None, PullRequest.title == "")))
        report["pull_requests_empty_title"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count(Issue.id)).where(or_(Issue.title == None, Issue.title == "")))
        report["issues_empty_title"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count(Branch.id)).where(or_(Branch.name == None, Branch.name == "")))
        report["branches_empty_name"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count(Fork.id)).where(or_(Fork.owner == None, Fork.owner == "", Fork.name == None, Fork.name == "")))
        report["forks_empty_owner_or_name"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count(Workflow.id)).where(or_(Workflow.name == None, Workflow.name == "", Workflow.path == None, Workflow.path == "")))
        report["workflows_empty_name_or_path"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count(WorkflowRun.id)).where(or_(WorkflowRun.status == None, WorkflowRun.status == "")))
        report["workflow_runs_empty_status"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count(Discussion.id)).where(or_(Discussion.title == None, Discussion.title == "")))
        report["discussions_empty_title"] = res.scalar() or 0
        
        res = await self.db.execute(select(func.count(Project.id)).where(or_(Project.name == None, Project.name == "")))
        report["projects_empty_name"] = res.scalar() or 0
        
        return report

    async def validate_repo_mappings(self) -> Dict[str, int]:
        report = {}
        valid_repo_ids = select(Repository.id)
        
        def _q(model):
            return select(func.count(model.id)).where(~model.repo_id.in_(valid_repo_ids))

        res = await self.db.execute(_q(PullRequest))
        report["orphaned_repo_id_pull_requests"] = res.scalar() or 0
        res = await self.db.execute(_q(Issue))
        report["orphaned_repo_id_issues"] = res.scalar() or 0
        res = await self.db.execute(_q(Branch))
        report["orphaned_repo_id_branches"] = res.scalar() or 0
        res = await self.db.execute(_q(Fork))
        report["orphaned_repo_id_forks"] = res.scalar() or 0
        res = await self.db.execute(_q(Discussion))
        report["orphaned_repo_id_discussions"] = res.scalar() or 0
        res = await self.db.execute(_q(Project))
        report["orphaned_repo_id_projects"] = res.scalar() or 0
        res = await self.db.execute(_q(Workflow))
        report["orphaned_repo_id_workflows"] = res.scalar() or 0
        res = await self.db.execute(_q(Contributor))
        report["orphaned_repo_id_contributors"] = res.scalar() or 0

        def _q_join(model):
            return select(func.count(model.id)).join(Repository, model.repo_id == Repository.id).where(
                or_(model.repo_owner != Repository.owner, model.repo_name != Repository.name)
            )

        res = await self.db.execute(_q_join(PullRequest))
        report["inconsistent_owner_or_name_pull_requests"] = res.scalar() or 0
        res = await self.db.execute(_q_join(Issue))
        report["inconsistent_owner_or_name_issues"] = res.scalar() or 0
        res = await self.db.execute(_q_join(Branch))
        report["inconsistent_owner_or_name_branches"] = res.scalar() or 0
        res = await self.db.execute(_q_join(Discussion))
        report["inconsistent_owner_or_name_discussions"] = res.scalar() or 0

        return report

    async def validate_counts_consistency(self, specific_repo_id: int = None) -> List[Dict[str, Any]]:
        repos_query = select(Repository)
        if specific_repo_id:
            repos_query = repos_query.where(Repository.id == specific_repo_id)
            
        result = await self.db.execute(repos_query)
        repos = result.scalars().all()
        discrepancies = []
        
        for r in repos:
            res = await self.db.execute(select(func.count(PullRequest.id)).where(PullRequest.repo_id == r.id))
            actual_prs = res.scalar() or 0
            res = await self.db.execute(select(func.count(Issue.id)).where(Issue.repo_id == r.id))
            actual_issues = res.scalar() or 0
            res = await self.db.execute(select(func.count(Branch.id)).where(Branch.repo_id == r.id))
            actual_branches = res.scalar() or 0
            res = await self.db.execute(select(func.count(Fork.id)).where(Fork.repo_id == r.id))
            actual_forks = res.scalar() or 0
            res = await self.db.execute(select(func.count(Workflow.id)).where(Workflow.repo_id == r.id))
            actual_workflows = res.scalar() or 0
            res = await self.db.execute(select(func.count(WorkflowRun.id)).where(WorkflowRun.repo_id == r.id))
            actual_runs = res.scalar() or 0
            res = await self.db.execute(select(func.count(Discussion.id)).where(Discussion.repo_id == r.id))
            actual_discussions = res.scalar() or 0
            res = await self.db.execute(select(func.count(Project.id)).where(Project.repo_id == r.id))
            actual_projects = res.scalar() or 0
            
            repo_total_projects = getattr(r, "total_projects", 0) or 0
            
            repo_disc = {}
            if r.total_prs != actual_prs:
                repo_disc["pull_requests"] = {"expected_in_repo": r.total_prs, "actual_db_count": actual_prs}
            if r.total_issues != actual_issues:
                repo_disc["issues"] = {"expected_in_repo": r.total_issues, "actual_db_count": actual_issues}
            if r.total_branches != actual_branches:
                repo_disc["branches"] = {"expected_in_repo": r.total_branches, "actual_db_count": actual_branches}
            if r.total_forks != actual_forks:
                repo_disc["forks"] = {"expected_in_repo": r.total_forks, "actual_db_count": actual_forks}
            if r.total_workflow_runs != actual_runs:
                repo_disc["workflow_runs"] = {"expected_in_repo": r.total_workflow_runs, "actual_db_count": actual_runs}
            if r.total_discussions != actual_discussions:
                repo_disc["discussions"] = {"expected_in_repo": r.total_discussions, "actual_db_count": actual_discussions}
            if repo_total_projects != actual_projects:
                repo_disc["projects"] = {"expected_in_repo": repo_total_projects, "actual_db_count": actual_projects}

            if repo_disc:
                discrepancies.append({
                    "repo_id": r.id,
                    "repo_name": r.full_name,
                    "mismatches": repo_disc
                })
                
        return discrepancies

    async def compare_tri_counts(self, repo_id: int) -> Dict[str, Any]:
        result = await self.db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one_or_none()
        if not repo:
            return {}

        gh_counts = {
            "pull_requests": repo.total_prs or 0,
            "issues": repo.total_issues or 0,
            "branches": repo.total_branches or 0,
            "forks": repo.total_forks or 0,
            "workflow_runs": repo.total_workflow_runs or 0,
            "discussions": repo.total_discussions or 0,
            "projects": getattr(repo, "total_projects", 0) or 0
        }

        async def _count(model):
            res = await self.db.execute(select(func.count(model.id)).where(model.repo_id == repo_id))
            return res.scalar() or 0

        db_counts = {
            "pull_requests": await _count(PullRequest),
            "issues": await _count(Issue),
            "branches": await _count(Branch),
            "forks": await _count(Fork),
            "workflow_runs": await _count(WorkflowRun),
            "discussions": await _count(Discussion),
            "projects": await _count(Project)
        }

        dash_counts = {}
        try:
            kpi = await ExtendedAnalytics(self.db).get_kpi_with_duration(repo_id)
            dash_counts["pull_requests"] = kpi.get("total_prs", 0)
        except Exception:
            dash_counts["pull_requests"] = 0

        try:
            iss_summary = await IssueAnalytics(self.db).get_summary(repo_id)
            dash_counts["issues"] = iss_summary.get("total_issues", 0)
        except Exception:
            dash_counts["issues"] = 0

        try:
            br_summary = await BranchAnalytics(self.db).get_summary(repo_id)
            dash_counts["branches"] = br_summary.get("total_branches", 0)
        except Exception:
            dash_counts["branches"] = 0

        try:
            fork_summary = await ForkAnalytics(self.db).get_summary(repo_id)
            dash_counts["forks"] = fork_summary.get("total_forks", 0)
        except Exception:
            dash_counts["forks"] = 0

        try:
            cicd_summary = await CICDAnalytics(self.db).get_summary(repo_id)
            dash_counts["workflow_runs"] = cicd_summary.get("total_runs", 0)
        except Exception:
            dash_counts["workflow_runs"] = 0

        try:
            disc_summary = await DiscussionAnalytics(self.db).get_summary(repo_id)
            dash_counts["discussions"] = disc_summary.get("total_discussions", 0)
        except Exception:
            dash_counts["discussions"] = 0

        try:
            proj_summary = await ProjectAnalytics(self.db).get_summary(repo_id)
            dash_counts["projects"] = proj_summary.get("total_projects", 0)
        except Exception:
            dash_counts["projects"] = 0

        comparison = {}
        for key in gh_counts:
            gh_val = gh_counts[key]
            db_val = db_counts[key]
            dash_val = dash_counts[key]
            consistent = (gh_val == db_val == dash_val)
            comparison[key] = {
                "github_count": gh_val,
                "db_count": db_val,
                "dashboard_count": dash_val,
                "consistent": consistent
            }

        return {
            "repo_id": repo_id,
            "repo_name": repo.full_name,
            "comparison": comparison
        }

    async def validate_failed_syncs(self) -> Dict[str, Any]:
        result = await self.db.execute(select(Repository).where(
            or_(Repository.sync_status == "FAILED", Repository.error_message.isnot(None), Repository.sync_error.isnot(None))
        ))
        failed_repos = result.scalars().all()
        
        details = []
        for r in failed_repos:
            details.append({
                "repo_id": r.id,
                "repo_name": r.full_name,
                "sync_status": r.sync_status,
                "error_message": r.error_message or r.sync_error
            })
            
        return {
            "failed_repos_count": len(failed_repos),
            "failed_repositories": details
        }


async def test_rest_endpoints_async(repo_id: int) -> Dict[str, Any]:
    """Dynamically make calls to core REST APIs locally to check endpoint integrity."""
    from main import app
    
    routes = {
        "repositories": "/api/repositories",
        "sync_status": f"/api/sync-status/{repo_id}",
        "kpi": f"/api/kpi/{repo_id}",
        "issues_analytics": f"/api/issues/analytics/{repo_id}",
        "branches_analytics": f"/api/branches/analytics/{repo_id}",
        "forks_analytics": f"/api/forks/analytics/{repo_id}",
        "cicd_analytics": f"/api/cicd/analytics/{repo_id}",
        "discussions_analytics": f"/api/discussions/analytics/{repo_id}",
        "projects_analytics": f"/api/projects/analytics/{repo_id}",
        "repo_health": f"/api/repo-health/{repo_id}"
    }
    
    results = {}
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        for name, path in routes.items():
            try:
                resp = await client.get(path)
                results[name] = {
                    "path": path,
                    "status_code": resp.status_code,
                    "ok": resp.status_code == 200,
                    "error": None if resp.status_code == 200 else resp.text[:200]
                }
            except Exception as e:
                results[name] = {
                    "path": path,
                    "status_code": 500,
                    "ok": False,
                    "error": str(e)
                }
                
    all_ok = all(r["ok"] for r in results.values())
    return {
        "all_endpoints_ok": all_ok,
        "endpoints": results
    }


def test_rest_endpoints(repo_id: int) -> Dict[str, Any]:
    """Synchronous wrapper to run async REST endpoint validation."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_running():
        # Fallback if already running in an event loop
        # Create a task and wait or block
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(test_rest_endpoints_async(repo_id))
    else:
        return loop.run_until_complete(test_rest_endpoints_async(repo_id))
