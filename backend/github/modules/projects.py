"""
github/modules/projects.py
Module 7 — Project Analytics sync.
Strategy: GitHub Projects v2 (GraphQL) first, then v1 REST fallback when v2
returns no readable nodes (e.g. missing read:project scope).
"""

from datetime import datetime, timezone
import json
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from database.models import Repository, Project, ProjectItem

async def sync_projects(
    owner: str,
    repo_name: str,
    db: AsyncSession,
    gql_client,
    repo: Repository,
    rest_client=None,
    progress=None,
    batch_size: int = 500,
) -> int:
    """
    Sync GitHub Projects v2 via GraphQL, with v1 REST fallback.
    Returns count of projects synced.
    """
    print(f"[Telemetry][Projects] Syncing projects for {owner}/{repo_name}")
    repo_id = repo.id
    total_projects_val = repo.total_projects or 0
    sync_cursors_val = repo.sync_cursors

    if rest_client:
        scope_info = rest_client.get_token_scopes()
        if scope_info.get("has_token") and not scope_info.get("has_project_scope"):
            scopes = scope_info.get("scopes") or []
            if scopes and "read:project" not in scopes and "project" not in " ".join(scopes):
                print(
                    "[Telemetry][Projects] Token may lack read:project scope — "
                    "Projects v2 nodes can be null; v1 REST fallback will be attempted."
                )

    features = gql_client.fetch_repository_module_features(owner, repo_name)
    print(
        f"[Telemetry][Projects] Feature probe: github_total={features.get('projects_total')}, "
        f"status={features.get('status')}"
    )
    if features.get("status") == "auth":
        print("[Telemetry][Projects] Aborting sync — invalid GitHub token.")
        await _finalize_project_count(db, repo_id)
        return 0

    github_total = features.get("projects_total", 0) or 0
    total_synced = await _sync_projects_v2(owner, repo_name, db, gql_client, repo, progress, batch_size, total_projects_val, sync_cursors_val)

    if total_synced == 0 and github_total > 0 and rest_client:
        print(
            f"[Telemetry][Projects] v2 synced 0 but GitHub reports {github_total} project(s) — "
            "trying v1 REST fallback."
        )
        total_synced = await _sync_projects_v1(owner, repo_name, db, rest_client, repo_id, batch_size)
    elif total_synced == 0 and github_total == 0:
        print(f"[Telemetry][Projects] No projects on {owner}/{repo_name} — valid zero state.")

    # Finalize project count and update repo sync_cursors asynchronously
    repo = await db.get(Repository, repo_id)
    repo.total_projects = (await db.execute(select(func.count(Project.id)).where(Project.repo_id == repo_id))).scalar() or 0
    
    # Reload sync_cursors as they might have changed
    repo.sync_cursors = repo.sync_cursors
    await db.commit()

    if progress:
        await progress.update(
            f"Projects sync complete: {total_synced:,} records",
            processed=total_synced,
            discovered=total_synced,
        )
    print(f"[Projects] Sync complete. Synced: {total_synced}, Total in DB: {repo.total_projects}")
    return total_synced


async def _finalize_project_count(db: AsyncSession, repo_id: int):
    repo = await db.get(Repository, repo_id)
    repo.total_projects = (await db.execute(select(func.count(Project.id)).where(Project.repo_id == repo_id))).scalar() or 0
    await db.commit()


