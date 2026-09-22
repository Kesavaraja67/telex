"""
Unit tests for routers/auth.py — session tokens, safe redirects, and require_auth dependency.
"""

import uuid
import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch

from routers.auth import (
    create_session_token,
    decode_session_token,
    is_safe_redirect,
    require_auth,
)


def test_create_and_decode_session_token():
    user_id = str(uuid.uuid4())
    token = create_session_token(user_id)
    assert isinstance(token, str)

    decoded = decode_session_token(token)
    assert decoded == user_id


def test_decode_invalid_session_token():
    assert decode_session_token("invalid.token.payload") is None
    assert decode_session_token("") is None


def test_is_safe_redirect():
    assert is_safe_redirect("/dashboard") is True
    assert is_safe_redirect("/dashboard/repos?tab=all") is True
    assert is_safe_redirect("http://localhost:3000/settings") is True
    assert is_safe_redirect("http://127.0.0.1:3000/home") is True

    # Dangerous / external redirects must fail
    assert is_safe_redirect("http://malicious-site.com/steal") is False
    assert is_safe_redirect("javascript:alert(1)") is False
    assert is_safe_redirect("") is False


@pytest.mark.asyncio
async def test_require_auth_with_cookie():
    user_id = str(uuid.uuid4())
    token = create_session_token(user_id)

    request = MagicMock()
    request.cookies = {"telex_session": token}
    request.headers = {}

    auth_dict = await require_auth(request)
    assert auth_dict["user_id"] == user_id


@pytest.mark.asyncio
async def test_require_auth_with_bearer_header():
    user_id = str(uuid.uuid4())
    token = create_session_token(user_id)

    request = MagicMock()
    request.cookies = {}
    request.headers = {"Authorization": f"Bearer {token}"}

    auth_dict = await require_auth(request)
    assert auth_dict["user_id"] == user_id


@pytest.mark.asyncio
async def test_require_auth_with_demo_key(monkeypatch):
    request = MagicMock()
    request.cookies = {}
    request.headers = {"x-demo-key": "telex_demo_secret_2026"}

    auth_dict = await require_auth(request)
    assert auth_dict["user_id"] == "demo-operator"


@pytest.mark.asyncio
async def test_require_auth_missing_raises_401():
    request = MagicMock()
    request.cookies = {}
    request.headers = {}

    with pytest.raises(HTTPException) as exc:
        await require_auth(request)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_unauthenticated():
    from main import app
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/auth/me")
        assert resp.status_code == 200
        assert resp.json() == {"authenticated": False, "user": None}


@pytest.mark.asyncio
async def test_auth_logout():
    from main import app
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/auth/logout", follow_redirects=False)
        assert resp.status_code in (302, 307, 303)
        assert resp.headers["location"].endswith("/")


@pytest.mark.asyncio
async def test_health_endpoint():
    from main import app
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_github_login_redirects():
    from main import app
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/auth/github?next=/dashboard", follow_redirects=False)
        assert resp.status_code in (302, 307)
        assert "github.com/login/oauth/authorize" in resp.headers["location"]
        assert "telex_oauth_state" in resp.cookies


@pytest.mark.asyncio
async def test_dev_login_allowed_in_development(monkeypatch):
    from main import app
    from httpx import AsyncClient, ASGITransport
    from unittest.mock import patch, AsyncMock
    from db.models import User

    fake_user = User(
        id=uuid.uuid4(),
        github_id=99999,
        github_login="dev_tester",
        email="dev_tester@example.com",
        avatar_url="https://github.com/dev_tester.png",
    )

    with patch("routers.auth.AsyncSessionLocal") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=fake_user))
        )
        mock_session_ctx.return_value = mock_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/auth/dev-login", follow_redirects=False)
            assert resp.status_code in (302, 303, 307)
            assert "telex_session" in resp.cookies


@pytest.mark.asyncio
async def test_auth_me_authenticated():
    from main import app
    from httpx import AsyncClient, ASGITransport
    from unittest.mock import patch, AsyncMock
    from db.models import User

    user_uuid = uuid.uuid4()
    fake_user = User(
        id=user_uuid,
        github_id=12345,
        github_login="auth_user",
        email="auth@example.com",
    )
    token = create_session_token(str(user_uuid))

    with patch("routers.auth.AsyncSessionLocal") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session.get = AsyncMock(return_value=fake_user)
        mock_session_ctx.return_value = mock_session

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies={"telex_session": token},
        ) as client:
            resp = await client.get("/auth/me")
            assert resp.status_code == 200
            data = resp.json()
            assert data["authenticated"] is True
            assert data["user"]["github_login"] == "auth_user"


