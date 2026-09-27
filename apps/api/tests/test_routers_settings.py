"""
Unit tests for routers/settings.py — BYOK key storage, listing, and deletion.
"""

import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from main import app
from routers.auth import require_auth
from routers.settings import SUPPORTED_PROVIDERS


@pytest.mark.asyncio
async def test_supported_providers_set():
    assert "openai" in SUPPORTED_PROVIDERS
    assert "anthropic" in SUPPORTED_PROVIDERS
    assert "gemini" in SUPPORTED_PROVIDERS
    assert "mistral" in SUPPORTED_PROVIDERS
    assert "groq" in SUPPORTED_PROVIDERS


@pytest.mark.asyncio
async def test_get_api_keys_unsupported_provider():
    user_id = str(uuid.uuid4())

    async def override_require_auth():
        return {"user_id": user_id}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/settings/api-keys",
                json={"provider": "unsupported-vendor-xyz", "key": "secret-123"},
            )
            assert resp.status_code == 422
            assert "Unsupported provider" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_list_api_keys():
    user_id = str(uuid.uuid4())

    async def override_require_auth():
        return {"user_id": user_id}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        with patch("routers.settings.AsyncSessionLocal") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_session.execute = AsyncMock(
                return_value=MagicMock(
                    scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
                )
            )
            mock_session_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/settings/api-keys")
                assert resp.status_code == 200
                data = resp.json()
                assert "keys" in data
                assert data["keys"] == []
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_delete_api_key_unsupported():
    user_id = str(uuid.uuid4())

    async def override_require_auth():
        return {"user_id": user_id}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/settings/api-keys/not-a-real-provider")
            assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_store_api_key_demo_user_rejected():
    async def override_require_auth():
        return {"user_id": "demo-operator"}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/settings/api-keys",
                json={"provider": "openai", "key": "test-mock-secret-key-12345"},
            )
            assert resp.status_code == 403
            assert "Demo accounts cannot" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_delete_api_key_demo_user_rejected():
    async def override_require_auth():
        return {"user_id": "demo-operator"}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/settings/api-keys/openai")
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_store_api_key_success():
    user_id = str(uuid.uuid4())

    async def override_require_auth():
        return {"user_id": user_id}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        from db.models import UserApiKey

        mock_row = UserApiKey(
            user_id=uuid.UUID(user_id),
            provider="openai",
            encrypted_key=b"enc-bytes",
            created_at=datetime.now(timezone.utc),
        )

        with patch("routers.settings.AsyncSessionLocal") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_session.get_bind = MagicMock(
                return_value=MagicMock(dialect=MagicMock(name="sqlite"))
            )
            mock_res = MagicMock()
            mock_res.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_res)
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/settings/api-keys",
                    json={"provider": "openai", "key": "test-mock-real-token-1234"},
                )
                assert resp.status_code == 201
                data = resp.json()
                assert data["provider"] == "openai"
                assert data["connected"] is True
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_delete_api_key_success_and_not_found():
    user_id = str(uuid.uuid4())

    async def override_require_auth():
        return {"user_id": user_id}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        from db.models import UserApiKey

        mock_row = UserApiKey(
            user_id=uuid.UUID(user_id),
            provider="anthropic",
            encrypted_key=b"enc-bytes",
            created_at=datetime.now(timezone.utc),
        )

        with patch("routers.settings.AsyncSessionLocal") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None

            # First test: not found
            mock_res_empty = MagicMock()
            mock_res_empty.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_res_empty)
            mock_session_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete("/api/settings/api-keys/anthropic")
                assert resp.status_code == 404

            # Second test: found and deleted
            mock_res_found = MagicMock()
            mock_res_found.scalar_one_or_none.return_value = mock_row
            mock_session.execute = AsyncMock(return_value=mock_res_found)
            mock_session.delete = AsyncMock()
            mock_session.commit = AsyncMock()

            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete("/api/settings/api-keys/anthropic")
                assert resp.status_code == 200
                assert resp.json()["connected"] is False
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_store_api_key_too_short_rejected():
    user_id = str(uuid.uuid4())

    async def override_require_auth():
        return {"user_id": user_id}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/settings/api-keys",
                json={"provider": "openai", "key": "short"},
            )
            assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_store_api_key_whitespace_only_rejected():
    user_id = str(uuid.uuid4())

    async def override_require_auth():
        return {"user_id": user_id}

    app.dependency_overrides[require_auth] = override_require_auth
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/settings/api-keys",
                json={"provider": "openai", "key": "          "},
            )
            assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_settings_endpoints_unauthenticated_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET
        get_res = await client.get("/api/settings/api-keys")
        assert get_res.status_code == 401

        # POST
        post_res = await client.post(
            "/api/settings/api-keys",
            json={"provider": "openai", "key": "valid-secret-key-1234"},
        )
        assert post_res.status_code == 401

        # DELETE
        del_res = await client.delete("/api/settings/api-keys/openai")
        assert del_res.status_code == 401