async def _sync_projects_v2(owner, repo_name, db, gql_client, repo, progress, batch_size, total_projects_val, sync_cursors_val) -> int:
    """Sync Projects v2 via GraphQL."""
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
            nodes, page_info = gql_client.fetch_projects_v2(
                owner, repo_name, first=100, cursor=cursor
            )
            api_response_count += 1
            print(
                f"[Telemetry][Projects] Pagination page {page_num}: "
                f"received {len(nodes)} project record(s)."
            )
        except Exception as e:
            print(f"[Projects v2] Fetch error: {e}")
            break

        if not nodes:
            break

        records_fetched += len(nodes)

        for item in nodes:
            if not item:
                records_skipped += 1
                continue
            try:
                status = await _upsert_project_v2(db, repo.id, owner, repo_name, item)
                if status == "inserted":
                    records_inserted += 1
                    total_synced += 1
                    batch_buffer.append(total_synced)
                    print(
                        f"[Telemetry][Projects] Inserted Project v2 #{item.get('number')}."
                    )
                elif status == "updated":
                    records_updated += 1
                    total_synced += 1
                    batch_buffer.append(total_synced)
                    print(
                        f"[Telemetry][Projects] Updated Project v2 #{item.get('number')}."
                    )
                elif status == "skipped":
                    records_skipped += 1
            except Exception as e:
                print(f"[Projects v2] Upsert error: {e}")
                continue

            if progress and total_synced % 10 == 0:
                await progress.update(
                    f"Syncing {owner}/{repo_name} Projects",
                    module="projects",
                    processed=total_synced,
                    discovered=max(total_synced, total_projects_val),
                )

            if len(batch_buffer) >= batch_size:
                await db.commit()
                batch_buffer.clear()

        has_next = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")

        # Persist cursor for resume
        try:
            cursors = json.loads(sync_cursors_val) if sync_cursors_val else {}
            cursors["projects"] = cursor
            sync_cursors_val = json.dumps(cursors)
            repo.sync_cursors = sync_cursors_val
            await db.commit()
        except Exception as e:
            print(f"[Telemetry][Projects] Cursor persistence/commit error: {e}")
            import traceback
            traceback.print_exc()
            try:
                await db.rollback()
            except Exception:
                pass

    if batch_buffer:
        await db.commit()
        batch_buffer.clear()

    print(
        f"[Telemetry][Projects] v2 sync stats: fetched={records_fetched}, "
        f"inserted={records_inserted}, updated={records_updated}, "
        f"skipped={records_skipped}, api_responses={api_response_count}"
    )
    return total_synced

async def _sync_projects_v1(owner, repo_name, db, rest_client, repo_id, batch_size) -> int:
    """Sync classic Projects v1 via REST (deprecated on many orgs)."""
    records_inserted = 0
    records_updated = 0
    records_skipped = 0

    try:
        projects = rest_client.get_projects_v1(owner, repo_name)
    except Exception as e:
        print(f"[Telemetry][Projects] v1 REST fetch failed: {e}")
        return 0

    print(f"[Telemetry][Projects] v1 REST response count: {len(projects)} projects")
    if not projects:
        return 0

    total_synced = 0
    for item in projects:
        try:
            status = await _upsert_project_v1(db, repo_id, item, rest_client)
            if status == "inserted":
                records_inserted += 1
                total_synced += 1
            elif status == "updated":
                records_updated += 1
                total_synced += 1
            else:
                records_skipped += 1
        except Exception as e:
            print(f"[Projects v1] Upsert error: {e}")
            continue

    await db.commit()
    print(
        f"[Telemetry][Projects] v1 sync stats: inserted={records_inserted}, "
        f"updated={records_updated}, skipped={records_skipped}"
    )
    return total_synced


async def _sync_project_items(db: AsyncSession, repo_id: int, project_id: int, items_nodes: list) -> tuple:
    """Sync project items nested inside Project v2."""
    inserted = 0
    updated = 0
    skipped = 0
    fetched_ids = []

    open_items_count = 0
    closed_items_count = 0
    in_progress_items_count = 0

    for item in items_nodes:
        if not item or not item.get("id"):
            continue

        github_id = item.get("id")
        fetched_ids.append(github_id)
        content_type = item.get("type")
        content = item.get("content") or {}

        # Get status from single-select field values (look for field name "Status")
        status_val = None
        field_values = (item.get("fieldValues") or {}).get("nodes", []) or []
        for fv in field_values:
            if not fv:
                continue
            field_name = (fv.get("field") or {}).get("name")
            if field_name == "Status":
                status_val = fv.get("name")
                break

        title = content.get("title")
        if not title:
            title = "Untitled Item"

        assignees_nodes = (content.get("assignees") or {}).get("nodes", []) or []
        assignees_list = [node.get("login") for node in assignees_nodes if node and node.get("login")]
        assignees_json = json.dumps(assignees_list)

        created_at = _parse_dt(content.get("createdAt"))
        updated_at = _parse_dt(content.get("updatedAt"))

        # Calculate item counts
        content_state = content.get("state")
        is_closed = False
        if content_state in ("CLOSED", "MERGED"):
            is_closed = True
        elif status_val and status_val.lower() in ("done", "closed", "completed", "done (completed)", "resolved"):
            is_closed = True

        is_in_progress = False
        if status_val and status_val.lower() in ("in progress", "doing", "progress", "started", "active"):
            is_in_progress = True

        if is_closed:
            closed_items_count += 1
        elif is_in_progress:
            in_progress_items_count += 1
        else:
            open_items_count += 1

        # Check existing ProjectItem
        existing = (await db.execute(select(ProjectItem).filter(
            ProjectItem.repo_id == repo_id,
            ProjectItem.github_id == github_id
        ))).scalars().first()

        if existing:
            # Check if any fields changed
            is_changed = False
            if existing.title != title or existing.status != status_val or existing.assignees != assignees_json or existing.content_type != content_type:
                is_changed = True
            if existing.updated_at and updated_at and existing.updated_at.replace(tzinfo=timezone.utc) != updated_at.replace(tzinfo=timezone.utc):
                is_changed = True

            if not is_changed:
                skipped += 1
                continue

            existing.project_id = project_id
            existing.content_type = content_type
            existing.title = title
            existing.status = status_val
            existing.assignees = assignees_json
            existing.updated_at = updated_at
            updated += 1
        else:
            new_item = ProjectItem(
                project_id=project_id,
                repo_id=repo_id,
                github_id=github_id,
                content_type=content_type,
                title=title,
                status=status_val,
                assignees=assignees_json,
                created_at=created_at,
                updated_at=updated_at
            )
            db.add(new_item)
            inserted += 1

    # Prune items belonging to this project that are not in fetched_ids
    if fetched_ids:
        await db.execute(delete(ProjectItem).where(
            ProjectItem.project_id == project_id,
            ProjectItem.repo_id == repo_id,
            ~ProjectItem.github_id.in_(fetched_ids)
        ))

    return inserted, updated, skipped, open_items_count, closed_items_count, in_progress_items_count


