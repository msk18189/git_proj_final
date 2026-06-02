from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.database import get_db
from database.models import Repository, PullRequest, Contributor, User, RefreshToken, MLPrediction, UserRepository
from api.auth import (
    UserSignup, UserLogin, TokenResponse, RefreshTokenRequest,
    hash_password, verify_password, create_access_token, create_refresh_token_value,
    REFRESH_TOKEN_EXPIRE_DAYS, hash_refresh_token, is_hashed_refresh_token
)
from ml.models import MLModels
from services.data_processor import DataProcessor, parse_github_repo_url, normalize_github_url
from services.extended_analytics import ExtendedAnalytics
from services.module_analytics import (
    IssueAnalytics, BranchAnalytics, ForkAnalytics,
    CICDAnalytics, DiscussionAnalytics, ProjectAnalytics, RepoHealthAnalytics
)
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta  
from typing import Optional
import io
import threading
from playwright.async_api import async_playwright
from api.dependencies import get_current_user, get_current_user_optional, require_repo_access
from api.rate_limiter import limiter
import config

router = APIRouter()

def _cookie_secure() -> bool:
    return bool(getattr(config, "COOKIE_SECURE", False))

def _set_auth_cookies(response: Response, access_token: str):
    response.set_cookie(
        key="accessToken",
        value=access_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        key="isAuthenticated",
        value="true",
        httponly=False,
        secure=_cookie_secure(),
        samesite="strict",
        path="/",
    )

def normalize_telemetry_counts(synced: int, expected: int) -> tuple:

    s = synced if synced is not None else 0
    exp = expected if expected is not None else 0
    if exp <= 0 and s <= 0:
        return (0, 0)
    if exp <= 0 and s > 0:
        return (s, s)
    return (s, max(exp, s))

class RepositoryRequest(BaseModel):
    url: str
    github_token: Optional[str] = None
    sync_mode: Optional[str] = None

class CompareRequest(BaseModel):
    url_a: str
    url_b: str
    github_token: Optional[str] = None

# ---------------------------------------------------------------------------
# Background sync (via SyncEngine)
# ---------------------------------------------------------------------------

async def run_background_sync(repo_url: str, github_token: Optional[str], sync_mode: Optional[str] = None):
    """Launch SyncEngine in background task."""
    try:
        print(f"[AUTH AUDIT] run_background_sync: token_present={bool(github_token)}")
        from github.sync_engine import run_sync_in_background
        await run_sync_in_background(repo_url, github_token, sync_mode=sync_mode)
    except Exception as e:
        print(f"[Routes] Background sync error for {repo_url}: {e}")

# ---------------------------------------------------------------------------
# AUTHENTICATION ROUTES
# ---------------------------------------------------------------------------

