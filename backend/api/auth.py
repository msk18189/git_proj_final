import os
import re
import jwt
from datetime import datetime, timezone, timedelta
import bcrypt
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
import secrets

from config import (
    JWT_SECRET,
    PASSWORD_MIN_LENGTH,
    PASSWORD_REQUIRE_UPPERCASE,
    PASSWORD_REQUIRE_LOWERCASE,
    PASSWORD_REQUIRE_DIGITS,
    PASSWORD_REQUIRE_SPECIAL,
)

# Algorithm configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  
REFRESH_TOKEN_EXPIRE_DAYS = 7

# ── Password Validation Function ──
def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password meets complexity requirements.
    Returns (is_valid, error_message).
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, (
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long. "
            f"Current length: {len(password)}"
        )
    
    if PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter (A-Z)"
    
    if PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter (a-z)"
    
    if PASSWORD_REQUIRE_DIGITS and not re.search(r"\d", password):
        return False, "Password must contain at least one digit (0-9)"
    
    if PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\,.<>?/]', password):
        return False, (
            "Password must contain at least one special character "
            "(!@#$%^&*()_+-=[]{};':,.<>?/)"
        )
    
    return True, ""

class UserSignup(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH)
    confirm_password: Optional[str] = None
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password complexity requirements."""
        is_valid, error_msg = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v

class UserLogin(BaseModel):
    username_or_email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    username: str
    email: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# Password hashing helpers
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

# JWT Token helpers
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> tuple[str, int]:
    """Create an access token and return (token, expires_in_seconds)."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    expires_in = int(expires_delta.total_seconds()) if expires_delta else ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return encoded_jwt, expires_in

def create_refresh_token_value() -> str:
    """Generate a random refresh token value (stored in database)."""
    return secrets.token_urlsafe(32)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        # Verify it's an access token, not something else
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.PyJWTError:
        return None
