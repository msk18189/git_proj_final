from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, inspect
from sqlalchemy.orm import declarative_base
import os
from urllib.parse import quote_plus

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "github_analytics")

    encoded_password = quote_plus(DB_PASSWORD)

    if DB_PASSWORD:
        SQLALCHEMY_DATABASE_URL = (
            f"mysql+asyncmy://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    else:
        SQLALCHEMY_DATABASE_URL = (
            f"mysql+asyncmy://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
else:
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "github_analytics")

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,
    pool_pre_ping=False,  # Disabled: SQLAlchemy 2.0.23 pymysql dialect ping() incompatible with aiomysql
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

async def _create_database_async():
    """
    Create MySQL database if it doesn't exist.
    Called asynchronously during FastAPI startup.
    Must be awaited in an existing event loop.
    """
    try:
        import aiomysql
        
        conn = await aiomysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD or None,
            port=int(DB_PORT),
        )
        
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
                await conn.commit()
            print(f"[DB] Verified/created MySQL database '{DB_NAME}'")
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[DB Warning] Could not verify/create database '{DB_NAME}': {e}")


async def init_db():
    """
    Initialize database schema and tables.
    Called during FastAPI startup event.
    
    Flow:
    1. Create database if needed (via _create_database_async)
    """
    # Step 1: Create database (async operation)
    await _create_database_async()
    
    print("[DB] Database existence verified successfully.")

    # Step 2: Import models to register them with Base.metadata
    from . import models
    print("[DB] Registered tables in metadata:", list(Base.metadata.tables.keys()))

    # Step 3: Create all tables asynchronously
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Step 4: Verify created tables using SHOW TABLES
    async with engine.connect() as conn:
        result = await conn.execute(text("SHOW TABLES;"))
        tables = [row[0] for row in result.fetchall()]
        print("[DB] Actual tables in database after create_all:", tables)

    # Step 5: Automatically recover/reset any stuck syncs
    try:
        from database.models import Repository, PullRequest
        from sqlalchemy import select, func
        async with async_session_maker() as session:
            stuck_repos_res = await session.execute(
                select(Repository).where(Repository.sync_status.in_(["SYNCING", "PENDING", "VERIFYING"]))
            )
            stuck_repos = stuck_repos_res.scalars().all()
            if stuck_repos:
                print(f"[DB] Found {len(stuck_repos)} repositories stuck in syncing states on startup. Recovering...")
                for r in stuck_repos:
                    pr_count_res = await session.execute(
                        select(func.count(PullRequest.id)).where(PullRequest.repo_id == r.id)
                    )
                    pr_count = pr_count_res.scalar() or 0
                    if pr_count > 0:
                        r.sync_status = "COMPLETED"
                        r.initial_sync_completed = True
                        r.sync_progress = "Sync completed (recovered after server restart)"
                        print(f"  * Repo {r.owner}/{r.name} reset to COMPLETED ({pr_count} PRs found)")
                    else:
                        r.sync_status = "FAILED"
                        r.sync_progress = "Sync failed: Interrupted by server restart"
                        r.error_message = "Sync was interrupted before any data could be fetched. Please sync again."
                        print(f"  * Repo {r.owner}/{r.name} reset to FAILED (no PRs found)")
                await session.commit()
                print("[DB] Stuck sync states recovered successfully.")
    except Exception as recovery_err:
        print(f"[DB Warning] Stuck sync recovery failed: {recovery_err}")




async def get_db():
    """Async database session dependency for FastAPI routes."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()