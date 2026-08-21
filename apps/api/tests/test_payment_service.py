import hmac
import hashlib
import pytest
from unittest.mock import patch, MagicMock

from services import payment_service
from config import settings


def test_verify_webhook_signature_valid():
    """Valid HMAC signature matches computed digest."""
    secret = "test_webhook_secret_key_12345"
    payload = b'{"event":"payment.failed","payload":{"payment":{"entity":{"id":"pay_123"}}}}'
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    with patch.object(settings, "razorpay_webhook_secret", secret):
        assert payment_service.verify_webhook_signature(payload, expected_sig) is True


def test_verify_webhook_signature_invalid_and_tampered():
    """Tampered payload or wrong signature returns False."""
    secret = "test_webhook_secret_key_12345"
    payload = b'{"event":"payment.failed"}'
    fake_sig = "a" * 64

    with patch.object(settings, "razorpay_webhook_secret", secret):
        assert payment_service.verify_webhook_signature(payload, fake_sig) is False
        assert payment_service.verify_webhook_signature(payload, "") is False


def test_verify_webhook_signature_missing_secret():
    """Missing webhook secret rejects immediately."""
    payload = b'{"event":"payment.failed"}'
    with patch.object(settings, "razorpay_webhook_secret", ""):
        assert payment_service.verify_webhook_signature(payload, "some_sig") is False


def test_simulate_payment_locally_injected_failures():
    """Locally simulated failures raise RuntimeError at service boundary without hitting Razorpay."""
    with pytest.raises(RuntimeError) as exc_info:
        payment_service.simulate_payment("order_test_123", force_failure="timeout")
    assert "Locally-simulated failure: timeout" in str(exc_info.value)

    with pytest.raises(RuntimeError) as exc_info:
        payment_service.simulate_payment("order_test_123", force_failure="db_unavailable")
    assert "Locally-simulated failure: db_unavailable" in str(exc_info.value)


def test_simulate_payment_unconfigured_credentials():
    """When credentials are not configured, falls back to safe synthetic response."""
    with patch.object(settings, "razorpay_test_key_id", ""), patch.object(settings, "razorpay_test_key_secret", ""):
        res_success = payment_service.simulate_payment("order_test_123", force_failure=None)
        assert res_success["success"] is True
        assert res_success["error_type"] is None
        assert res_success["razorpay_payment_id"].startswith("pay_synthetic_")

        res_fail = payment_service.simulate_payment("order_test_123", force_failure="card_declined")
        assert res_fail["success"] is False
        assert res_fail["error_type"] == "card_declined"
        assert res_fail["razorpay_payment_id"] is None


def test_simulate_payment_configured_card_declined():
    """Card decline uses documented Razorpay test card."""
    mock_client = MagicMock()
    mock_client.payment.create.return_value = {"id": "pay_declined_123", "status": "failed"}

    with patch.object(settings, "razorpay_test_key_id", "rzp_test_key"), \
         patch.object(settings, "razorpay_test_key_secret", "rzp_test_secret"), \
         patch("services.payment_service._get_razorpay_client", return_value=mock_client):

        result = payment_service.simulate_payment("order_test_123", force_failure="card_declined")
        assert result["success"] is False
        assert result["error_type"] == "card_declined"
        # Verify it used the decline card number 4100280000060003
        call_args = mock_client.payment.create.call_args[0][0]
        assert call_args["card"]["number"] == payment_service._TEST_CARD_DECLINED
        assert call_args["card"]["number"] == "4100280000060003"


def test_simulate_payment_configured_normal_failure_handling():
    """Normal payment exception from client.payment.create returns failure without synthetic ID."""
    mock_client = MagicMock()
    mock_client.payment.create.side_effect = Exception("Gateway connection error")

    with patch.object(settings, "razorpay_test_key_id", "rzp_test_key"), \
         patch.object(settings, "razorpay_test_key_secret", "rzp_test_secret"), \
         patch("services.payment_service._get_razorpay_client", return_value=mock_client):

        result = payment_service.simulate_payment("order_test_123", force_failure=None)
        assert result["success"] is False
        assert result["error_type"] == "payment_failed"
        assert result["razorpay_payment_id"] is None
