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
    """
    simulate_payment(force_failure=None) now delegates to verify_order_payment_status,
    which queries order.fetch rather than calling payment.create.
    Per Razorpay docs, backends cannot collect payments via the Payments API;
    the correct path is to verify if the order is already paid, and if not,
    generate a Checkout retry URL for the customer.
    When order.fetch raises, verify_order_payment_status returns success=False.
    """
    mock_client = MagicMock()
    mock_client.order.fetch.side_effect = Exception("Gateway connection error")

    with patch.object(settings, "razorpay_test_key_id", "rzp_test_key"), \
         patch.object(settings, "razorpay_test_key_secret", "rzp_test_secret"), \
         patch("services.payment_service._get_razorpay_client", return_value=mock_client):

        result = payment_service.simulate_payment("order_test_123", force_failure=None)
        assert result["success"] is False
        # verify_order_payment_status returns order_status="error" when fetch raises
        assert result.get("order_status") == "error"
        assert result.get("payment_id") is None


def test_verify_webhook_signature_payment_captured():
    """Verify payment.captured webhook signature and event parsing."""
    secret = "test_webhook_secret_key_12345"
    payload = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_captured_999","order_id":"order_123"}}}}'
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    with patch.object(settings, "razorpay_webhook_secret", secret):
        assert payment_service.verify_webhook_signature(payload, expected_sig) is True


def test_verify_checkout_signature_valid():
    """Valid Checkout.js HMAC signature matches order_id|payment_id digest."""
    secret = "rzp_secret_test_98765"
    order_id = "order_ABCD1234"
    payment_id = "pay_XYZ9876"
    msg = f"{order_id}|{payment_id}".encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), msg=msg, digestmod=hashlib.sha256).hexdigest()

    with patch.object(settings, "razorpay_test_key_secret", secret):
        assert payment_service.verify_checkout_signature(order_id, payment_id, expected_sig) is True


def test_verify_checkout_signature_invalid_and_tampered():
    """Tampered signature or modified order/payment ID is rejected."""
    secret = "rzp_secret_test_98765"
    order_id = "order_ABCD1234"
    payment_id = "pay_XYZ9876"

    with patch.object(settings, "razorpay_test_key_secret", secret):
        assert payment_service.verify_checkout_signature(order_id, payment_id, "invalid_sig_abc") is False
        assert payment_service.verify_checkout_signature(order_id, payment_id, "") is False
        assert payment_service.verify_checkout_signature("tampered_order", payment_id, "some_sig") is False


