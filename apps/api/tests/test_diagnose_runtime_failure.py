import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from jobs.handlers import diagnose_runtime_failure
from services.patch_providers.gemini import parse_classification_response


def test_tier1_deterministic_classifications():
    """All known deterministic failure types map correctly to transient or code_defect."""
    assert diagnose_runtime_failure.DETERMINISTIC_CLASSIFICATIONS["timeout"] == "transient"
    assert diagnose_runtime_failure.DETERMINISTIC_CLASSIFICATIONS["rate_limit"] == "transient"
    assert diagnose_runtime_failure.DETERMINISTIC_CLASSIFICATIONS["db_unavailable"] == "transient"
    assert diagnose_runtime_failure.DETERMINISTIC_CLASSIFICATIONS["network_error"] == "transient"
    assert diagnose_runtime_failure.DETERMINISTIC_CLASSIFICATIONS["payment_failed"] == "transient"
    assert diagnose_runtime_failure.DETERMINISTIC_CLASSIFICATIONS["card_declined"] == "transient"
    assert diagnose_runtime_failure.DETERMINISTIC_CLASSIFICATIONS["webhook_signature_mismatch"] == "code_defect"
    assert diagnose_runtime_failure.DETERMINISTIC_CLASSIFICATIONS["webhook_schema_mismatch"] == "code_defect"


def test_parse_classification_response_valid_json():
    """Extracts classification, reasoning, and recommended_action from clean JSON."""
    raw = '{"classification": "code_defect", "reasoning": "Missing field in payload", "recommended_action": "open PR"}'
    res = parse_classification_response(raw)
    assert res["classification"] == "code_defect"
    assert res["reasoning"] == "Missing field in payload"
    assert res["recommended_action"] == "open PR"


def test_parse_classification_response_fenced_markdown():
    """Handles markdown code fences around JSON response."""
    raw = """```json
{
  "classification": "transient",
  "reasoning": "Gateway timed out on upstream dependency",
  "recommended_action": "retry with backoff"
}
```"""
    res = parse_classification_response(raw)
    assert res["classification"] == "transient"
    assert "Gateway timed out" in res["reasoning"]


def test_parse_classification_response_invalid_and_non_dict():
    """Gracefully handles strings, lists, or invalid JSON by returning unknown."""
    assert parse_classification_response("Not a json")["classification"] == "unknown"
    assert parse_classification_response('["transient", "reason"]')["classification"] == "unknown"
    assert parse_classification_response('"just_a_string"')["classification"] == "unknown"
    assert parse_classification_response("")["classification"] == "unknown"


def test_parse_classification_response_unknown_type_normalization():
    """Normalizes unexpected classification values to unknown."""
    raw = '{"classification": "something_random", "reasoning": "test"}'
    res = parse_classification_response(raw)
    assert res["classification"] == "unknown"


@pytest.mark.asyncio
async def test_diagnose_handler_tier1_deterministic_flow():
    """Tier 1 failure types short-circuit without calling the LLM provider."""
    mock_event = MagicMock()
    mock_event.failure_type = "timeout"
    mock_event.classification = "unknown"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_event

    mock_session_local = MagicMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    with patch("db.session.AsyncSessionLocal", mock_session_local), \
         patch("jobs.queue.enqueue_job", new_callable=AsyncMock) as mock_enqueue, \
         patch("services.patch_providers.get_patch_provider") as mock_get_provider:

        event_id = uuid.uuid4()
        await diagnose_runtime_failure.run({"recovery_event_id": str(event_id)})

        # LLM provider should NOT be called for deterministic timeout
        mock_get_provider.assert_not_called()

        # Event fields updated to Tier 1 metadata
        assert mock_event.classification == "transient"
        assert mock_event.llm_provider == "none"
        assert mock_event.llm_model == "none"
        assert "Classified via deterministic rule" in mock_event.action_taken

        # recover_runtime job enqueued with classification
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args[1]
        assert call_kwargs["job_type"] == "recover_runtime"
        assert call_kwargs["payload"]["classification"] == "transient"


@pytest.mark.asyncio
async def test_diagnose_handler_tier2_llm_flow():
    """Ambiguous failure types not in rule table call LLM provider."""
    mock_event = MagicMock()
    mock_event.failure_type = "unrecognized_custom_gateway_error"
    mock_event.classification = "unknown"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_event

    mock_session_local = MagicMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_provider = AsyncMock()
    mock_provider.model_name = "gemini-2.5-flash"
    mock_provider.classify_failure.return_value = {
        "classification": "code_defect",
        "reasoning": "The payload schema deviates from API contract v2.",
        "recommended_action": "Generate patch for payment handler",
    }

    with patch("db.session.AsyncSessionLocal", mock_session_local), \
         patch("jobs.queue.enqueue_job", new_callable=AsyncMock) as mock_enqueue, \
         patch("services.patch_providers.get_patch_provider", return_value=mock_provider):

        event_id = uuid.uuid4()
        await diagnose_runtime_failure.run({"recovery_event_id": str(event_id)})

        # Provider classify_failure WAS called
        mock_provider.classify_failure.assert_called_once()

        # Event fields updated from LLM response
        assert mock_event.classification == "code_defect"
        assert mock_event.llm_model == "gemini-2.5-flash"
        assert "Classified via LLM: The payload schema deviates" in mock_event.action_taken

        # recover_runtime job enqueued
        mock_enqueue.assert_called_once()
        call_kwargs = mock_enqueue.call_args[1]
        assert call_kwargs["payload"]["classification"] == "code_defect"
