"""
github/modules/contributors.py

Module 10 — Contributors Analytics sync.

Uses GitHub REST API /contributors endpoint.
Stores contributor metadata (github_user_id, username, contributions, type).
"""
import asyncio
from datetime import datetime, timezone
import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import Repository, Contributor

async def sync_contributors(
    owner: str,
    repo_name: str,
    db: AsyncSession,
    rest_client,
    repo: Repository,
    progress=None,
    batch_size: int = 500,
) -> int:
    """
    Full REST paginated contributors sync.
    Returns count of contributors synced.
    """
    print(f"[Telemetry][Contributors] Syncing contributors for {owner}/{repo_name}")
    repo_id = repo.id
    sync_cursors_val = repo.sync_cursors
    rate_limit_limit_val = repo.rate_limit_limit
    rate_limit_remaining_val = repo.rate_limit_remaining
    
    total_synced = 0
    batch_buffer = []
    records_fetched = 0
    records_inserted = 0
    records_updated = 0
    records_skipped = 0
    api_response_count = 0
    page_num = 0
    
    fetched_keys = set()

    for page_items in rest_client.get_contributors(owner, repo_name):
        page_num += 1
        api_response_count += 1
        records_fetched += len(page_items)
        print(f"[Telemetry][Contributors] Pagination Progress: Fetching page {page_num}. Received {len(page_items)} contributor records.")

        for item in page_items:
            try:
                is_anon = item.get("type") == "Anonymous"
                
                github_user_id = item.get("id") if not is_anon else None
                username = item.get("login") if not is_anon else None
                
                if is_anon:
                    name = item.get("name") or "Anonymous"
                    email = item.get("email") or ""
                    username = f"{name} <{email}>" if email else name
                
                if not username:
                    continue
                
                fetched_keys.add(username)
                
                contributions = item.get("contributions", 0)
                user_type = item.get("type", "User")
                
                existing = None
                if github_user_id is not None:
                    existing = (await db.execute(select(Contributor).filter(
                        Contributor.repo_id == repo_id,
                        Contributor.github_user_id == github_user_id
                    ))).scalars().first()
                
                if not existing:
                    existing = (await db.execute(select(Contributor).filter(
                        Contributor.repo_id == repo_id,
                        Contributor.username == username
                    ))).scalars().first()

                if existing:
                    if existing.github_user_id is None and github_user_id is not None:
                        existing.github_user_id = github_user_id
                        
                    if (existing.contributions == contributions and 
                        existing.type == user_type and 
                        existing.username == username):
                        records_skipped += 1
                    else:
                        existing.username = username
                        existing.contributions = contributions
                        existing.type = user_type
                        records_updated += 1
                        print(f"[Telemetry][Contributors] Incremental Decision: Updating Contributor '{username}'.")
                else:
                    contributor = Contributor(
                        repo_id=repo_id,
                        repo_owner=owner,
                        repo_name=repo_name,
                        username=username,
                        github_user_id=github_user_id,
                        contributions=contributions,
                        type=user_type,
                    )
                    db.add(contributor)
                    records_inserted += 1
                    print(f"[Telemetry][Contributors] Incremental Decision: Inserting brand new Contributor '{username}'.")

                total_synced += 1
                batch_buffer.append(total_synced)

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[Contributors] Error syncing contributor '{item.get('login') or item.get('name', '?')}': {e}")
                continue

            if progress and total_synced % 50 == 0:
                await progress.update(
                    f"Syncing {owner}/{repo_name} Contributors",
                    module="contributors",
                    processed=total_synced,
                    discovered=total_synced,
                )

            if len(batch_buffer) >= batch_size:
                await db.commit()
                batch_buffer.clear()

        try:
            next_url = getattr(rest_client, "last_next_url", None)
            cursors = json.loads(sync_cursors_val) if sync_cursors_val else {}
            cursors["contributors"] = next_url
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

    # Safe Pruning: remove obsolete contributors that were NOT returned by API and have no PRs
    db_contributors = (await db.execute(select(Contributor).filter(Contributor.repo_id == repo_id))).scalars().all()
    to_delete = [c for c in db_contributors if c.username not in fetched_keys and c.total_prs == 0 and c.github_user_id is not None]
    if to_delete:
        for c in to_delete:
            db.delete(c)
        await db.commit()
        print(f"[Telemetry][Contributors] Pruned {len(to_delete)} obsolete contributors from database.")

    if progress:
        await progress.update(f"Contributors sync complete: {total_synced:,} records", processed=total_synced, discovered=total_synced)

    print(f"[Telemetry][Contributors] Sync complete. Stats: fetched={records_fetched}, inserted={records_inserted}, updated={records_updated}, skipped={records_skipped}, api_responses={api_response_count}")
    return total_synced
