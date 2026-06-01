"""
github/modules/issues.py

Module 2 — Issue Intelligence sync.

Uses GitHub REST API /issues endpoint.
Correctly filters out pull requests (items with 'pull_request' key).
Supports incremental sync via 'since' parameter.
"""
from datetime import datetime, timezone
from typing import Optional
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from database.models import Repository, Issue

async def sync_issues(
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
    """
    Full REST paginated issue sync with incremental detection via 'since'.
    Correctly filters pull requests from the /issues endpoint.
    Returns total records synced (new + updated).
    """
    repo_id = repo.id
    total_issues_val = repo.total_issues or 0
    sync_cursors_val = repo.sync_cursors
    rate_limit_limit_val = repo.rate_limit_limit
    rate_limit_remaining_val = repo.rate_limit_remaining

    since_iso = None
    if since:
        since_ts = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since
        since_iso = since_ts.isoformat().replace("+00:00", "Z")
        print(f"[Telemetry][Issues] Ingestion Mode: Incremental. Filtering since: {since_iso}")
    else:
        print(f"[Telemetry][Issues] Ingestion Mode: Full sync mode for {owner}/{repo_name}")

    total_synced = 0
    records_fetched = 0
    records_inserted = 0
    records_updated = 0
    records_skipped = 0
    api_response_count = 0
    batch_buffer = []
    page_num = 0
    fetched_numbers = set()
    
    # Initialize synced count from database count
    synced_issues_val = (await db.execute(select(func.count(Issue.id)).where(Issue.repo_id == repo_id))).scalar() or 0
    
    for page_items in rest_client.get_issues(owner, repo_name, since=since_iso):
        page_num += 1
        api_response_count += 1
        print(f"[Telemetry][Issues] Pagination Progress: Fetching page {page_num}. Received {len(page_items)} issue records.")

        for issue in page_items:
            # Exclude pull requests correctly
            if "pull_request" in issue:
                continue

            records_fetched += 1
            updated_at = _parse_dt(issue.get("updated_at"))
            if updated_at and updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)

            try:
                if issue.get("number"):
                    fetched_numbers.add(issue.get("number"))
                status = await _upsert_issue(db, repo_id, owner, repo_name, issue)
                if status == "inserted":
                    records_inserted += 1
                    total_synced += 1
                    synced_issues_val += 1
                    batch_buffer.append(total_synced)
                    print(f"[Telemetry][Issues] Incremental Decision: Inserting brand new Issue #{issue.get('number')}.")
                elif status == "updated":
                    records_updated += 1
                    total_synced += 1
                    batch_buffer.append(total_synced)
                    print(f"[Telemetry][Issues] Incremental Decision: Updating Issue #{issue.get('number')}.")
                elif status == "skipped":
                    records_skipped += 1
            except Exception as e:
                print(f"[Issues] Upsert error for issue #{issue.get('number', '?')}: {e}")
                continue

            # Progress
            if progress and total_synced % 100 == 0:
                await progress.update(
                    f"Syncing {owner}/{repo_name} Issues",
                    module="issues",
                    processed=total_synced,
                    discovered=max(total_synced, total_issues_val),
                )

            # Batch commit
            if len(batch_buffer) >= batch_size:
                await db.commit()
                batch_buffer.clear()

        if lightweight_mode:
            print(f"[Issues] Lightweight mode active: processed one page of issues. Breaking pagination.")
            break

        # Persist pagination cursor/next-url and rate-limit telemetry for resume
        try:
            next_url = getattr(rest_client, "last_next_url", None)
            cursors = json.loads(sync_cursors_val) if sync_cursors_val else {}
            cursors["issues"] = next_url
            sync_cursors_val = json.dumps(cursors)

            # capture last rate limit if available
            rl = getattr(rest_client, "last_rate_limit", None)
            if rl:
                rate_limit_limit_val = rl.get("limit") or rate_limit_limit_val
                rate_limit_remaining_val = rl.get("remaining") or rate_limit_remaining_val
            await db.commit()
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass

    if batch_buffer:
        await db.commit()
        batch_buffer.clear()

    # Delete issues that are no longer in GitHub (only during full sync)
    if not since:
        db_issues = (await db.execute(select(Issue).filter(Issue.repo_id == repo_id))).scalars().all()
        to_delete = [iss for iss in db_issues if iss.issue_number not in fetched_numbers]
        if to_delete:
            for i in range(0, len(to_delete), 900):
                chunk = to_delete[i:i+900]
                for iss in chunk:
                    db.delete(iss)
                await db.commit()
            print(f"[Telemetry][Issues] Pruned {len(to_delete)} issues from database.")

    # Update repository totals asynchronously
    repo = await db.get(Repository, repo_id)
    repo.total_issues = (await db.execute(select(func.count(Issue.id)).where(Issue.repo_id == repo_id))).scalar() or 0
    repo.synced_issues = repo.total_issues
    repo.sync_cursors = sync_cursors_val
    if rate_limit_limit_val:
        repo.rate_limit_limit = rate_limit_limit_val
    if rate_limit_remaining_val:
        repo.rate_limit_remaining = rate_limit_remaining_val
    await db.commit()

    if progress:
        await progress.update(
            f"Issues sync complete: {total_synced:,} records",
            processed=total_synced,
            discovered=total_synced,
        )

    print(f"[Telemetry][Issues] Sync complete. Stats: fetched={records_fetched}, inserted={records_inserted}, updated={records_updated}, skipped={records_skipped}, api_responses={api_response_count}")
    print(f"[Telemetry][Issues] Sync complete.")
    print(f"pages fetched: {page_num}")
    print(f"issues fetched: {records_fetched}")
    print(f"inserted: {records_inserted}")
    print(f"updated: {records_updated}")
    print(f"skipped: {records_skipped}")
    print(f"[Issues] Sync complete. Synced: {total_synced}, Total in DB: {repo.total_issues}")
    return total_synced


