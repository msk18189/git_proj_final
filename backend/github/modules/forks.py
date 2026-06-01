"""
github/modules/forks.py

Module 5 — Fork Analytics sync.

Uses GitHub REST API /forks endpoint.
Stores fork metadata and computes staleness (days since last push).
"""
from datetime import datetime, timezone
import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from database.models import Repository, Fork

async def sync_forks(
    owner: str,
    repo_name: str,
    db: AsyncSession,
    rest_client,
    repo: Repository,
    progress=None,
    batch_size: int = 500,
) -> int:
    """
    Full REST paginated fork sync.
    Returns count of forks synced.
    """
    print(f"[Telemetry][Forks] Syncing forks for {owner}/{repo_name}")
    repo_id = repo.id
    total_forks_val = repo.total_forks or 0
    sync_cursors_val = repo.sync_cursors
    rate_limit_limit_val = repo.rate_limit_limit
    rate_limit_remaining_val = repo.rate_limit_remaining

    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    total_synced = 0
    batch_buffer = []
    records_fetched = 0
    records_inserted = 0
    records_updated = 0
    records_skipped = 0
    api_response_count = 0
    page_num = 0
    fetched_ids = set()

    for page_items in rest_client.get_forks(owner, repo_name):
        page_num += 1
        api_response_count += 1
        records_fetched += len(page_items)
        print(f"[Telemetry][Forks] Pagination Progress: Fetching page {page_num}. Received {len(page_items)} fork records.")

        for item in page_items:
            try:
                github_id = item.get("id")
                if not github_id:
                    continue
                fetched_ids.add(github_id)

                full_name = item.get("full_name", "")
                fork_owner = (item.get("owner") or {}).get("login", "")
                fork_name = item.get("name", "")

                pushed_at = _parse_dt(item.get("pushed_at"))
                staleness_days = None
                if pushed_at:
                    pa = pushed_at.replace(tzinfo=timezone.utc) if pushed_at.tzinfo is None else pushed_at
                    staleness_days = (now - pa).days

                existing = (await db.execute(select(Fork).filter(
                    Fork.repo_id == repo_id,
                    Fork.github_id == github_id
                ))).scalars().first()

                if existing:
                    existing_pushed = existing.pushed_at
                    if existing_pushed and pushed_at and existing_pushed.replace(tzinfo=timezone.utc) == pushed_at.replace(tzinfo=timezone.utc):
                        records_skipped += 1
                    else:
                        existing.full_name = full_name
                        existing.owner = fork_owner
                        existing.name = fork_name
                        existing.stars = item.get("stargazers_count", 0)
                        existing.forks = item.get("forks_count", 0)
                        existing.open_issues = item.get("open_issues_count", 0)
                        existing.description = (item.get("description") or "")[:500]
                        existing.language = item.get("language")
                        existing.updated_at = _parse_dt(item.get("updated_at"))
                        existing.pushed_at = pushed_at
                        existing.staleness_days = staleness_days
                        existing.synced_at = datetime.utcnow()
                        records_updated += 1
                        print(f"[Telemetry][Forks] Incremental Decision: Updating Fork '{full_name}'.")
                else:
                    fork = Fork(
                        repo_id=repo_id,
                        github_id=github_id,
                        full_name=full_name,
                        owner=fork_owner,
                        name=fork_name,
                        stars=item.get("stargazers_count", 0),
                        forks=item.get("forks_count", 0),
                        open_issues=item.get("open_issues_count", 0),
                        description=(item.get("description") or "")[:500],
                        language=item.get("language"),
                        created_at=_parse_dt(item.get("created_at")),
                        updated_at=_parse_dt(item.get("updated_at")),
                        pushed_at=pushed_at,
                        staleness_days=staleness_days,
                    )
                    db.add(fork)
                    records_inserted += 1
                    print(f"[Telemetry][Forks] Incremental Decision: Inserting brand new Fork '{full_name}'.")

                total_synced += 1
                batch_buffer.append(total_synced)

            except Exception as e:
                print(f"[Forks] Error syncing fork {item.get('full_name', '?')}: {e}")
                continue

            if progress and total_synced % 100 == 0:
                await progress.update(
                    f"Syncing {owner}/{repo_name} Forks",
                    module="forks",
                    processed=total_synced,
                    discovered=total_synced + 100,
                )

            if len(batch_buffer) >= batch_size:
                await db.commit()
                batch_buffer.clear()

        # Persist pagination cursor/next-url and rate-limit telemetry for resume (once per page)
        try:
            next_url = getattr(rest_client, "last_next_url", None)
            cursors = json.loads(sync_cursors_val) if sync_cursors_val else {}
            cursors["forks"] = next_url
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

    # Delete forks that are no longer in GitHub
    db_forks = (await db.execute(select(Fork).filter(Fork.repo_id == repo_id))).scalars().all()
    to_delete = [f for f in db_forks if f.github_id not in fetched_ids]
    if to_delete:
        for i in range(0, len(to_delete), 900):
            chunk = to_delete[i:i+900]
            for f in chunk:
                db.delete(f)
            await db.commit()
        print(f"[Telemetry][Forks] Pruned {len(to_delete)} forks from database.")

    repo = await db.get(Repository, repo_id)
    repo.total_forks = (await db.execute(select(func.count(Fork.id)).where(Fork.repo_id == repo_id))).scalar() or 0
    repo.sync_cursors = sync_cursors_val
    if rate_limit_limit_val:
        repo.rate_limit_limit = rate_limit_limit_val
    if rate_limit_remaining_val:
        repo.rate_limit_remaining = rate_limit_remaining_val
    await db.commit()

    if progress:
        await progress.update(f"Forks sync complete: {total_synced:,} records", processed=total_synced, discovered=total_synced)

    print(f"[Telemetry][Forks] Sync complete. Stats: fetched={records_fetched}, inserted={records_inserted}, updated={records_updated}, skipped={records_skipped}, api_responses={api_response_count}")
    print(f"[Forks] Sync complete. Synced: {total_synced}, Total in DB: {repo.total_forks}")
    return total_synced


def _parse_dt(val) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except Exception:
        return None
