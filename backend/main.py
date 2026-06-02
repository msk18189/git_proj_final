import os
import sys
import asyncio
from fastapi import FastAPI, Request
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request as StarletteRequest
from api.rate_limiter import limiter
from api.routes import router
from database.database import init_db
from config import CORS_ORIGINS, API_HOST, API_PORT, API_RELOAD, API_WORKERS

app = FastAPI(
    title="PRISM — GitHub Engineering Intelligence Platform",
    version="2.0.0",
    description="Enterprise-grade GitHub repository intelligence: PRs, Issues, Branches, CI/CD, Forks, Discussions, Projects",
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsProactorEventLoopPolicy()
    )

# Apply rate limiter to app state
app.state.limiter = limiter

# Rate limit exception handler
@app.exception_handler(RateLimitExceeded)
async def _custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."}
    )

class CustomSlowAPIMiddleware(SlowAPIMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next) -> Response:
        response = await super().dispatch(request, call_next)
        if response.status_code == 429:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )
        return response

# SlowAPI middleware for rate limiting (global limit)
app.add_middleware(CustomSlowAPIMiddleware)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Cookie", "X-Requested-With"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize database schema on application startup."""
    try:
        await init_db()
        print("[App] Database initialization completed successfully")
    except Exception as e:
        print(f"[App Error] Database initialization failed: {e}")
        raise e

# Include routes
app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    # Simple test route to verify DB connection on startup
    return {"message": "MySQL Connected Successfully"}

if __name__ == "__main__":
    import uvicorn
    print(f"Starting server on {API_HOST}:{API_PORT}")
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=API_RELOAD,
        workers=API_WORKERS,
        loop="asyncio",
        limit_concurrency=100,
        limit_max_requests=1000,
    )
