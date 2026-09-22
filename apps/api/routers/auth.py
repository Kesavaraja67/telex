"""
GitHub OAuth callback — creates/updates users row and manages authentication sessions.
"""

import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from jose import JWTError, jwt
from sqlalchemy import select

from config import settings
from db.models import User
from db.session import AsyncSessionLocal

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


async def get_authorized_repo(
    session,
    repo_identifier: str,
    auth_data: dict,
) -> tuple:
    """
    Authorize that the requested repository belongs to an installation accessible
    to the authenticated user.
    Raises HTTPException(403) if access is denied, or HTTPException(404) if repo not found.
    Returns tuple (Repo, Installation).
    """
    from sqlalchemy import func, or_

    from db.models import Installation, Repo, User

    user_id_raw = auth_data.get("user_id") if isinstance(auth_data, dict) else None
    if not user_id_raw:
        raise HTTPException(status_code=401, detail="Authentication required")

    repo_uuid = None
    try:
        repo_uuid = uuid.UUID(repo_identifier)
    except (ValueError, TypeError):
        pass

    repo_filters = [Repo.full_name == repo_identifier]
    if repo_uuid is not None:
        repo_filters.append(Repo.id == repo_uuid)

    # In dev/demo environment fallback
    if user_id_raw in ("dev-user", "demo-operator"):
        res = await session.execute(
            select(Repo, Installation)
            .join(Installation, Repo.installation_id == Installation.id)
            .where(or_(*repo_filters))
            .limit(1)
        )
        row = res.first()
        if not row:
            raise HTTPException(status_code=404, detail="Repo not found")
        return row[0], row[1]

    try:
        user_uuid = uuid.UUID(str(user_id_raw))
    except (ValueError, TypeError):
        raise HTTPException(status_code=403, detail="Repository access denied")

    user_res = await session.execute(select(User).where(User.id == user_uuid))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=403, detail="Repository access denied")

    user_login = user.github_login.lower() if user.github_login else None

    inst_conditions = [Installation.installed_by == user_uuid]
    if user_login:
        inst_conditions.append(func.lower(Installation.account_login) == user_login)

    result = await session.execute(
        select(Repo, Installation)
        .join(Installation, Repo.installation_id == Installation.id)
        .where(
            or_(*repo_filters),
            or_(*inst_conditions),
        )
        .limit(1)
    )
    row = result.first()
    if row is None:
        # Check if repo exists to distinguish 403 Forbidden vs 404 Not Found
        exists = await session.execute(select(Repo.id).where(or_(*repo_filters)).limit(1))
        if exists.scalar_one_or_none() is not None:
            raise HTTPException(status_code=403, detail="Repository access denied")
        raise HTTPException(status_code=404, detail="Repo not found")

    return row[0], row[1]


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


def decode_session_token(token: str) -> str | None:
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
        if (
            netloc.startswith("localhost:")
            or netloc == "localhost"
            or netloc.startswith("127.0.0.1:")
            or netloc == "127.0.0.1"
        ):
            return True
        for allowed in settings.cors_origins:
            allowed_netloc = urlparse(allowed).netloc.lower()
            if allowed_netloc and netloc == allowed_netloc:
                return True
        if settings.web_app_url:
            web_netloc = urlparse(settings.web_app_url).netloc.lower()
            if web_netloc and netloc == web_netloc:
                return True
        return False
    except Exception:
        return False


def _resolve_web_base(request: Request | None = None) -> str:
    """Resolve the web dashboard base URL, ensuring production never redirects to localhost."""
    is_prod = bool(os.getenv("RENDER") or settings.environment.strip().lower() == "production")
    env_web = os.getenv("WEB_APP_URL") or settings.web_app_url
    if env_web and not (is_prod and "localhost" in env_web):
        return env_web.rstrip("/")
    if is_prod:
        if request:
            ref = request.headers.get("referer") or request.headers.get("origin")
            if ref:
                try:
                    p = urlparse(ref)
                    if p.netloc.endswith(".vercel.app") or "telex" in p.netloc:
                        return f"{p.scheme}://{p.netloc}"
                except Exception:
                    pass
        return "https://telex-web.vercel.app"
    return "http://localhost:3000"


@router.get("/github")
async def github_login(
    request: Request,
    next_url: str | None = Query(None, alias="next"),
    origin: str | None = Query(None),
):
    """Redirect the user to GitHub OAuth with optional post-login redirect state."""
    client_origin = origin
    if not client_origin:
        ref = request.headers.get("referer")
        if ref:
            try:
                p = urlparse(ref)
                if p.scheme and p.netloc:
                    candidate = f"{p.scheme}://{p.netloc}"
                    if is_safe_redirect(candidate):
                        client_origin = candidate
            except Exception:
                pass
    elif not is_safe_redirect(client_origin):
        client_origin = ""

    # If running locally (not in production) and the client is on localhost, redirect to dev-login
    is_prod = bool(os.getenv("RENDER") or settings.environment.strip().lower() == "production")
    client_host = request.url.hostname or ""
    if not is_prod and (
        client_host in ("localhost", "127.0.0.1")
        or (client_origin and "localhost" in client_origin)
    ):
        if request.query_params.get("force_oauth") != "1":
            return RedirectResponse(f"{request.base_url}api/auth/dev-login", status_code=307)

    # Generate a CSRF nonce; store in cookie and embed in state: nonce:next_url:client_origin
    nonce = secrets.token_urlsafe(24)
    state_payload = f"{nonce}:{next_url or ''}:{client_origin or ''}"
    query = urlencode(
        {
            "client_id": settings.github_oauth_client_id,
            "scope": "read:user,user:email",
            "state": state_payload,
        }
    )
    response = RedirectResponse(f"https://github.com/login/oauth/authorize?{query}")

    is_secure = request.url.scheme == "https" or bool(
        os.getenv("RENDER") or settings.environment == "production"
    )
    response.set_cookie(
        "telex_oauth_state",
        nonce,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=600,  # 10-minute window for the OAuth flow
    )
    return response


