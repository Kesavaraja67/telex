"""
GitHub OAuth callback — creates/updates users row and manages authentication sessions.
"""
import logging
import secrets
import uuid
from typing import Optional
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import RedirectResponse
import httpx
from jose import jwt, JWTError

from db.session import AsyncSessionLocal
from db.models import User
from config import settings
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

# Shared client timeout for all GitHub HTTP requests
_GITHUB_TIMEOUT = httpx.Timeout(10.0)

JWT_ALGORITHM = "HS256"


# ── Auth dependency ─────────────────────────────────────────────────────────
# Import this in any router that must be protected:
#   from routers.auth import require_auth
#   @router.get("/protected", dependencies=[Depends(require_auth)])
#
# Payment-facing endpoints (create-order, verify-signature, webhook) must
# remain open because Aura Drops customers are anonymous.

async def require_auth(request: Request) -> dict:
    """
    FastAPI dependency — raises 401 if the request has no valid session token.
    Checks:
      1. Cookie: telex_session
      2. Header: Authorization: Bearer <token>
      3. Header: X-Demo-Key (matched against settings.demo_key)
    """
    # 1. Cookie
    token = request.cookies.get("telex_session")

    # 2. Authorization Header
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    # 3. Demo Key header (for demo/evaluator script access)
    demo_key = request.headers.get("x-demo-key")
    if demo_key and settings.demo_key and demo_key == settings.demo_key:
        return {"user_id": "demo-operator", "role": "operator"}

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id_str = decode_session_token(token)
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return {"user_id": user_id_str}



from datetime import datetime, timedelta, timezone

def _get_jwt_secret() -> str:
    if not settings.nextauth_secret:
        raise RuntimeError("NEXTAUTH_SECRET is not configured")
    return settings.nextauth_secret


def create_session_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=30)).timestamp()),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def is_safe_redirect(url_str: str) -> bool:
    """Validate that redirect target is a safe relative path or explicitly allowed host."""
    if not url_str:
        return False
    if url_str.startswith("/") and not url_str.startswith("//"):
        return True
    try:
        parsed = urlparse(url_str)
        if parsed.scheme not in ("http", "https"):
            return False
        netloc = parsed.netloc.lower()
        if netloc.startswith("localhost:") or netloc == "localhost" or netloc.startswith("127.0.0.1:"):
            return True
        for allowed in settings.cors_origins:
            allowed_netloc = urlparse(allowed).netloc.lower()
            if allowed_netloc and netloc == allowed_netloc:
                return True
        return False
    except Exception:
        return False


@router.get("/github")
async def github_login(next_url: Optional[str] = Query(None, alias="next")):
    """Redirect the user to GitHub OAuth with optional post-login redirect state."""
    # Generate a CSRF nonce; store in cookie and embed in state
    nonce = secrets.token_urlsafe(24)
    query = urlencode(
        {
            "client_id": settings.github_oauth_client_id,
            "scope": "read:user,user:email",
            "state": f"{nonce}:{next_url or ''}",
        }
    )
    response = RedirectResponse(f"https://github.com/login/oauth/authorize?{query}")
    response.set_cookie(
        "telex_oauth_state",
        nonce,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=600,  # 10-minute window for the OAuth flow
    )
    return response


