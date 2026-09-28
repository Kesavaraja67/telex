"""
Unit tests for patch providers BYOK factory, fallback hierarchy, and credential safety.
"""

import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from config import settings
from db.models import UserApiKey
from services.crypto import encrypt_key
from services.patch_providers import get_patch_provider, get_patch_provider_for_user
from services.patch_providers.gemini import GeminiProvider
from services.patch_providers.claude import ClaudeProvider
from services.patch_providers.openai_provider import OpenAIProvider
from services.patch_providers.mistral_provider import MistralProvider
from services.patch_providers.groq_provider import GroqProvider
from services.patch_providers.extra_providers import (
    CohereProvider,
    DeepSeekProvider,
    NemotronProvider,
    TogetherProvider,
    XAIProvider,
)


def test_get_patch_provider_unknown_raises_value_error():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_patch_provider("unsupported-llm-12345")


def test_get_patch_provider_missing_keys_fail_closed(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(RuntimeError, match="GeminiProvider requires GEMINI_API_KEY"):
        get_patch_provider("gemini", api_key="")

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(RuntimeError, match="ClaudeProvider requires ANTHROPIC_API_KEY"):
        get_patch_provider("claude", api_key="")

    with pytest.raises(RuntimeError, match="OpenAI is a BYOK-only provider"):
        get_patch_provider("openai", api_key=None)

    with pytest.raises(RuntimeError, match="Mistral is a BYOK-only provider"):
        get_patch_provider("mistral", api_key=None)

    with pytest.raises(RuntimeError, match="Groq is a BYOK-only provider"):
        get_patch_provider("groq", api_key=None)


@pytest.fixture(autouse=True)
def mock_optional_sdks(monkeypatch):
    """Ensure optional provider SDKs can be imported during tests without failing."""
    mock_openai = MagicMock()
    mock_anthropic = MagicMock()
    mock_mistral = MagicMock()
    mock_groq = MagicMock()
    mock_cohere = MagicMock()

    modules = {
        "openai": mock_openai,
        "anthropic": mock_anthropic,
        "mistralai": mock_mistral,
        "groq": mock_groq,
        "cohere": mock_cohere,
    }
    with patch.dict("sys.modules", modules):
        yield


def test_provider_repr_masks_api_keys():
    test_key = "super-secret-production-key-9999"

    gemini = GeminiProvider(api_key=test_key)
    assert repr(gemini) == "<GeminiProvider model='gemini-2.5-flash'>"
    assert test_key not in repr(gemini)

    claude = ClaudeProvider(api_key=test_key)
    assert repr(claude) == "<ClaudeProvider model='claude-sonnet-4-5'>"
    assert test_key not in repr(claude)

    openai_p = OpenAIProvider(api_key=test_key)
    assert repr(openai_p) == "<OpenAIProvider model='gpt-4o-mini'>"
    assert test_key not in repr(openai_p)

    mistral = MistralProvider(api_key=test_key)
    assert repr(mistral) == "<MistralProvider model='mistral-small-latest'>"
    assert test_key not in repr(mistral)

    groq = GroqProvider(api_key=test_key)
    assert repr(groq) == "<GroqProvider model='llama-3.3-70b-versatile'>"
    assert test_key not in repr(groq)

    cohere = CohereProvider(api_key=test_key)
    assert repr(cohere) == "<CohereProvider model='command-r-plus-08-2024'>"
    assert test_key not in repr(cohere)

    xai = XAIProvider(api_key=test_key)
    assert repr(xai) == "<XAIProvider model='grok-3-mini'>"
    assert test_key not in repr(xai)

    deepseek = DeepSeekProvider(api_key=test_key)
    assert repr(deepseek) == "<DeepSeekProvider model='deepseek-chat'>"
    assert test_key not in repr(deepseek)

    together = TogetherProvider(api_key=test_key)
    assert repr(together) == "<TogetherProvider model='meta-llama/Llama-3.3-70B-Instruct-Turbo'>"
    assert test_key not in repr(together)

    nemotron = NemotronProvider(api_key=test_key)
    assert repr(nemotron) == "<NemotronProvider model='nvidia/llama-3.1-nemotron-70b-instruct'>"
    assert test_key not in repr(nemotron)


@pytest.mark.asyncio
async def test_get_patch_provider_for_user_with_byok_key():
    user_id = str(uuid.uuid4())
    plain_key = "user-custom-openai-key-8888"
    cipher = encrypt_key(plain_key)

    mock_row = UserApiKey(
        user_id=uuid.UUID(user_id),
        provider="openai",
        encrypted_key=cipher,
        created_at=datetime.now(timezone.utc),
        last_used_at=None,
    )

    with patch("services.patch_providers.AsyncSessionLocal") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session.commit = AsyncMock()
        mock_session_ctx.return_value = mock_session

        provider = await get_patch_provider_for_user(user_id=user_id, preferred_provider="openai")
        assert isinstance(provider, OpenAIProvider)
        assert mock_row.last_used_at is not None
        mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_patch_provider_for_user_fallback_to_platform_gemini(monkeypatch):
    user_id = str(uuid.uuid4())
    monkeypatch.setattr(settings, "gemini_api_key", "platform-gemini-key")
    monkeypatch.setattr(settings, "llm_provider_default", "gemini")

    with patch("services.patch_providers.AsyncSessionLocal") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session_ctx.return_value = mock_session

        provider = await get_patch_provider_for_user(user_id=user_id, preferred_provider="openai")
        assert isinstance(provider, GeminiProvider)


@pytest.mark.asyncio
async def test_get_patch_provider_for_user_no_credentials_fails_closed(monkeypatch):
    user_id = str(uuid.uuid4())
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "llm_provider_default", "gemini")

    with patch("services.patch_providers.AsyncSessionLocal") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session_ctx.return_value = mock_session

        with pytest.raises(RuntimeError, match="No usable LLM provider credentials found"):
            await get_patch_provider_for_user(user_id=user_id, preferred_provider="openai")


@pytest.mark.asyncio
async def test_get_patch_provider_for_user_corrupted_key_falls_back(monkeypatch, caplog):
    user_id = str(uuid.uuid4())
    monkeypatch.setattr(settings, "gemini_api_key", "platform-gemini-key")
    monkeypatch.setattr(settings, "llm_provider_default", "gemini")

    mock_row = UserApiKey(
        user_id=uuid.UUID(user_id),
        provider="openai",
        encrypted_key="corrupted-non-fernet-token-123",
        created_at=datetime.now(timezone.utc),
    )

    with patch("services.patch_providers.AsyncSessionLocal") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_res)
        mock_session_ctx.return_value = mock_session

        provider = await get_patch_provider_for_user(user_id=user_id, preferred_provider="openai")
        assert isinstance(provider, GeminiProvider)
        assert "failed to decrypt BYOK key" in caplog.text
        assert "corrupted-non-fernet-token-123" not in caplog.text