@router.get("/github/callback")
@router.get("/callback/github")
async def github_callback(code: str, request: Request, state: str | None = None):
    """
    Exchange OAuth code for token, upsert user in database,
    set session cookie, and redirect to destination.
    """
    # ── CSRF validation ─────────────────────────────────────────────────────
    stored_nonce = request.cookies.get("telex_oauth_state", "")
    parts = state.split(":", 2) if state else []
    nonce_from_state = parts[0] if len(parts) > 0 else ""
    next_url = parts[1] if len(parts) > 1 else ""
    origin_from_state = parts[2] if len(parts) > 2 else ""

    if stored_nonce and nonce_from_state:
        if not secrets.compare_digest(stored_nonce, nonce_from_state):
            raise HTTPException(
                status_code=400, detail="Invalid OAuth state — possible CSRF attack"
            )

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
        result = await session.execute(select(User).where(User.github_id == github_id).limit(1))
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

    # ── Build redirect response with session cookie & token fragment ─────────
    web_base = (
        origin_from_state
        if (origin_from_state and is_safe_redirect(origin_from_state))
        else _resolve_web_base(request)
    )

    session_token = create_session_token(user_id_str)

    if next_url == "install":
        redirect_url = f"https://github.com/apps/{settings.github_app_slug}/installations/new"
    elif next_url and is_safe_redirect(next_url):
        base_dest = f"{web_base}{next_url}" if next_url.startswith("/") else next_url
        redirect_url = f"{base_dest}#token={session_token}"
    else:
        redirect_url = f"{web_base}/dashboard#token={session_token}"

    response = RedirectResponse(url=redirect_url)
    # Clear the CSRF nonce — single-use
    response.delete_cookie("telex_oauth_state")

    is_prod = bool(os.getenv("RENDER") or settings.environment == "production")
    is_secure = request.url.scheme == "https" or is_prod
    same_site_val = "none" if is_secure else "lax"

    # Set signed session token containing user id
    response.set_cookie(
        key="telex_session",
        value=session_token,
        max_age=60 * 60 * 24 * 30,  # 30 days
        httponly=True,
        secure=is_secure,
        samesite=same_site_val,
    )
    # Set indicator cookie for client UI presence check (constant value to prevent cookie injection)
    response.set_cookie(
        key="telex_user",
        value="1",
        max_age=60 * 60 * 24 * 30,
        httponly=False,
        secure=is_secure,
        samesite=same_site_val,
    )
    return response


@router.get("/me")
async def get_current_user(request: Request):
    """Return the currently authenticated user based on signed session cookie or Bearer header."""
    token = request.cookies.get("telex_session")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

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
@router.post("/logout")
async def logout(request: Request):
    """Clear session cookie and redirect to home or return JSON status."""
    is_prod = bool(os.getenv("RENDER") or settings.environment == "production")
    is_secure = request.url.scheme == "https" or is_prod
    same_site_val = "none" if is_secure else "lax"

    accept = request.headers.get("accept", "")
    wants_json = request.method == "POST" or "application/json" in accept

    web_base = _resolve_web_base(request)
    if wants_json:
        response = JSONResponse(content={"ok": True, "status": "logged_out"})
    else:
        response = RedirectResponse(url=f"{web_base}/", status_code=303)

    response.delete_cookie(
        key="telex_session",
        path="/",
        secure=is_secure,
        samesite=same_site_val,
    )
    response.delete_cookie(
        key="telex_user",
        path="/",
        secure=is_secure,
        samesite=same_site_val,
    )
    return response


@router.get("/dev-login")
@router.post("/dev-login")
async def dev_login(request: Request, login: str = "kesavaraja67"):
    """Development-only bypass to quickly sign in locally without GitHub roundtrip."""
    is_prod = bool(os.getenv("RENDER") or settings.environment == "production")
    if is_prod:
        raise HTTPException(status_code=403, detail="Dev login is disabled in production")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.github_login == login).limit(1))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                github_id=676767,
                github_login=login,
                email=f"{login}@users.noreply.github.com",
                avatar_url="https://avatars.githubusercontent.com/u/676767?v=4",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        user_id_str = str(user.id)

    session_token = create_session_token(user_id_str)
    web_base = os.getenv("WEB_APP_URL", "http://localhost:3000")
    redirect_url = f"{web_base}/dashboard#token={session_token}"
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(
        key="telex_session",
        value=session_token,
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    response.set_cookie(
        key="telex_user",
        value="1",
        max_age=60 * 60 * 24 * 30,
        httponly=False,
        secure=False,
        samesite="lax",
    )
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
