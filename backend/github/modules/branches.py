"""
github/modules/branches.py

Module 3 — Branch Intelligence sync.

Uses GitHub REST API /branches endpoint.
Each branch record stores protection status, last commit SHA, author, and timestamp.
Staleness (days since last commit) is computed at sync time.
"""
import asyncio
from datetime import datetime, timezone
import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.models import Repository, Branch


async def sync_branches(
    owner: str,
    repo_name: str,
    db: AsyncSession,
    rest_client,
    repo: Repository,
    progress=None,
    batch_size: int = 500,
) -> int:
    """
    Full REST paginated branch sync.
    Replaces stale branch records on each full sync (branches are frequently renamed/deleted).
    Returns count of branches synced.
    """
    print(f"[Telemetry][Branches] Syncing branches for {owner}/{repo_name}")
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    total_synced = 0
    batch_buffer = []
    repo_id = repo.id
    total_branches_val = repo.total_branches or 0
    sync_cursors_val = repo.sync_cursors
    rate_limit_limit_val = repo.rate_limit_limit
    rate_limit_remaining_val = repo.rate_limit_remaining
    records_fetched = 0
    records_inserted = 0
    records_updated = 0
    records_skipped = 0
    api_response_count = 0
    page_num = 0
    fetched_names = set()

    for page_items in rest_client.get_branches(owner, repo_name):
        page_num += 1
        api_response_count += 1
        records_fetched += len(page_items)
        print(f"[Telemetry][Branches] Pagination Progress: Fetching page {page_num}. Received {len(page_items)} branch records.")

        for item in page_items:
            try:
                name = item.get("name", "")
                if not name:
                    continue
                fetched_names.add(name)

                # Fallback info from the list response
                protected = item.get("protected", False)
                commit_data = item.get("commit") or {}
                last_sha = commit_data.get("sha")
                commit_inner = commit_data.get("commit") or {}
                commit_author = commit_inner.get("author") or {}
                last_commit_author = commit_author.get("name") or commit_author.get("email")
                last_commit_at = _parse_dt(commit_author.get("date"))
                last_commit_message = (commit_inner.get("message") or "")[:500]

                # Fetch detailed branch info (message, author, timestamp) since it is missing from /branches list response
                try:
                    detail = await asyncio.to_thread(rest_client.get_branch_detail, owner, repo_name, name)
                    if detail:
                        protected = detail.get("protected", False)
                        commit_data_det = detail.get("commit") or {}
                        last_sha = commit_data_det.get("sha") or last_sha
                        commit_inner_det = commit_data_det.get("commit") or {}
                        commit_author_det = commit_inner_det.get("author") or {}
                        last_commit_author = commit_author_det.get("name") or commit_author_det.get("email") or last_commit_author
                        last_commit_at = _parse_dt(commit_author_det.get("date")) or last_commit_at
                        last_commit_message = (commit_inner_det.get("message") or "")[:500] or last_commit_message
                except Exception as detail_err:
                    print(f"[Branches] Failed to fetch details for branch '{name}': {detail_err}")

                staleness_days = None
                if last_commit_at:
                    lca = last_commit_at.replace(tzinfo=timezone.utc) if last_commit_at.tzinfo is None else last_commit_at
                    staleness_days = (now - lca).days

                existing = (await db.execute(select(Branch).filter(
                    Branch.repo_id == repo_id,
                    Branch.name == name
                ))).scalars().first()

                if existing:
                    if existing.last_commit_sha == last_sha and existing.protected == protected:
                        records_skipped += 1
                    else:
                        existing.protected = protected
                        existing.last_commit_sha = last_sha
                        existing.last_commit_message = last_commit_message
                        existing.last_commit_author = last_commit_author
                        existing.last_commit_at = last_commit_at
                        existing.staleness_days = staleness_days
                        existing.synced_at = datetime.utcnow()
                        records_updated += 1
                        print(f"[Telemetry][Branches] Incremental Decision: Updating Branch '{name}' (commit SHA or protection status changed).")
                else:
                    branch = Branch(
                        repo_id=repo_id,
                        repo_owner=owner,
                        repo_name=repo_name,
                        name=name,
                        protected=protected,
                        last_commit_sha=last_sha,
                        last_commit_message=last_commit_message,
                        last_commit_author=last_commit_author,
                        last_commit_at=last_commit_at,
                        staleness_days=staleness_days,
                    )
                    db.add(branch)
                    records_inserted += 1
                    print(f"[Telemetry][Branches] Incremental Decision: Inserting brand new Branch '{name}'.")

                total_synced += 1
                batch_buffer.append(total_synced)

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[Branches] Error syncing branch '{item.get('name', '?')}': {e}")
                continue

            if progress and total_synced % 50 == 0:
                await progress.update(
                    f"Syncing {owner}/{repo_name} Branches",
                    module="branches",
                    processed=total_synced,
                    discovered=max(total_synced, total_branches_val),
                )

            if len(batch_buffer) >= batch_size:
                await db.commit()
                batch_buffer.clear()

        # Persist pagination cursor/next-url and rate-limit telemetry for resume (once per page)
        try:
            next_url = getattr(rest_client, "last_next_url", None)
            cursors = json.loads(sync_cursors_val) if sync_cursors_val else {}
            cursors["branches"] = next_url
            sync_cursors_val = json.dumps(cursors)
            repo.sync_cursors = sync_cursors_val
            rl = getattr(rest_client, "last_rate_limit", None)
            if rl:
                rate_limit_limit_val = rl.get("limit") or rate_limit_limit_val
                repo.rate_limit_limit = rate_limit_limit_val
                rate_limit_remaining_val = rl.get("remaining") or rate_limit_remaining_val
                repo.rate_limit_remaining = rate_limit_remaining_val
                try:
                    reset_ts = rl.get("reset")
                    if reset_ts:
                        repo.rate_limit_reset = datetime.fromtimestamp(float(reset_ts))
                except Exception:
                    pass
            await db.commit()
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass

    if batch_buffer:
        await db.commit()
        batch_buffer.clear()

    # Delete branches that are no longer in GitHub
    db_branches = (await db.execute(select(Branch).filter(Branch.repo_id == repo_id))).scalars().all()
    to_delete = [b for b in db_branches if b.name not in fetched_names]
    if to_delete:
        for i in range(0, len(to_delete), 900):
            chunk = to_delete[i:i+900]
            for b in chunk:
                db.delete(b)
            await db.commit()
        print(f"[Telemetry][Branches] Pruned {len(to_delete)} branches from database.")

    # Update repository totals
    repo = await db.get(Repository, repo_id)
    repo.total_branches = (await db.execute(select(func.count(Branch.id)).where(Branch.repo_id == repo_id))).scalar() or 0
    total_branches_final = repo.total_branches
    await db.commit()

    if progress:
        await progress.update(f"Branches sync complete: {total_synced:,} records", processed=total_synced, discovered=total_synced)

    print(f"[Telemetry][Branches] Sync complete. Stats: fetched={records_fetched}, inserted={records_inserted}, updated={records_updated}, skipped={records_skipped}, api_responses={api_response_count}")
    print(f"[Branches] Sync complete. Synced: {total_synced}, Total in DB: {total_branches_final}")
    return total_synced


def _parse_dt(val) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except Exception:
        return None
