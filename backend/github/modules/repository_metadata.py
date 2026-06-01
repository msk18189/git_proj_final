"""
github/modules/repository_metadata.py

Module 4 — Repository Metadata sync.
Fetches repo info via REST and updates the Repository record.
"""
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from database.models import Repository

async def sync_repository_metadata(
    owner: str,
    repo_name: str,
    db: AsyncSession,
    rest_client,
    gql_client,
    repo: Repository,
) -> int:
    """Fetch and persist repository metadata. Returns 1 on success."""
    try:
        # Try REST first (fastest, most complete)
        data = rest_client.get_repository_metadata(owner, repo_name)
        if data:
            repo.description = (data.get("description") or "")[:1000]
            repo.homepage = (data.get("homepage") or "")[:1024]
            repo.language = data.get("language")
            repo.default_branch = data.get("default_branch")
            repo.repo_size = data.get("size", 0)
            repo.stars = data.get("stargazers_count", repo.stars or 0)
            repo.watchers = data.get("watchers_count", repo.watchers or 0)
            repo.forks_count = data.get("forks_count", repo.forks_count or 0)
            visibility = data.get("visibility", "public")
            repo.visibility = visibility if visibility in ("public", "private", "internal") else "public"
            repo.updated_at = datetime.utcnow()
            await db.commit()
            print(f"[Metadata] Updated metadata for {owner}/{repo_name}")
            return 1
    except Exception as e:
        print(f"[Metadata] REST metadata fetch failed, trying GraphQL: {e}")

    # Fallback to GraphQL
    try:
        result = gql_client.verify_repository_access(owner, repo_name)
        repo.stars = result.get("stars", repo.stars or 0)
        repo.watchers = result.get("watchers", repo.watchers or 0)
        repo.language = result.get("language")
        repo.default_branch = result.get("default_branch")
        repo.description = (result.get("description") or "")[:1000]
        repo.homepage = (result.get("homepage") or "")[:1024]
        repo.forks_count = result.get("fork_count", repo.forks_count or 0)
        repo.visibility = "private" if result.get("is_private") else "public"
        repo.updated_at = datetime.utcnow()
        await db.commit()
        print(f"[Metadata] Updated metadata via GraphQL for {owner}/{repo_name}")
        return 1
    except Exception as e:
        print(f"[Metadata] GraphQL metadata fetch failed: {e}")
        raise RuntimeError(f"Failed to retrieve repository metadata from GitHub APIs. Verify repository exists and token is valid.")