async def _upsert_issue(db: AsyncSession, repo_id: int, owner: str, repo_name: str, item: dict) -> str:
    """Upsert a single issue record. Returns status ('inserted', 'updated', 'skipped')."""
    issue_number = item.get("number")
    if not issue_number:
        return "skipped"

    # Parse dates
    created_at = _parse_dt(item.get("created_at"))
    updated_at = _parse_dt(item.get("updated_at"))
    closed_at = _parse_dt(item.get("closed_at"))

    # Derive resolution time
    resolution_hours = None
    if created_at and closed_at:
        c = created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else created_at
        cl = closed_at.replace(tzinfo=timezone.utc) if closed_at.tzinfo is None else closed_at
        resolution_hours = (cl - c).total_seconds() / 3600

    # Labels
    labels = [lb.get("name", "") for lb in (item.get("labels") or []) if lb]
    labels_json = json.dumps(labels)
    is_bug = any("bug" in lb.lower() for lb in labels)

    # Assignees
    assignees = [a.get("login", "") for a in (item.get("assignees") or []) if a]
    assignees_json = json.dumps(assignees)

    author = (item.get("user") or {}).get("login", "unknown")
    state = item.get("state", "open")
    state_reason = item.get("state_reason")
    comment_count = item.get("comments", 0)
    github_id = item.get("id")
    title = (item.get("title") or "")[:1000]
    body = item.get("body")

    existing = (await db.execute(select(Issue).filter(
        Issue.repo_id == repo_id,
        Issue.issue_number == issue_number
    ))).scalars().first()

    if existing:
        existing_updated = existing.updated_at
        if existing_updated and updated_at and existing_updated.replace(tzinfo=timezone.utc) == updated_at.replace(tzinfo=timezone.utc):
            return "skipped"

        existing.title = title
        existing.body = body
        existing.state = state
        existing.state_reason = state_reason
        existing.labels = labels_json
        existing.assignees = assignees_json
        existing.author = author
        existing.is_bug = is_bug
        existing.updated_at = updated_at
        existing.closed_at = closed_at
        existing.comment_count = comment_count
        existing.resolution_hours = resolution_hours
        return "updated"
    else:
        issue = Issue(
            repo_id=repo_id,
            repo_owner=owner,
            repo_name=repo_name,
            issue_number=issue_number,
            github_id=github_id,
            title=title,
            body=body,
            state=state,
            state_reason=state_reason,
            labels=labels_json,
            assignees=assignees_json,
            author=author,
            is_bug=is_bug,
            created_at=created_at,
            updated_at=updated_at,
            closed_at=closed_at,
            comment_count=comment_count,
            resolution_hours=resolution_hours,
        )
        db.add(issue)
        return "inserted"


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except Exception:
        return None
