from typing import Optional
from fastapi import Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from database.models import User, UserRepository, Repository
from api.auth import decode_access_token

async def _extract_user(request: Request, authorization: Optional[str], db: AsyncSession) -> Optional[User]:
    """Decode bearer token and return User object, or None."""
    token = request.cookies.get("accessToken")
    
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            
    if not token:
        return None
        
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    
    result = await db.execute(
        select(User).where(User.username == payload["sub"])
    )
    return result.scalar_one_or_none()


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require authenticated user — raises 401 if not valid."""
    user = await _extract_user(request, authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def get_current_user_optional(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Return authenticated user or None — for endpoints that work both ways."""
    return await _extract_user(request, authorization, db)


async def require_repo_access(
    repo_id: int,
    user: Optional[User],
    db: AsyncSession,
) -> Repository:
    """Validate that a user can access the given repository.

    Rules:
    - Public repos: accessible by anyone
    - Private repos: only accessible by associated users (UserRepository)

    Returns the Repository object or raises 403/404.
    """
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Public repos are accessible by anyone
    visibility = getattr(repo, "visibility", "public") or "public"
    if visibility == "public":
        return repo

    # Private repos require auth + association
    if not user:
        raise HTTPException(
            status_code=403,
            detail="Authentication required to access private repositories",
        )

    assoc_result = await db.execute(
        select(UserRepository).where(
            (UserRepository.user_id == user.id) &
            (UserRepository.repo_id == repo.id)
        )
    )
    assoc = assoc_result.scalar_one_or_none()

    if not assoc:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this private repository",
        )

    return repo
