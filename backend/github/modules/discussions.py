"""
github/modules/discussions.py

Module 6 — Discussion Analytics sync.

Uses GitHub GraphQL API (repository.discussions).
If discussions are not enabled on a repo, returns 0 gracefully.
"""
from datetime import datetime, timezone
import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from database.models import Repository, Discussion, DiscussionComment


async def sync_discussions(
    owner: str,
    repo_name: str,
    db: AsyncSession,
    gql_client,
    repo: Repository,
    progress=None,
    batch_size: int = 500,
) -> int:
    """
    Full GraphQL paginated discussion sync.
    Returns count of discussions synced.
    """
    print(f"[Telemetry][Discussions] Syncing discussions for {owner}/{repo_name}")
    repo_id = repo.id
    total_discussions_val = repo.total_discussions or 0
    sync_cursors_val = repo.sync_cursors

    features = gql_client.fetch_repository_module_features(owner, repo_name)
    print(
        f"[Telemetry][Discussions] Feature probe: enabled={features.get('discussions_enabled')}, "
        f"github_total={features.get('discussions_total')}, status={features.get('status')}"
    )
    if features.get("status") == "auth":
        print("[Telemetry][Discussions] Aborting sync — invalid GitHub token.")
        return 0
    if not features.get("discussions_enabled") and features.get("discussions_total", 0) == 0:
        print(f"[Telemetry][Discussions] Discussions not enabled on {owner}/{repo_name} — valid zero state.")
        repo = await db.get(Repository, repo_id)
        repo.total_discussions = 0
        await db.commit()
        return 0

    total_synced = 0
    cursor = None
    has_next = True
    batch_buffer = []

    records_fetched = 0
    records_inserted = 0
    records_updated = 0
    records_skipped = 0
    api_response_count = 0
    page_num = 0

    while has_next:
        page_num += 1
        try:
            nodes, page_info = gql_client.fetch_discussions(
                owner,
                repo_name, 
                first=100, 
                cursor=cursor
            )
            api_response_count += 1
            print(f"[Telemetry][Discussions] Pagination Progress: Fetching page {page_num} (cursor={cursor}). Received {len(nodes)} discussion records.")
        except Exception as e:
            print(f"[Discussions] Fetch error: {e}")
            break

        if not nodes:
            break

        records_fetched += len(nodes)

        for item in nodes:
            try:
                status = await _upsert_discussion(db, repo_id, owner, repo_name, item)
                if status == "inserted":
                    records_inserted += 1
                    total_synced += 1
                    batch_buffer.append(total_synced)
                    print(f"[Telemetry][Discussions] Incremental Decision: Inserting brand new Discussion #{item.get('number')}.")
                elif status == "updated":
                    records_updated += 1
                    total_synced += 1
                    batch_buffer.append(total_synced)
                    print(f"[Telemetry][Discussions] Incremental Decision: Updating Discussion #{item.get('number')}.")
                elif status == "skipped":
                    records_skipped += 1
            except Exception as e:
                print(f"[Discussions] Upsert error for discussion #{item.get('number', '?')}: {e}")
                continue

            if progress and total_synced % 50 == 0:
                await progress.update(
                    f"Syncing {owner}/{repo_name} Discussions",
                    module="discussions",
                    processed=total_synced,
                    discovered=max(total_synced, total_discussions_val),
                )

            if len(batch_buffer) >= batch_size:
                await db.commit()
                batch_buffer.clear()

        has_next = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")

        # Persist cursor for resume (once per page)
        try:
            cursors = json.loads(sync_cursors_val) if sync_cursors_val else {}
            cursors["discussions"] = cursor
            sync_cursors_val = json.dumps(cursors)
            repo.sync_cursors = sync_cursors_val
            await db.commit()
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass

    if batch_buffer:
        await db.commit()
        batch_buffer.clear()

    repo = await db.get(Repository, repo_id)
    repo.total_discussions = (await db.execute(select(func.count(Discussion.id)).where(Discussion.repo_id == repo_id))).scalar() or 0
    repo.sync_cursors = sync_cursors_val
    await db.commit()

    if progress:
        await progress.update(f"Discussions sync complete: {total_synced:,} records", processed=total_synced, discovered=total_synced)

    print(f"[Telemetry][Discussions] Sync complete. Stats: fetched={records_fetched}, inserted={records_inserted}, updated={records_updated}, skipped={records_skipped}, api_responses={api_response_count}")
    print(f"[Discussions] Sync complete. Synced: {total_synced}, Total in DB: {repo.total_discussions}")
    return total_synced