@router.post("/api/auth/signup", response_model=TokenResponse)
@limiter.limit(config.SIGNUP_RATE_LIMIT)
async def signup(request: Request, payload: UserSignup, response: Response, db: AsyncSession = Depends(get_db)):
    """Register a new user, hash password, and return a JWT."""
    if payload.confirm_password is not None and payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")
        
    username = payload.username.strip()
    email = payload.email.strip().lower()
    
    # Check if user already exists
    result = await db.execute(
        select(User).where(
            (User.username == username) | (User.email == email)
        )
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        if existing_user.username == username:
            raise HTTPException(status_code=400, detail="Username already exists.")
        else:
            raise HTTPException(status_code=400, detail="Email already registered.")
            
    # Hash password and create user
    hashed = hash_password(payload.password)
    new_user = User(
        username=username,
        email=email,
        password_hash=hashed
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    
    # Generate access token
    access_token, expires_in = create_access_token({"sub": new_user.username, "email": new_user.email})
    
    # Generate and store refresh token
    refresh_token_value = create_refresh_token_value()
    refresh_token_expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = RefreshToken(
        user_id=new_user.id,
        token_value=hash_refresh_token(refresh_token_value),
        expires_at=refresh_token_expires
    )
    db.add(refresh_token)
    await db.commit()
    
    _set_auth_cookies(response, access_token)
    
    return TokenResponse(
        refresh_token=refresh_token_value,
        expires_in=expires_in,
        username=new_user.username,
        email=new_user.email
    )

@router.post("/api/auth/login", response_model=TokenResponse)
@limiter.limit(config.LOGIN_RATE_LIMIT)
async def login(request: Request, payload: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    """Authenticate with username or email, verify password, and return a JWT."""
    ident = payload.username_or_email.strip()
    
    # Query by username or email
    result = await db.execute(
        select(User).where(
            (User.username == ident) | (User.email == ident.lower())
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username, email, or password.")
        
    access_token, expires_in = create_access_token({"sub": user.username, "email": user.email})
    
    # Generate and store refresh token
    refresh_token_value = create_refresh_token_value()
    refresh_token_expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = RefreshToken(
        user_id=user.id,
        token_value=hash_refresh_token(refresh_token_value),
        expires_at=refresh_token_expires
    )
    db.add(refresh_token)
    await db.commit()
    
    _set_auth_cookies(response, access_token)
    
    return TokenResponse(
        refresh_token=refresh_token_value,
        expires_in=expires_in,
        username=user.username,
        email=user.email
    )

@router.post("/api/auth/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_access_token(request: Request, payload: RefreshTokenRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new access token.
    
    - Validates that the refresh token exists, is not revoked, and has not expired
    - Returns a new short-lived access token
    - Optionally rotates the refresh token (issues a new one)
    """
    # Find the refresh token in the database
    incoming_token_hash = hash_refresh_token(payload.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            (RefreshToken.token_value == incoming_token_hash) & (RefreshToken.revoked == False)
        )
    )
    refresh_token = result.scalar_one_or_none()

    if not refresh_token:
        result = await db.execute(
            select(RefreshToken).where(
                (RefreshToken.token_value == payload.refresh_token) & (RefreshToken.revoked == False)
            )
        )
        refresh_token = result.scalar_one_or_none()
        if refresh_token and not is_hashed_refresh_token(refresh_token.token_value):
            refresh_token.token_value = incoming_token_hash
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Invalid or revoked refresh token.")
    
    # Check if the refresh token has expired
    # Compare timezone-aware datetimes since expires_at is naive but stored in UTC
    expires_at_utc = refresh_token.expires_at.replace(tzinfo=timezone.utc) if refresh_token.expires_at.tzinfo is None else refresh_token.expires_at
    if expires_at_utc < datetime.now(timezone.utc):
        # Mark as revoked if expired
        refresh_token.revoked = True
        await db.commit()
        raise HTTPException(status_code=401, detail="Refresh token has expired.")
    
    # Get the associated user
    result = await db.execute(
        select(User).where(User.id == refresh_token.user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    
    # Generate new access token
    access_token, expires_in = create_access_token({"sub": user.username, "email": user.email})
    
    # Optional: Rotate the refresh token (issue a new one)
    # This is a security best practice to reduce the window of exposure
    new_refresh_token_value = create_refresh_token_value()
    new_refresh_token_expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Revoke the old refresh token
    refresh_token.revoked = True
    
    # Create the new refresh token (store as hash)
    new_refresh_token = RefreshToken(
        user_id=user.id,
        token_value=hash_refresh_token(new_refresh_token_value),
        expires_at=new_refresh_token_expires
    )
    db.add(new_refresh_token)
    await db.commit()
    
    _set_auth_cookies(response, access_token)
    
    return TokenResponse(
        refresh_token=new_refresh_token_value,
        expires_in=expires_in,
        username=user.username,
        email=user.email
    )

@router.post("/api/auth/logout")
async def logout(
    response: Response,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    if current_user:
        from sqlalchemy import update
        await db.execute(
            update(RefreshToken)
            .where((RefreshToken.user_id == current_user.id) & (RefreshToken.revoked == False))
            .values(revoked=True)
        )
        await db.commit()
        
    response.delete_cookie(key="accessToken", path="/", secure=_cookie_secure(), httponly=True, samesite="strict")
    response.delete_cookie(key="isAuthenticated", path="/", secure=_cookie_secure(), samesite="strict")
    return {"message": "Logged out"}

@router.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email}

# ---------------------------------------------------------------------------
# REPOSITORY MANAGEMENT
# ---------------------------------------------------------------------------

@router.post("/api/verify-repo")
@limiter.limit(config.VERIFY_RATE_LIMIT)
async def verify_repository(request: Request, payload: RepositoryRequest, db: AsyncSession = Depends(get_db)):
    """Verify repository accessibility and fetch basic metadata including API usage estimates."""
    url = payload.url.strip()
    user_token = (payload.github_token or "").strip() or None
    token_source = "user" if user_token else "none"

    # Step 1: URL Validation
    try:
        from services.data_processor import parse_github_repo_url
        owner, repo_name = parse_github_repo_url(url)
    except Exception:
        return {
            "ok": False,
            "status": "INVALID_URL",
            "detail": "Invalid GitHub repository URL"
        }

    from github.client import GitHubClient, GitHubRestClient
    rest = GitHubRestClient(token=user_token)

    exists = False
    is_private = False
    has_token = bool(user_token)
    is_large = False
    ok = False

    try:
        # Step 2: Repository Existence Check
        meta = rest.get_repository_metadata(owner, repo_name)
        if not meta:
            if "private" in repo_name.lower() and not user_token:
                print(f"[VALIDATION]\nurl={url}\nowner={owner}\nrepo={repo_name}\nexists=True\nprivate=True\nauthenticated=False\nlarge_repo=False\ncan_analyze=False")
                return {
                    "ok": False,
                    "status": "PRIVATE_REPO_PAT_REQUIRED",
                    "detail": "Private repository. GitHub PAT required.",
                    "owner": owner,
                    "repo": repo_name,
                    "is_private": True
                }
            print(f"[VALIDATION]\nurl={url}\nowner={owner}\nrepo={repo_name}\nexists=False\nprivate=False\nauthenticated={has_token}\nlarge_repo=False\ncan_analyze=False")
            return {
                "ok": False,
                "status": "NOT_FOUND",
                "detail": "Repository does not exist"
            }

        exists = True
        is_private = meta.get("private", False)
        
        # Step 3: Repository Visibility
        if is_private and not user_token:
            print(f"[VALIDATION]\nurl={url}\nowner={owner}\nrepo={repo_name}\nexists=True\nprivate=True\nauthenticated=False\nlarge_repo=False\ncan_analyze=False")
            return {
                "ok": False,
                "status": "PRIVATE_REPO_PAT_REQUIRED",
                "detail": "Private repository. GitHub PAT required.",
                "owner": owner,
                "repo": repo_name,
                "is_private": True
            }

        discussions_enabled = False
        discussions_total = 0
        projects_total = 0
        scope_info = {"scopes": [], "has_project_scope": False}
        if user_token:
            try:
                gql_client = GitHubClient(token=user_token)
                features = gql_client.fetch_repository_module_features(owner, repo_name)
                discussions_enabled = features.get("discussions_enabled", False)
                discussions_total = features.get("discussions_total", 0)
                projects_total = features.get("projects_total", 0)
                scope_info = rest.get_token_scopes()
            except Exception as e:
                print(f"[Verify] GraphQL probe failed: {e}")

        # Step 4: Repository Size Classification
        estimates = rest.get_repository_estimates(owner, repo_name)
        chosen_estimate = estimates["estimated_requests_pat"] if user_token else estimates["estimated_requests_rest"]
        is_large = chosen_estimate > 60

        canonical_url = normalize_github_url(estimates["owner"], estimates["repo"])

        detail_msg = "Repository verified."
        if is_private:
            status = "VERIFIED_PAT"
        else:
            if is_large and not user_token:
                status = "LARGE_REPO_PAT_REQUIRED"
                detail_msg = "Large repository. PAT recommended for full analysis."
                ok = False
            elif user_token:
                status = "VERIFIED_PAT"
                ok = True
            else:
                status = "VERIFIED_ANONYMOUS"
                ok = True

        # Step 5: Analysis Eligibility
        print(f"[VALIDATION]\nurl={url}\nowner={owner}\nrepo={repo_name}\nexists=True\nprivate={is_private}\nauthenticated={has_token}\nlarge_repo={is_large}\ncan_analyze={ok}")

        return {
            "ok": ok,
            "status": status,
            "detail": detail_msg,
            "owner": estimates["owner"],
            "repo": estimates["repo"],
            "is_private": is_private,
            "url": canonical_url,
            "stars": estimates["stars"],
            "language": estimates["language"],
            "description": estimates["description"],
            "has_token": has_token,
            "token_source": token_source,
            "discussions_enabled": discussions_enabled,
            "discussions_total": discussions_total or estimates["discussions_count"],
            "projects_total": projects_total,
            "token_scopes": scope_info.get("scopes", []),
            "has_project_scope": scope_info.get("has_project_scope", False),
            "pr_count": estimates["pr_count"],
            "issues_count": estimates["issues_count"],
            "forks_count": estimates["forks_count"],
            "contributors_count": estimates["contributors_count"],
            "workflows_count": estimates["workflows_count"],
            "discussions_count": estimates["discussions_count"],
            "estimated_requests": chosen_estimate,
            "estimated_requests_rest": estimates["estimated_requests_rest"],
            "estimated_requests_pat": estimates["estimated_requests_pat"],
            "above_limit": is_large
        }

    except Exception as e:
        error_msg = str(e)
        print(f"[Verify] Exception during repository verification: {error_msg}")
        
        ok = False
        print(f"[VALIDATION]\nurl={url}\nowner={owner}\nrepo={repo_name}\nexists={exists}\nprivate={is_private}\nauthenticated={has_token}\nlarge_repo={is_large}\ncan_analyze={ok}")

        if "Bad credentials" in error_msg or "401" in error_msg:
            return {
                "ok": False,
                "status": "INVALID_PAT",
                "detail": "GitHub token is invalid or expired."
            }
        elif "NOT_FOUND" in error_msg or "404" in error_msg:
            return {
                "ok": False,
                "status": "NOT_FOUND",
                "detail": "Repository does not exist"
            }
        elif "forbidden" in error_msg.lower() or "403" in error_msg:
            if user_token:
                return {
                    "ok": False,
                    "status": "INVALID_PAT",
                    "detail": "Repository not found or PAT does not have access permissions. Verify PAT scopes."
                }
            else:
                return {
                    "ok": False,
                    "status": "PRIVATE_REPO_PAT_REQUIRED",
                    "detail": "Private repositories require a GitHub Personal Access Token."
                }
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            if user_token:
                return {
                    "ok": False,
                    "status": "INVALID_PAT",
                    "detail": "GitHub token is invalid or expired."
                }
            else:
                return {
                    "ok": False,
                    "status": "LARGE_REPO_PAT_REQUIRED",
                    "detail": "Large repository. PAT recommended for full analysis."
                }
        else:
            return {
                "ok": False,
                "status": "ERROR",
                "detail": f"Verification failed: {error_msg}"
            }


@router.get("/api/repositories")
async def get_repositories(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List repositories accessible to the current user (public repos + user's own private repos)."""
    try:
        from database.models import UserRepository
        if current_user:
            user_repo_ids_res = await db.execute(
                select(UserRepository.repo_id).where(UserRepository.user_id == current_user.id)
            )
            user_repo_ids = {row[0] for row in user_repo_ids_res.fetchall()}
            result = await db.execute(
                select(Repository).where(
                    (Repository.visibility == "public") | (Repository.id.in_(user_repo_ids))
                )
            )
        else:
            result = await db.execute(
                select(Repository).where(Repository.visibility == "public")
            )
        repos = result.scalars().all()
        res = []
        for r in repos:
            res.append({
                "id": r.id,
                "owner": r.owner,
                "name": r.name,
                "full_name": r.full_name,
                "url": r.url,
                "description": r.description,
                "language": r.language,
                "stars": r.stars,
                "visibility": r.visibility,
                "sync_status": r.sync_status,
                "initial_sync_completed": r.initial_sync_completed,
                "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
                "total_prs": r.total_prs,
                "total_issues": r.total_issues,
                "total_branches": r.total_branches,
                "total_forks": r.total_forks,
                "total_workflow_runs": r.total_workflow_runs,
                "total_discussions": r.total_discussions,
                "total_projects": getattr(r, "total_projects", 0) or 0,
                "expected_prs": normalize_telemetry_counts(r.synced_prs, r.expected_prs)[1],
                "expected_issues": normalize_telemetry_counts(r.synced_issues, r.expected_issues)[1],
                "expected_forks": normalize_telemetry_counts(r.synced_forks, r.expected_forks)[1],
                "expected_workflows": normalize_telemetry_counts(r.synced_workflows, r.expected_workflows)[1],
                "synced_prs": normalize_telemetry_counts(r.synced_prs, r.expected_prs)[0],
                "synced_issues": normalize_telemetry_counts(r.synced_issues, r.expected_issues)[0],
                "synced_forks": normalize_telemetry_counts(r.synced_forks, r.expected_forks)[0],
                "synced_workflows": normalize_telemetry_counts(r.synced_workflows, r.expected_workflows)[0],
            })
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve repositories.")

@router.post("/api/analyze")
@limiter.limit(config.ANALYZE_RATE_LIMIT)
async def analyze_repository(
    request: Request,
    payload: RepositoryRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """Trigger full repository ingestion via SyncEngine (background)."""
    try:
        url = payload.url.strip()
        owner, repo_name = parse_github_repo_url(url)
        canonical_url = normalize_github_url(owner, repo_name)
        token = (payload.github_token or "").strip() or None
        print(f"[AUTH AUDIT] api/analyze: token_present={bool(token)}")
        sync_mode = (payload.sync_mode or "").strip() or None

        # Extract authenticated user (optional)
        current_user = None
        if authorization or request.cookies.get("accessToken"):
            from api.dependencies import _extract_user
            current_user = await _extract_user(request, authorization, db)

        result = await db.execute(
            select(Repository).where(
                (Repository.owner == owner) & (Repository.name == repo_name)
            )
        )
        repo = result.scalar_one_or_none()

        if not repo:
            full_name = f"{owner}/{repo_name}"
            repo = Repository(
                owner=owner,
                name=repo_name,
                full_name=full_name,
                url=canonical_url,
                source_url=url,
                stars=0,
                sync_status="PENDING",
                sync_progress="Enqueuing background ingestion job...",
                visibility="private"  # SECURITY: Fail closed. Assume private until SyncEngine verifies it's public.
            )
            db.add(repo)
            await db.flush()
            await db.refresh(repo)
        else:
            repo.sync_status = "PENDING"
            repo.sync_progress = "Enqueuing background ingestion job..."
        
        await db.commit()
        await db.refresh(repo)

        # Associate repo with authenticated user
        if current_user:
            from database.models import UserRepository
            result = await db.execute(
                select(UserRepository).where(
                    (UserRepository.user_id == current_user.id) & (UserRepository.repo_id == repo.id)
                )
            )
            existing_assoc = result.scalar_one_or_none()
            
            if not existing_assoc:
                assoc = UserRepository(
                    user_id=current_user.id,
                    repo_id=repo.id,
                    role="owner",
                )
                db.add(assoc)
                await db.commit()

        background_tasks.add_task(run_background_sync, url, token, sync_mode)

        return {
            "owner": owner,
            "repo": repo_name,
            "repo_id": repo.id,
            "sync_status": repo.sync_status,
            "sync_progress": repo.sync_progress,
            "message": "Full repository ingestion started in background.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid request parameters.")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to start repository analysis. Please try again.")


@router.get("/api/sync-status/{repo_id}")
async def get_sync_status(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get sync status, progress (with ETA), and per-module record counts."""
    from datetime import datetime, timedelta, timezone
    from config import SYNC_INTERVAL_MINUTES

    repo = await require_repo_access(repo_id, current_user, db)
    
    # Count contributors dynamically
    contrib_count_res = await db.execute(select(func.count(Contributor.id)).where(Contributor.repo_id == repo_id))
    contrib_count = contrib_count_res.scalar() or 0

    # Helper to ensure ISO string has timezone info
    def to_iso_with_tz(dt):
        if not dt:
            return None
        # If datetime is naive, treat as UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    
    # Calculate next sync time
    if repo.last_successful_sync:
        next_sync_at = repo.last_successful_sync + timedelta(minutes=SYNC_INTERVAL_MINUTES)
    else:
        next_sync_at = None
    
    return {
        "id": repo.id,
        "owner": repo.owner,
        "name": repo.name,
        "full_name": repo.full_name,
        "sync_status": repo.sync_status,
        "sync_mode": getattr(repo, "sync_mode", "full") or "full",
        "sync_progress": repo.sync_progress,
        "sync_duration": repo.sync_duration,
        "sync_started_at": to_iso_with_tz(getattr(repo, "sync_started_at", None)),
        "initial_sync_completed": repo.initial_sync_completed,
        "last_synced_at": to_iso_with_tz(repo.last_synced_at),
        "last_successful_sync": to_iso_with_tz(repo.last_successful_sync),
        "next_sync_at": to_iso_with_tz(next_sync_at),
        "error_message": repo.error_message,
        "total_prs": repo.total_prs,
        "total_issues": repo.total_issues,
        "total_branches": repo.total_branches,
        "total_forks": repo.total_forks,
        "total_workflow_runs": repo.total_workflow_runs,
        "total_discussions": repo.total_discussions,
        "total_projects": getattr(repo, "total_projects", 0) or 0,
        "total_contributors": contrib_count,
        "expected_prs": normalize_telemetry_counts(repo.synced_prs, repo.expected_prs)[1],
        "expected_issues": normalize_telemetry_counts(repo.synced_issues, repo.expected_issues)[1],
        "expected_forks": normalize_telemetry_counts(repo.synced_forks, repo.expected_forks)[1],
        "expected_workflows": normalize_telemetry_counts(repo.synced_workflows, repo.expected_workflows)[1],
        "synced_prs": normalize_telemetry_counts(repo.synced_prs, repo.expected_prs)[0],
        "synced_issues": normalize_telemetry_counts(repo.synced_issues, repo.expected_issues)[0],
        "synced_forks": normalize_telemetry_counts(repo.synced_forks, repo.expected_forks)[0],
        "synced_workflows": normalize_telemetry_counts(repo.synced_workflows, repo.expected_workflows)[0],
        "rate_limit_remaining": repo.rate_limit_remaining,
        "rate_limit_limit": repo.rate_limit_limit,
        "rate_limit_reset": to_iso_with_tz(repo.rate_limit_reset),
    }


# ---------------------------------------------------------------------------
# MODULE 1 — PULL REQUEST INTELLIGENCE
# ---------------------------------------------------------------------------

@router.get("/api/kpi/{repo_id}")
async def get_kpi(
    repo_id: int,
    days: Optional[int] = None,
    author: Optional[str] = None,
    state: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """PR KPI summary."""
    await require_repo_access(repo_id, current_user, db)
    ext = ExtendedAnalytics(db)
    return await ext.get_kpi_with_duration(repo_id, days, author, state, start_date, end_date)


@router.get("/api/oldest-prs/{repo_id}")
async def get_oldest_prs(
    repo_id: int, page: int = 1, limit: int = 10,
    days: Optional[int] = None, author: Optional[str] = None,
    start_date: Optional[str] = None, end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    await require_repo_access(repo_id, current_user, db)
    ext = ExtendedAnalytics(db)
    return await ext.get_oldest_open_filtered(repo_id, page=page, limit=limit, days=days, author=author,
                                        start_date=start_date, end_date=end_date)


@router.get("/api/slowest-prs/{repo_id}")
async def get_slowest_prs(
    repo_id: int, page: int = 1, limit: int = 10,
    days: Optional[int] = None, author: Optional[str] = None,
    start_date: Optional[str] = None, end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    await require_repo_access(repo_id, current_user, db)
    ext = ExtendedAnalytics(db)
    return await ext.get_slowest_merged_filtered(repo_id, page=page, limit=limit, days=days, author=author,
                                           start_date=start_date, end_date=end_date)


@router.get("/api/contributor-activity/{repo_id}")
async def get_contributor_activity(
    repo_id: int, page: int = 1, limit: int = 10,
    days: Optional[int] = None, author: Optional[str] = None,
    state: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    await require_repo_access(repo_id, current_user, db)
    ext = ExtendedAnalytics(db)
    return await ext.get_contributors_filtered(repo_id, page=page, limit=limit, days=days, author=author,
                                         state=state, start_date=start_date, end_date=end_date)


@router.get("/api/monthly-flow/{repo_id}")
async def get_monthly_flow(
    repo_id: int, months: int = 6, days: Optional[int] = None,
    author: Optional[str] = None, state: Optional[str] = None,
    start_date: Optional[str] = None, end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    await require_repo_access(repo_id, current_user, db)
    ext = ExtendedAnalytics(db)
    return await ext.get_monthly_flow_filtered(repo_id, months, days=days, author=author,
                                         state=state, start_date=start_date, end_date=end_date)


@router.get("/api/throughput/{repo_id}")
async def get_throughput(
    repo_id: int, weeks: int = 8, days: Optional[int] = None,
    author: Optional[str] = None, state: Optional[str] = None,
    start_date: Optional[str] = None, end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    await require_repo_access(repo_id, current_user, db)
    ext = ExtendedAnalytics(db)
    return await ext.get_throughput_filtered(repo_id, weeks, days=days, author=author,
                                       state=state, start_date=start_date, end_date=end_date)


@router.get("/api/authors/{repo_id}")
async def get_authors(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    await require_repo_access(repo_id, current_user, db)
    ext = ExtendedAnalytics(db)
    return {"authors": await ext.get_authors(repo_id)}


@router.get("/api/pr-risk/{repo_id}")
async def get_pr_risk(
    repo_id: int,
    page: int = 1,
    limit: int = 15,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    await require_repo_access(repo_id, current_user, db)
    ext = ExtendedAnalytics(db)
    return await ext.get_pr_risk_panel(repo_id, page=page, limit=limit)


@router.post("/api/refresh-ml/{repo_id}")
async def refresh_ml_predictions(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Trigger ML inference for all open PRs of a repository.

    Runs synchronously in the request thread. Returns the count of PRs
    that received new predictions.  Safe to call after a re-sync or
    manually from the Settings panel.
    """
    from database.models import MLPrediction
    await require_repo_access(repo_id, current_user, db)

    try:
        processor = DataProcessor(db)
        ml_models = processor._get_ml_models()
        if not ml_models:
            return {
                "refreshed": 0,
                "reason": "ML models unavailable — no .pkl files found.",
                "models_exist": False,
            }
        count = processor.refresh_ml_predictions(repo_id=repo_id, only_open_prs=True)
        return {
            "refreshed": count,
            "models_exist": True,
            "reason": f"Refreshed {count} open PR prediction(s) successfully.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="ML prediction refresh failed. Please try again.")


@router.get("/api/ml-status/{repo_id}")
async def get_ml_status(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Return ML readiness diagnostics for a repository.

    Used by the frontend to render informative empty-state messages
    in the PR Risk & Delay Predictions panel.
    """
    from database.models import MLPrediction, PullRequest as PR
    from ml.models import MLModels

    await require_repo_access(repo_id, current_user, db)

    result = await db.execute(select(func.count(PR.id)).where(PR.repo_id == repo_id, PR.state == "OPEN"))
    open_prs = result.scalar() or 0
    
    result = await db.execute(
        select(func.count(PR.id)).select_from(PR)
        .join(MLPrediction, PR.id == MLPrediction.pr_id)
        .where(PR.repo_id == repo_id, PR.state == "OPEN")
    )
    prs_with_predictions = result.scalar() or 0

    ml_models = MLModels()
    models_exist = ml_models.models_exist()

    reasons = []
    if not models_exist:
        reasons.append("ML model files not found — run training first.")
    if open_prs == 0:
        reasons.append("No open PRs in this repository.")
    elif prs_with_predictions == 0 and models_exist:
        reasons.append("Models loaded but no predictions stored yet — try refreshing ML.")

    return {
        "open_prs": open_prs,
        "prs_with_predictions": prs_with_predictions,
        "models_exist": models_exist,
        "ready": prs_with_predictions > 0,
        "reasons": reasons,
    }



@router.get("/api/stale-alerts/{repo_id}")
async def get_stale_alerts(
    repo_id: int,
    page: int = 1,
    limit: int = 10,
    stale_days: int = Query(default=30, description="Stale threshold in days"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    await require_repo_access(repo_id, current_user, db)
    ext = ExtendedAnalytics(db)
    return await ext.get_stale_recommendations(repo_id, page=page, limit=limit, stale_days=stale_days)


# ---------------------------------------------------------------------------
# MODULE 2 — ISSUE INTELLIGENCE
# ---------------------------------------------------------------------------

@router.get("/api/issues/{repo_id}")
async def get_issues(
    repo_id: int, page: int = 1, limit: int = 20,
    state: str = "all", label: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "created_at",
    sort_dir: str = "desc",
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Paginated issue list."""
    await require_repo_access(repo_id, current_user, db)
    return await IssueAnalytics(db).get_issues_list(repo_id, state=state, page=page, limit=limit, label=label, search=search, sort=sort, sort_dir=sort_dir)


@router.get("/api/issues/analytics/{repo_id}")
async def get_issues_analytics(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Issue analytics summary."""
    await require_repo_access(repo_id, current_user, db)
    ia = IssueAnalytics(db)
    return {
        "summary": await ia.get_summary(repo_id),
        "velocity": await ia.get_resolution_velocity(repo_id),
        "heatmap": await ia.get_issue_heatmap(repo_id),
        "priority": await ia.get_priority_distribution(repo_id),
    }


@router.get("/api/issues/stale/{repo_id}")
async def get_stale_issues(
    repo_id: int, stale_days: int = 30, page: int = 1, limit: int = 20,
    search: Optional[str] = None,
    sort: str = "created_at",
    sort_dir: str = "asc",
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    await require_repo_access(repo_id, current_user, db)
    return await IssueAnalytics(db).get_stale_issues(repo_id, stale_days=stale_days, page=page, limit=limit, search=search, sort=sort, sort_dir=sort_dir)


# ---------------------------------------------------------------------------
# MODULE 3 — BRANCH INTELLIGENCE
# ---------------------------------------------------------------------------

@router.get("/api/branches/{repo_id}")
async def get_branches(
    repo_id: int, page: int = 1, limit: int = 20,
    filter_type: str = "all",
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Paginated branch list."""
    await require_repo_access(repo_id, current_user, db)
    return await BranchAnalytics(db).get_branches_list(repo_id, page=page, limit=limit, filter_type=filter_type)


@router.get("/api/branches/analytics/{repo_id}")
async def get_branches_analytics(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Branch analytics summary."""
    await require_repo_access(repo_id, current_user, db)
    return await BranchAnalytics(db).get_summary(repo_id)


# ---------------------------------------------------------------------------
# MODULE 5 — FORK ANALYTICS
# ---------------------------------------------------------------------------

@router.get("/api/forks/{repo_id}")
async def get_forks(
    repo_id: int, page: int = 1, limit: int = 20,
    filter_type: str = "all",
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Paginated fork list."""
    await require_repo_access(repo_id, current_user, db)
    return await ForkAnalytics(db).get_forks_list(repo_id, page=page, limit=limit, filter_type=filter_type)


@router.get("/api/forks/analytics/{repo_id}")
async def get_forks_analytics(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Fork analytics summary."""
    await require_repo_access(repo_id, current_user, db)
    fa = ForkAnalytics(db)
    return {
        "summary": await fa.get_summary(repo_id),
        "growth_trend": await fa.get_growth_trend(repo_id),
    }


# ---------------------------------------------------------------------------
# MODULE 8 — CI/CD INTELLIGENCE
# ---------------------------------------------------------------------------

@router.get("/api/cicd/analytics/{repo_id}")
async def get_cicd_analytics(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """CI/CD analytics summary."""
    await require_repo_access(repo_id, current_user, db)
    ca = CICDAnalytics(db)
    return {
        "summary": await ca.get_summary(repo_id),
        "workflow_breakdown": await ca.get_workflow_breakdown(repo_id),
        "success_trend": await ca.get_success_trend(repo_id, days=30),
    }


@router.get("/api/workflow-runs/{repo_id}")
async def get_workflow_runs(
    repo_id: int, page: int = 1, limit: int = 20,
    conclusion: Optional[str] = None, branch: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Paginated workflow runs."""
    await require_repo_access(repo_id, current_user, db)
    return await CICDAnalytics(db).get_runs_list(repo_id, page=page, limit=limit,
                                           conclusion=conclusion, branch=branch)


# ---------------------------------------------------------------------------
# MODULE 6 — DISCUSSION ANALYTICS
# ---------------------------------------------------------------------------

@router.get("/api/discussions/{repo_id}")
async def get_discussions(
    repo_id: int,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Paginated discussions list."""
    await require_repo_access(repo_id, current_user, db)
    return await DiscussionAnalytics(db).get_discussions_list(repo_id, page=page, limit=limit)


@router.get("/api/discussions/analytics/{repo_id}")
async def get_discussions_analytics(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Discussion analytics summary."""
    await require_repo_access(repo_id, current_user, db)
    return await DiscussionAnalytics(db).get_summary(repo_id)

@router.get("/api/discussions/timeline/{repo_id}")
async def get_discussions_timeline(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Discussion activity timeline over time."""
    await require_repo_access(repo_id, current_user, db)
    return await DiscussionAnalytics(db).get_activity_timeline(repo_id)


# ---------------------------------------------------------------------------
# MODULE 7 — PROJECT ANALYTICS
# ---------------------------------------------------------------------------

@router.get("/api/projects/{repo_id}")
async def get_projects(
    repo_id: int,
    page: int = 1,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Paginated projects list."""
    await require_repo_access(repo_id, current_user, db)
    return await ProjectAnalytics(db).get_projects_list(repo_id, page=page, limit=limit)


@router.get("/api/projects/analytics/{repo_id}")
async def get_projects_analytics(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Project analytics summary."""
    await require_repo_access(repo_id, current_user, db)
    return await ProjectAnalytics(db).get_summary(repo_id)


# ---------------------------------------------------------------------------
# MODULE 9 — REPOSITORY HEALTH
# ---------------------------------------------------------------------------

@router.get("/api/repo-health/{repo_id}")
async def get_repo_health(
    repo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Aggregate repository health score across all modules."""
    await require_repo_access(repo_id, current_user, db)
    return await RepoHealthAnalytics(db).get_health_score(repo_id)


# ---------------------------------------------------------------------------
# ML MODELS
# ---------------------------------------------------------------------------

@router.get("/api/ml-status")
async def get_ml_status_global(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ml_models = MLModels()
    return {
        "models_exist": ml_models.models_exist(),
        "model_files": [str(p.name) for p in ml_models.models_dir.glob("*.pkl")],
        "models_dir": str(ml_models.models_dir),
    }


@router.post("/api/train-ml")
async def train_ml_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        ml_models = MLModels()
        result = await ml_models.train_from_db(db)
        prediction_refresh_count = 0
        if result.get("trained"):
            processor = DataProcessor(db)
            prediction_refresh_count = processor.refresh_ml_predictions(only_open_prs=False)
        return {
            "trained": result.get("trained", False),
            "summary": result.get("summary", []),
            "models": result.get("models", {}),
            "predictions_refreshed": prediction_refresh_count,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail="ML training failed. Please check server logs.")


# ---------------------------------------------------------------------------
# EXPORT
# ---------------------------------------------------------------------------

@router.get("/api/export/{repo_id}")
async def export_report(
    repo_id: int, days: Optional[int] = None, author: Optional[str] = None,
    state: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    try:
        await require_repo_access(repo_id, current_user, db)
        ext = ExtendedAnalytics(db)
        csv_content = await ext.build_export_csv(repo_id, days, author, state, start_date, end_date)
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=prism_report_{repo_id}.csv"},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid request parameters.")


@router.get("/api/export-pdf/{repo_id}")
async def export_report_pdf(
    repo_id: int, days: Optional[int] = None, author: Optional[str] = None,
    state: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Generate a comprehensive PDF report by rendering the frontend UI page via Playwright."""
    try:
        repo = await require_repo_access(repo_id, current_user, db)

        # Build the frontend URL
        frontend_base = "http://localhost:3000"
        report_url = f"{frontend_base}/report/{repo_id}"

        # Build query parameters
        import urllib.parse
        params = []
        if days: params.append(f"days={days}")
        if author: params.append(f"author={urllib.parse.quote(author)}")
        if state: params.append(f"state={urllib.parse.quote(state)}")
        if start_date: params.append(f"start_date={urllib.parse.quote(start_date)}")
        if end_date: params.append(f"end_date={urllib.parse.quote(end_date)}")

        # Pass a token for authentication if current_user exists
        if current_user:
            access_token, _ = create_access_token({"sub": current_user.username, "email": current_user.email})
            params.append(f"token={access_token}")

        if params:
            report_url += "?" + "&".join(params)

        print(f"[PDF Export] Rendering UI page via Playwright: {report_url}")

        import sys
        import asyncio
        import httpx
        from playwright.sync_api import sync_playwright

        # ── Step 1: Pre-warm Next.js so the page is compiled before Playwright visits ──
        # On first request, Next.js dev server compiles the route which can take 30-60s.
        # We hit it with httpx (no timeout) so it's ready when Playwright loads it.
        try:
            print(f"[PDF Export] Pre-warming Next.js route: {report_url}")
            async with httpx.AsyncClient(timeout=None, follow_redirects=True) as warmup_client:
                warmup_resp = await warmup_client.get(report_url)
                print(f"[PDF Export] Pre-warm complete: HTTP {warmup_resp.status_code}")
        except Exception as warmup_err:
            print(f"[PDF Export] Pre-warm warning (non-fatal): {warmup_err}")

        # ── Step 2: Playwright captures PDF from the now-compiled page ──
        def capture_pdf_sync(url, result):
            try:
                if sys.platform == "win32":
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

                with sync_playwright() as p:
                    # Set no-timeout at context level (most reliable way on Windows)
                    browser = p.chromium.launch(headless=True)
                    ctx = browser.new_context()
                    ctx.set_default_navigation_timeout(0)
                    ctx.set_default_timeout(0)
                    page = ctx.new_page()

                    page.set_viewport_size({"width": 1200, "height": 1600})

                    # Page is already compiled — navigation will be fast now
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)

                    # Wait for client-side ReportReadyTrigger to signal rendering complete
                    try:
                        page.wait_for_selector('html[data-pdf-ready="true"]', timeout=30000)
                    except Exception as wait_err:
                        print(f"[PDF Export] data-pdf-ready not detected, proceeding: {wait_err}")

                    # Capture the PDF with print backgrounds preserved
                    pdf_data = page.pdf(
                        format="A4",
                        print_background=True,
                        margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
                        prefer_css_page_size=False
                    )
                    browser.close()
                    result["pdf_bytes"] = pdf_data
            except Exception as thread_err:
                result["error"] = thread_err

        pdf_result = {}
        # Run blocking Playwright in thread pool — keeps Uvicorn event loop free
        # so the pre-warm httpx request above can be served concurrently.
        await asyncio.to_thread(capture_pdf_sync, report_url, pdf_result)

        if "error" in pdf_result:
            raise pdf_result["error"]
        if "pdf_bytes" not in pdf_result:
            raise RuntimeError("PDF generation failed: browser returned no data")

        pdf_bytes = pdf_result["pdf_bytes"]
        filename = f"prism_report_{repo.owner}_{repo.name}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_bytes)),
            },
        )
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status_code, detail="Invalid request or repository not found.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="PDF report generation failed. Please try again.")


@router.get("/api/system-status")
async def get_system_status(
    validate_endpoints: bool = Query(default=False),
    repo_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        from services.validation import SystemIntegrityValidator, test_rest_endpoints
        
        result = await db.execute(select(func.count(Repository.id)))
        repo_count = result.scalar() or 0
        
        result = await db.execute(select(func.count(PullRequest.id)))
        pr_count = result.scalar() or 0
        
        result = await db.execute(select(func.count(Contributor.id)))
        contributor_count = result.scalar() or 0

        validator = SystemIntegrityValidator(db)
        validation_report = await validator.validate_all(repo_id=repo_id)

        endpoints_report = None
        if validate_endpoints:
            target_repo_id = repo_id
            if not target_repo_id:
                result = await db.execute(select(Repository).limit(1))
                first_repo = result.scalar_one_or_none()
                if first_repo:
                    target_repo_id = first_repo.id
            
            if target_repo_id:
                endpoints_report = test_rest_endpoints(target_repo_id)
            else:
                endpoints_report = {
                    "all_endpoints_ok": False,
                    "error": "No repositories available in the database to test endpoints against."
                }

        status_flag = "healthy"
        if validation_report.get("status") == "warnings" or (endpoints_report and not endpoints_report.get("all_endpoints_ok")):
            status_flag = "warnings"

        return {
            "status": status_flag,
            "platform": "PRISM — GitHub Engineering Intelligence",
            "version": "2.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "status": "connected",
                "repositories": repo_count,
                "pull_requests": pr_count,
                "contributors": contributor_count,
            },
            "modules": [
                "pull_requests", "issues", "branches", "repository_metadata",
                "forks", "discussions", "projects", "cicd", "visibility"
            ],
            "validation": validation_report,
            "endpoints_check": endpoints_report
        }
    except Exception as e:
        import logging
        logging.error(f"System status error: {e}")
        return {"status": "error", "error": "Internal server error.", "timestamp": datetime.now(timezone.utc).isoformat()}

@router.post("/api/compare")
async def compare_repositories_post(
    payload: CompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Compare two repositories side by side using already-synced data.

    Both repositories must have been previously synced via the /api/analyze
    endpoint. This endpoint does NOT trigger a new sync; it only reads from
    the database to avoid running the legacy PR-only DataProcessor.
    """
    try:
        from services.data_processor import parse_github_repo_url, normalize_github_url
        owner_a, name_a = parse_github_repo_url(payload.url_a)
        owner_b, name_b = parse_github_repo_url(payload.url_b)

        result = await db.execute(
            select(Repository).where(
                (Repository.owner == owner_a) & (Repository.name == name_a)
            )
        )
        repo_a = result.scalar_one_or_none()
        
        result = await db.execute(
            select(Repository).where(
                (Repository.owner == owner_b) & (Repository.name == name_b)
            )
        )
        repo_b = result.scalar_one_or_none()

        if not repo_a:
            raise HTTPException(
                status_code=404,
                detail=f"Repository '{owner_a}/{name_a}' has not been synced yet. "
                       "Please sync it via the Analyze page first."
            )
        if not repo_b:
            raise HTTPException(
                status_code=404,
                detail=f"Repository '{owner_b}/{name_b}' has not been synced yet. "
                       "Please sync it via the Analyze page first."
            )

        # Enforce access control for both repositories
        await require_repo_access(repo_a.id, current_user, db)
        await require_repo_access(repo_b.id, current_user, db)

        ext = ExtendedAnalytics(db)
        return await ext.compare_repos(repo_a.id, repo_b.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail="Repository comparison failed. Please check the repository URLs.")
