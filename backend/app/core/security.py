import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from joserfc import jwt
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry

from app.core.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _signing_key() -> OctKey:
    """joserfc requires a JWK object, not a raw secret string."""
    secret = settings.JWT_SECRET
    if not secret:
        raise RuntimeError("JWT_SECRET is empty. Set it in backend/.env")
    return OctKey.import_key(secret)


def create_access_token(*, sub: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": sub,
        "email": email,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    header = {"alg": settings.JWT_ALGORITHM}
    return jwt.encode(header, payload, _signing_key())


def create_refresh_token() -> str:
    """Opaque refresh token stored in DB — not a JWT."""
    return secrets.token_urlsafe(48)


def decode_access_token(token: str) -> dict:
    decoded = jwt.decode(token, _signing_key())
    JWTClaimsRegistry().validate(decoded.claims)
    if decoded.claims.get("type") != "access":
        raise ValueError("Invalid token type")
    return dict(decoded.claims)