async def _sync_project_items_v1(db: AsyncSession, repo_id: int, project_id: int, project_github_id: int, rest_client) -> tuple:
    """Sync classic Project v1 cards."""
    inserted = 0
    updated = 0
    skipped = 0
    fetched_ids = []

    open_items_count = 0
    closed_items_count = 0
    in_progress_items_count = 0

    try:
        import asyncio
        columns = await asyncio.to_thread(rest_client.get_project_columns, project_github_id)
        for col in columns:
            column_name = col.get("name")
            column_id = col.get("id")

            cards = await asyncio.to_thread(rest_client.get_project_cards, column_id)
            for card in cards:
                card_id = card.get("id")
                if not card_id:
                    continue

                github_id = str(card_id)
                fetched_ids.append(github_id)

                note = card.get("note")
                content_url = card.get("content_url")

                title = note
                content_type = "DraftIssue"

                if content_url:
                    if "/pulls/" in content_url:
                        content_type = "PullRequest"
                    else:
                        content_type = "Issue"

                    item_num = content_url.split("/")[-1]
                    title = f"{content_type} #{item_num}"

                if not title:
                    title = "Untitled Card"

                created_at = _parse_dt(card.get("created_at"))
                updated_at = _parse_dt(card.get("updated_at"))

                # Check status names
                is_closed = False
                if column_name and column_name.lower() in ("done", "closed", "completed", "done (completed)", "resolved"):
                    is_closed = True
                is_in_progress = False
                if column_name and column_name.lower() in ("in progress", "doing", "progress", "started", "active"):
                    is_in_progress = True

                if is_closed:
                    closed_items_count += 1
                elif is_in_progress:
                    in_progress_items_count += 1
                else:
                    open_items_count += 1

                existing = (await db.execute(select(ProjectItem).filter(
                    ProjectItem.repo_id == repo_id,
                    ProjectItem.github_id == github_id
                ))).scalars().first()

                if existing:
                    is_changed = False
                    if existing.title != title or existing.status != column_name or existing.content_type != content_type:
                        is_changed = True
                    if existing.updated_at and updated_at and existing.updated_at.replace(tzinfo=timezone.utc) != updated_at.replace(tzinfo=timezone.utc):
                        is_changed = True

                    if not is_changed:
                        skipped += 1
                        continue

                    existing.project_id = project_id
                    existing.content_type = content_type
                    existing.title = title
                    existing.status = column_name
                    existing.updated_at = updated_at
                    updated += 1
                else:
                    new_item = ProjectItem(
                        project_id=project_id,
                        repo_id=repo_id,
                        github_id=github_id,
                        content_type=content_type,
                        title=title,
                        status=column_name,
                        created_at=created_at,
                        updated_at=updated_at
                    )
                    db.add(new_item)
                    inserted += 1
    except Exception as e:
        print(f"[Telemetry][Projects v1] Sync items error for project {project_github_id}: {e}")

    if fetched_ids:
        await db.execute(delete(ProjectItem).where(
            ProjectItem.project_id == project_id,
            ProjectItem.repo_id == repo_id,
            ~ProjectItem.github_id.in_(fetched_ids)
        ))

    return inserted, updated, skipped, open_items_count, closed_items_count, in_progress_items_count


