from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
import os

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(user_id: str) -> str:
    # Timezone-aware UTC: python-jose serializes a naive datetime as if it were
    # UTC, so datetime.now() (naive local time) would shift the real expiry by
    # the host's UTC offset. Anchoring to UTC keeps the 1-day window correct on
    # any host, regardless of its local timezone.
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> str:
    """Returns user_id string or raises 401."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    """FastAPI dependency — use this on any protected route."""
    return decode_token(token)


def get_current_admin(user_id: str = Depends(get_current_user_id)) -> str:
    """FastAPI dependency — gate a route to admin users only.

    Builds on get_current_user_id (a valid, unexpired JWT) and then checks the
    is_admin flag for that user. The token itself carries only `sub`, so admin
    status is read live from the DB — this means demoting a user takes effect
    immediately without waiting for their token to expire.
    """
    # Imported lazily so this auth module has no import-time DB dependency
    # (keeps it importable in contexts — e.g. token unit tests — with no DB).
    from DBConnection import get_connection
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="Could not verify admin status.")
    if not row or not row.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    return user_id