async def _upsert_discussion(db: AsyncSession, repo_id: int, owner: str, repo_name: str, item: dict) -> str:
    github_id = item.get("id")
    number = item.get("number")

    existing = (await db.execute(select(Discussion).filter(
        Discussion.repo_id == repo_id,
        Discussion.discussion_number == number
    ))).scalars().first() if number else None

    category = (item.get("category") or {}).get("name")
    author = (item.get("author") or {}).get("login", "unknown")
    state = "CLOSED" if item.get("closed") else "OPEN"
    answer_chosen = item.get("answer") is not None
    comment_count = (item.get("comments") or {}).get("totalCount", 0)
    reaction_count = (item.get("reactions") or {}).get("totalCount", 0)
    participant_count = (item.get("participants") or {}).get("totalCount", 0)
    created_at = _parse_dt(item.get("createdAt"))
    updated_at = _parse_dt(item.get("updatedAt"))

    if existing:
        existing_updated = existing.updated_at
        if existing_updated and updated_at and existing_updated.replace(tzinfo=timezone.utc) == updated_at.replace(tzinfo=timezone.utc):
            return "skipped"
        existing.github_id = github_id
        existing.title = (item.get("title") or "")[:1000]
        existing.body = item.get("body")
        existing.category = category
        existing.author = author
        existing.state = state
        existing.answer_chosen = answer_chosen
        existing.comment_count = comment_count
        existing.reaction_count = reaction_count
        existing.participant_count = participant_count
        existing.updated_at = updated_at
        existing.synced_at = datetime.utcnow()
        await _sync_comments_and_replies(db, repo_id, existing.id, item)
        return "updated"
    else:
        disc = Discussion(
            repo_id=repo_id,
            repo_owner=owner,
            repo_name=repo_name,
            github_id=github_id,
            discussion_number=number,
            title=(item.get("title") or "")[:1000],
            body=item.get("body"),
            category=category,
            author=author,
            state=state,
            answer_chosen=answer_chosen,
            comment_count=comment_count,
            reaction_count=reaction_count,
            participant_count=participant_count,
            created_at=created_at,
            updated_at=updated_at,
        )
        db.add(disc)
        await db.flush()
        await _sync_comments_and_replies(db, repo_id, disc.id, item)
        return "inserted"

async def _sync_comments_and_replies(db: AsyncSession, repo_id: int, discussion_id: int, item: dict):
    # Gather all comment and reply nodes
    comments_data = item.get("comments") or {}
    nodes = comments_data.get("nodes") or []
    
    flat_nodes = []
    for c_node in nodes:
        if not c_node:
            continue
        flat_nodes.append(c_node)
        replies_data = c_node.get("replies") or {}
        reply_nodes = replies_data.get("nodes") or []
        for r_node in reply_nodes:
            if r_node:
                flat_nodes.append(r_node)
                
    # Track active comment/reply IDs to prune deletions
    active_ids = set()
    
    for node in flat_nodes:
        github_id = node.get("id")
        if not github_id:
            continue
        active_ids.add(github_id)
        
        author = (node.get("author") or {}).get("login", "unknown")
        body = node.get("body")
        reaction_count = (node.get("reactions") or {}).get("totalCount", 0)
        created_at = _parse_dt(node.get("createdAt"))
        
        existing_comment = (await db.execute(select(DiscussionComment).filter(
            DiscussionComment.repo_id == repo_id,
            DiscussionComment.github_id == github_id
        ))).scalars().first()
        
        if existing_comment:
            existing_comment.author = author
            existing_comment.body = body
            existing_comment.reaction_count = reaction_count
            existing_comment.created_at = created_at
        else:
            new_comment = DiscussionComment(
                discussion_id=discussion_id,
                repo_id=repo_id,
                github_id=github_id,
                author=author,
                body=body,
                reaction_count=reaction_count,
                created_at=created_at,
            )
            db.add(new_comment)
            
    # Delete comments/replies no longer present
    db_comments = (await db.execute(select(DiscussionComment).filter(
        DiscussionComment.discussion_id == discussion_id
    ))).scalars().all()
    for db_c in db_comments:
        if db_c.github_id not in active_ids:
            await db.delete(db_c)


def _parse_dt(val) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except Exception:
        return None