@router.get("/github/callback")
@router.get("/callback/github")
async def github_callback(code: str, request: Request, state: Optional[str] = None):
    """
    Exchange OAuth code for token, upsert user in database,
    set session cookie, and redirect to destination.
    """
    # ── CSRF validation ─────────────────────────────────────────────────────
    stored_nonce = request.cookies.get("telex_oauth_state", "")
    nonce_from_state = state.split(":", 1)[0] if state else ""
    next_url = state.split(":", 1)[1] if state and ":" in state else ""

    if stored_nonce and nonce_from_state:
        if not secrets.compare_digest(stored_nonce, nonce_from_state):
            raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF attack")

    # ── Exchange code for access token ───────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=_GITHUB_TIMEOUT) as client:
            token_resp = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_oauth_client_id,
                    "client_secret": settings.github_oauth_client_secret,
                    "code": code,
                },
            )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="GitHub OAuth token exchange failed")
        token_data = token_resp.json()
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="GitHub OAuth token exchange failed") from exc

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="GitHub OAuth token exchange failed")

    # ── Fetch user profile from GitHub ───────────────────────────────────────
    try:
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=_GITHUB_TIMEOUT,
        ) as client:
            user_resp = await client.get(GITHUB_USER_URL)
        if user_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch GitHub user profile")
        user_data = user_resp.json()
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Failed to fetch GitHub user profile") from exc

    github_id = user_data.get("id")
    user_login = user_data.get("login")
    user_email = user_data.get("email")
    avatar_url = user_data.get("avatar_url")

    if not github_id or not user_login:
        raise HTTPException(status_code=502, detail="Incomplete GitHub user profile")

    # ── Upsert user in database ──────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.github_id == github_id).limit(1)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                github_id=github_id,
                github_login=user_login,
                email=user_email,
                avatar_url=avatar_url,
            )
            session.add(user)
            await session.flush()
            logger.info("auth: created new user %s (github_id=%d)", user_login, github_id)
        else:
            user.github_login = user_login
            user.email = user_email
            user.avatar_url = avatar_url
            logger.info("auth: updated existing user %s (github_id=%d)", user_login, github_id)

        await session.commit()
        user_id_str = str(user.id)

    # ── Build redirect response with session cookie ──────────────────────────
    import os
    web_base = settings.web_app_url if settings.web_app_url and settings.web_app_url != "http://localhost:3000" else (
        "https://telex-pi.vercel.app" if os.getenv("RENDER") or os.getenv("ENVIRONMENT") == "production" else "http://localhost:3000"
    )

    if next_url == "install":
        redirect_url = f"https://github.com/apps/{settings.github_app_slug}/installations/new"
    elif next_url and is_safe_redirect(next_url):
        redirect_url = next_url
    else:
        redirect_url = f"{web_base}/dashboard?login={user_login}"

    response = RedirectResponse(url=redirect_url)
    # Clear the CSRF nonce — single-use
    response.delete_cookie("telex_oauth_state")

    # Set signed, httponly session token containing user id
    session_token = create_session_token(user_id_str)
    response.set_cookie(
        key="telex_session",
        value=session_token,
        max_age=60 * 60 * 24 * 30,  # 30 days
        httponly=True,
        secure=True,
        samesite="lax",
    )
    # Set display cookie for client UI
    response.set_cookie(
        key="telex_user",
        value=user_login,
        max_age=60 * 60 * 24 * 30,
        httponly=False,
        samesite="lax",
    )
    return response


@router.get("/me")
async def get_current_user(request: Request):
    """Return the currently authenticated user based on signed session cookie."""
    token = request.cookies.get("telex_session")
    if not token:
        return {"authenticated": False, "user": None}

    user_id_str = decode_session_token(token)
    if not user_id_str:
        return {"authenticated": False, "user": None}

    try:
        user_uuid = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        return {"authenticated": False, "user": None}

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_uuid)
        if not user:
            return {"authenticated": False, "user": None}

        return {
            "authenticated": True,
            "user": {
                "id": str(user.id),
                "github_login": user.github_login,
                "email": user.email,
                "avatar_url": user.avatar_url,
            },
        }


@router.get("/logout")
async def logout():
    """Clear session cookie and redirect to home."""
    response = RedirectResponse(url=f"{settings.web_app_url}/")
    response.delete_cookie(key="telex_session")
    response.delete_cookie(key="telex_user")
    return response


async def require_current_user(request: Request) -> User:
    """Dependency to enforce authenticated user on protected routes."""
    token = request.cookies.get("telex_session")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id_str = decode_session_token(token)
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid session payload")

    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_uuid)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user


