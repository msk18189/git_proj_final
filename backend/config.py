import os
import multiprocessing

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
GITHUB_REST_URL = "https://api.github.com"

DATABASE_URL = os.getenv("DATABASE_URL", "")

SYNC_BATCH_SIZE = int(os.getenv("SYNC_BATCH_SIZE", "300"))
SYNC_RATE_LIMIT_BUFFER = int(os.getenv("SYNC_RATE_LIMIT_BUFFER", "50"))
SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))

# ── Stale Resource Thresholds (Environment-Driven) ──
STALE_PR_DAYS = int(os.getenv("STALE_PR_DAYS", "30"))
STALE_ISSUE_DAYS = int(os.getenv("STALE_ISSUE_DAYS", "30"))
STALE_BRANCH_DAYS = int(os.getenv("STALE_BRANCH_DAYS", "90"))

# ── ML Models Configuration (Environment-Driven) ──
ML_MODELS_DIR = "ml/trained_models"
ML_CONTAMINATION = float(os.getenv("ML_CONTAMINATION", "0.1"))
ML_KMEANS_CLUSTERS = int(os.getenv("ML_KMEANS_CLUSTERS", "3"))

# ── API Server Configuration (Environment-Driven) ──
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))

_api_reload_raw = os.getenv("API_RELOAD", "false").lower().strip()
if _api_reload_raw not in ("true", "false"):
    raise ValueError(
        f"[FATAL] API_RELOAD must be 'true' or 'false' (case-insensitive), got: '{_api_reload_raw}'"
    )
API_RELOAD: bool = _api_reload_raw == "true"

try:
    _cpu_cores = multiprocessing.cpu_count()
    _default_workers = _cpu_cores * 2 + 1
except Exception:
    _default_workers = 4

if API_RELOAD:
    _default_workers = 1

_api_workers_raw = os.getenv("API_WORKERS", str(_default_workers)).strip()
try:
    _api_workers_int = int(_api_workers_raw)
except ValueError:
    raise ValueError(
        f"[FATAL] API_WORKERS must be a positive integer, got: '{_api_workers_raw}'"
    )

if _api_workers_int <= 0:
    raise ValueError(
        f"[FATAL] API_WORKERS must be > 0, got: {_api_workers_int}"
    )

# Auto-correct: reload mode requires exactly 1 worker
if API_RELOAD and _api_workers_int > 1:
    print(
        f"[Config Warning] API_RELOAD=true cannot be used with API_WORKERS={_api_workers_int}. "
        f"Auto-correcting to API_WORKERS=1 (reload mode requires single worker)."
    )
    API_WORKERS: int = 1
else:
    API_WORKERS: int = _api_workers_int

print(f"[Config] API Server: reload={API_RELOAD}, workers={API_WORKERS}")

_JWT_SECRET_MIN_LENGTH = 32

_jwt_secret_raw = os.getenv("JWT_SECRET")

if _jwt_secret_raw is None:
    raise EnvironmentError(
        "[FATAL] JWT_SECRET environment variable is required. "
        "Set it in your .env file or system environment before starting."
    )

if _jwt_secret_raw.strip() == "":
    raise EnvironmentError(
        "[FATAL] JWT_SECRET environment variable must not be empty. "
        "Provide a strong random secret of at least 32 characters."
    )

if len(_jwt_secret_raw.strip()) < _JWT_SECRET_MIN_LENGTH:
    raise ValueError(
        f"[FATAL] JWT_SECRET must be at least {_JWT_SECRET_MIN_LENGTH} characters long. "
        f"Current length: {len(_jwt_secret_raw.strip())} characters. "
        "Generate a strong secret with: "
        "python -c \"import secrets; print(secrets.token_hex(32))\""
    )

JWT_SECRET: str = _jwt_secret_raw.strip()

# ── Password Policy Configuration (Environment-Driven) ──
# Enforce strong password requirements for user accounts
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
PASSWORD_REQUIRE_UPPERCASE = os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
PASSWORD_REQUIRE_LOWERCASE = os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
PASSWORD_REQUIRE_DIGITS = os.getenv("PASSWORD_REQUIRE_DIGITS", "true").lower() == "true"
PASSWORD_REQUIRE_SPECIAL = os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"

# Validate password policy configuration
if PASSWORD_MIN_LENGTH < 6:
    raise ValueError(
        f"[FATAL] PASSWORD_MIN_LENGTH must be at least 6, got: {PASSWORD_MIN_LENGTH}"
    )

if PASSWORD_MIN_LENGTH < 12:
    print(
        f"[Config Warning] PASSWORD_MIN_LENGTH={PASSWORD_MIN_LENGTH} is below recommended 12. "
        f"Consider increasing to 12+ for production environments."
    )

_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")

CORS_ORIGINS = [
    origin.strip()
    for origin in _cors_origins_raw.split(",")
    if origin.strip()
]

if not CORS_ORIGINS:
    raise RuntimeError(
        "[FATAL] At least one CORS origin must be configured. "
        "Set CORS_ORIGINS in your .env file (comma-separated)."
    )

for _origin in CORS_ORIGINS:
    if not _origin.startswith(("http://", "https://")):
        raise RuntimeError(
            f"[FATAL] Invalid CORS origin: '{_origin}'. "
            "Each origin must start with http:// or https://."
        )

LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "5/minute")
SIGNUP_RATE_LIMIT = os.getenv("SIGNUP_RATE_LIMIT", "3/minute")
VERIFY_RATE_LIMIT = os.getenv("VERIFY_RATE_LIMIT", "20/minute")
ANALYZE_RATE_LIMIT = os.getenv("ANALYZE_RATE_LIMIT", "10/minute")
API_RATE_LIMIT = os.getenv("API_RATE_LIMIT", "60/minute")

_rate_limits = {
    "LOGIN_RATE_LIMIT": LOGIN_RATE_LIMIT,
    "SIGNUP_RATE_LIMIT": SIGNUP_RATE_LIMIT,
    "VERIFY_RATE_LIMIT": VERIFY_RATE_LIMIT,
    "ANALYZE_RATE_LIMIT": ANALYZE_RATE_LIMIT,
    "API_RATE_LIMIT": API_RATE_LIMIT
}

for _key, _val in _rate_limits.items():
    if not _val or not _val.strip():
        raise RuntimeError(f"[FATAL] {_key} cannot be empty. Configure it properly (e.g., '60/minute').")