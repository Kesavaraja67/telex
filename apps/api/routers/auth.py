"""
GitHub OAuth callback — creates/updates users row and manages authentication sessions.
"""
import secrets
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import RedirectResponse
import httpx

from db.session import AsyncSessionLocal
from db.models import User
from config import settings
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["auth"])

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

# Shared client timeout for all GitHub HTTP requests
_GITHUB_TIMEOUT = httpx.Timeout(10.0)


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
async def github_callback(code: str, request: Request, state: Optional[str] = None):
    """
    Exchange OAuth code for token, upsert user in database,
    set session cookie, and redirect to destination.
    """
    # ── CSRF validation ─────────────────────────────────────────────────────
    stored_nonce = request.cookies.get("telex_oauth_state", "")
    nonce_from_state = state.split(":", 1)[0] if state else ""
    next_url = state.split(":", 1)[1] if state and ":" in state else ""

    if not stored_nonce or not secrets.compare_digest(stored_nonce, nonce_from_state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF attack")

    # ── Exchange code for access token ───────────────────────────────────────
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
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="GitHub OAuth token exchange failed")

    # ── Fetch user profile from GitHub ───────────────────────────────────────
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=_GITHUB_TIMEOUT,
    ) as client:
        user_resp = await client.get(GITHUB_USER_URL)

    if user_resp.status_code != 200:
        raise HTTPException(status_code=502, detail="GitHub profile fetch failed")

    gh_user = user_resp.json()
    if "id" not in gh_user or "login" not in gh_user:
        raise HTTPException(status_code=502, detail="Unexpected GitHub profile payload")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.github_id == gh_user["id"])
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                github_id=gh_user["id"],
                github_login=gh_user["login"],
                email=gh_user.get("email"),
                avatar_url=gh_user.get("avatar_url"),
            )
            session.add(user)
        else:
            user.github_login = gh_user["login"]
            user.email = gh_user.get("email")
            user.avatar_url = gh_user.get("avatar_url")

        await session.commit()

    # Determine redirect destination
    web_base = settings.next_public_api_url.replace(":8000", ":3000")
    if next_url == "install":
        redirect_url = "https://github.com/apps/telex-agent-dev/installations/new"
    elif next_url and next_url.startswith("http"):
        redirect_url = next_url
    else:
        redirect_url = f"{web_base}/dashboard?login={user.github_login}"

    response = RedirectResponse(url=redirect_url)
    # Clear the CSRF nonce — single-use
    response.delete_cookie("telex_oauth_state")
    # Set readable cookie for client & backend verification
    response.set_cookie(
        key="telex_user",
        value=user.github_login,
        max_age=60 * 60 * 24 * 30,  # 30 days
        httponly=False,
        samesite="lax",
    )
    return response


@router.get("/me")
async def get_current_user(request: Request):
    """Return the currently authenticated user based on session cookie."""
    user_login = request.cookies.get("telex_user")
    if not user_login:
        return {"authenticated": False, "user": None}

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.github_login == user_login))
        user = result.scalar_one_or_none()
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
    web_base = settings.next_public_api_url.replace(":8000", ":3000")
    response = RedirectResponse(url=f"{web_base}/")
    response.delete_cookie(key="telex_user")
    return response