@pytest.mark.asyncio
async def test_github_callback_csrf_mismatch():
    from main import app
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"telex_oauth_state": "expected_nonce"},
    ) as client:
        resp = await client.get("/auth/github/callback?code=abc&state=bad_nonce:/dashboard")
        assert resp.status_code == 400
        assert "CSRF" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_github_callback_success(monkeypatch):
    from main import app
    from httpx import AsyncClient, ASGITransport, Response
    from unittest.mock import patch, AsyncMock
    from db.models import User

    fake_user = User(
        id=uuid.uuid4(),
        github_id=8888,
        github_login="oauth_tester",
        email="oauth@test.com",
    )

    mock_gh_client = AsyncMock()
    mock_gh_client.__aenter__.return_value = mock_gh_client
    mock_gh_client.__aexit__.return_value = None
    mock_gh_client.post = AsyncMock(
        return_value=Response(200, json={"access_token": "fake_oauth_token"})
    )
    mock_gh_client.get = AsyncMock(
        return_value=Response(
            200,
            json={
                "id": 8888,
                "login": "oauth_tester",
                "email": "oauth@test.com",
                "avatar_url": "https://avatar.png",
            },
        )
    )

    with patch("routers.auth.AsyncSessionLocal") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=fake_user))
        )
        mock_session.commit = AsyncMock()
        mock_session_ctx.return_value = mock_session

        with patch("routers.auth.httpx.AsyncClient", return_value=mock_gh_client):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies={"telex_oauth_state": "valid_nonce"},
            ) as client:
                resp = await client.get(
                    "/auth/github/callback?code=abc&state=valid_nonce:/dashboard",
                    follow_redirects=False,
                )
                assert resp.status_code in (302, 303, 307)
                assert "dashboard" in resp.headers["location"]
                assert "telex_session" in resp.cookies


@pytest.mark.asyncio
async def test_get_authorized_repo_missing_user():
    from routers.auth import get_authorized_repo

    mock_session = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await get_authorized_repo(mock_session, "some/repo", {})
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_authorized_repo_invalid_user_uuid():
    from routers.auth import get_authorized_repo

    mock_session = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await get_authorized_repo(mock_session, "some/repo", {"user_id": "not-a-uuid-and-not-dev"})
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_authorized_repo_user_not_found():
    from routers.auth import get_authorized_repo

    mock_session = AsyncMock()
    user_res = MagicMock()
    user_res.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=user_res)

    with pytest.raises(HTTPException) as exc:
        await get_authorized_repo(mock_session, "some/repo", {"user_id": str(uuid.uuid4())})
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_authorized_repo_success():
    from db.models import Installation, Repo, User
    from routers.auth import get_authorized_repo

    user_id = uuid.uuid4()
    user = User(id=user_id, github_login="testowner")
    repo = Repo(id=uuid.uuid4(), full_name="testowner/myrepo")
    inst = Installation(id=uuid.uuid4(), github_installation_id=123)

    mock_session = AsyncMock()
    call_count = 0

    def fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        mock_r = MagicMock()
        if call_count == 1:
            mock_r.scalar_one_or_none.return_value = user
        else:
            mock_r.first.return_value = (repo, inst)
        return mock_r

    mock_session.execute = AsyncMock(side_effect=fake_execute)

    res_repo, res_inst = await get_authorized_repo(
        mock_session, "testowner/myrepo", {"user_id": str(user_id)}
    )
    assert res_repo.id == repo.id
    assert res_inst.id == inst.id


@pytest.mark.asyncio
async def test_get_authorized_repo_forbidden_vs_not_found():
    from db.models import User
    from routers.auth import get_authorized_repo

    user_id = uuid.uuid4()
    user = User(id=user_id, github_login="testowner")

    mock_session = AsyncMock()
    call_count = 0

    def fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        mock_r = MagicMock()
        if call_count == 1:
            mock_r.scalar_one_or_none.return_value = user
        elif call_count == 2:
            mock_r.first.return_value = None  # unauthorized
        else:
            mock_r.scalar_one_or_none.return_value = uuid.uuid4()  # repo exists
        return mock_r

    mock_session.execute = AsyncMock(side_effect=fake_execute)

    with pytest.raises(HTTPException) as exc:
        await get_authorized_repo(mock_session, "other/repo", {"user_id": str(user_id)})
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_authorized_repo_demo_operator():
    from db.models import Installation, Repo
    from routers.auth import get_authorized_repo

    repo = Repo(id=uuid.uuid4(), full_name="demo/repo")
    inst = Installation(id=uuid.uuid4(), github_installation_id=999)

    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.first.return_value = (repo, inst)
    mock_session.execute = AsyncMock(return_value=mock_res)

    r, i = await get_authorized_repo(mock_session, "demo/repo", {"user_id": "demo-operator"})
    assert r.id == repo.id

    mock_res.first.return_value = None
    with pytest.raises(HTTPException) as exc:
        await get_authorized_repo(mock_session, "demo/repo", {"user_id": "demo-operator"})
    assert exc.value.status_code == 404