async def _upsert_project_v2(db, repo_id: int, owner, repo_name, item) -> str:
    github_node_id = item.get("id")
    number = item.get("number")

    existing = (await db.execute(select(Project).filter(
        Project.repo_id == repo_id,
        Project.github_node_id == github_node_id,
    ))).scalars().first() if github_node_id else None

    creator = (item.get("creator") or {}).get("login")
    state = "closed" if item.get("closed") else "open"
    updated_at = _parse_dt(item.get("updatedAt"))

    if existing:
        existing_updated = existing.updated_at
        project_db_id = existing.id
        items_nodes = (item.get("items") or {}).get("nodes", []) or []
        inserted_items, updated_items, skipped_items, open_cnt, closed_cnt, in_prog_cnt = await _sync_project_items(db, repo_id, project_db_id, items_nodes)

        # Check metadata match
        if existing_updated and updated_at and existing_updated.replace(tzinfo=timezone.utc) == updated_at.replace(tzinfo=timezone.utc):
            if inserted_items == 0 and updated_items == 0:
                return "skipped"

        existing.number = number
        existing.name = (item.get("title") or "")[:512]
        existing.body = item.get("shortDescription")
        existing.state = state
        existing.creator = creator
        existing.items_count = len(items_nodes)
        existing.open_items = open_cnt
        existing.closed_items = closed_cnt
        existing.in_progress_items = in_prog_cnt
        existing.updated_at = updated_at
        existing.synced_at = datetime.utcnow()
        return "updated"

    # Insert new project
    proj = Project(
        repo_id=repo_id,
        github_node_id=github_node_id,
        number=number,
        name=(item.get("title") or "")[:512],
        body=item.get("shortDescription"),
        state=state,
        creator=creator,
        project_type="v2",
        items_count=0,
        created_at=_parse_dt(item.get("createdAt")),
        updated_at=updated_at,
    )
    db.add(proj)
    await db.flush()

    items_nodes = (item.get("items") or {}).get("nodes", []) or []
    inserted_items, updated_items, skipped_items, open_cnt, closed_cnt, in_prog_cnt = await _sync_project_items(db, repo_id, proj.id, items_nodes)

    proj.items_count = len(items_nodes)
    proj.open_items = open_cnt
    proj.closed_items = closed_cnt
    proj.in_progress_items = in_prog_cnt
    return "inserted"


async def _upsert_project_v1(db, repo_id: int, item, rest_client) -> str:
    github_id = item.get("id")
    existing = (await db.execute(select(Project).filter(
        Project.repo_id == repo_id,
        Project.github_id == github_id,
    ))).scalars().first() if github_id else None

    creator = (item.get("creator") or {}).get("login")
    state = item.get("state") or "open"
    updated_at = _parse_dt(item.get("updated_at"))

    if existing:
        project_db_id = existing.id
        inserted_items, updated_items, skipped_items, open_cnt, closed_cnt, in_prog_cnt = await _sync_project_items_v1(db, repo_id, project_db_id, github_id, rest_client)

        existing_updated = existing.updated_at
        if existing_updated and updated_at and existing_updated.replace(tzinfo=timezone.utc) == updated_at.replace(tzinfo=timezone.utc):
            if inserted_items == 0 and updated_items == 0:
                return "skipped"

        existing.name = (item.get("name") or "")[:512]
        existing.body = item.get("body")
        existing.state = state
        existing.creator = creator
        existing.items_count = open_cnt + closed_cnt + in_prog_cnt
        existing.open_items = open_cnt
        existing.closed_items = closed_cnt
        existing.in_progress_items = in_prog_cnt
        existing.updated_at = updated_at
        existing.synced_at = datetime.utcnow()
        return "updated"

    proj = Project(
        repo_id=repo_id,
        github_id=github_id,
        github_node_id=item.get("node_id"),
        name=(item.get("name") or "")[:512],
        body=item.get("body"),
        state=state,
        creator=creator,
        project_type="v1",
        created_at=_parse_dt(item.get("created_at")),
        updated_at=updated_at,
    )
    db.add(proj)
    await db.flush()

    inserted_items, updated_items, skipped_items, open_cnt, closed_cnt, in_prog_cnt = await _sync_project_items_v1(db, repo_id, proj.id, github_id, rest_client)

    proj.items_count = open_cnt + closed_cnt + in_prog_cnt
    proj.open_items = open_cnt
    proj.closed_items = closed_cnt
    proj.in_progress_items = in_prog_cnt
    return "inserted"


def _parse_dt(val) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except Exception:
        return None
