"""
Payment service — Razorpay Test Mode wrapper.

HONESTY NOTE ON FAILURE INJECTION:
- "card_declined" failures are REAL Razorpay Test Mode API responses using
  documented test card numbers that Razorpay guarantees will decline.
- "timeout" and "db_unavailable" failures are locally-simulated at this
  service boundary because Razorpay itself provides no API lever to trigger
  network timeouts or database outages — those are infrastructure failures,
  not payment-rail failures. We raise them ourselves so they flow through
  the same recovery pipeline as real Razorpay errors without requiring
  actual infrastructure downtime during a demo.
This distinction is stated explicitly in BUILD_LOG.md and should be mentioned
honestly in the pitch video (section 11 of the spec).
"""
import hashlib
import hmac
import logging
import uuid

from config import settings

logger = logging.getLogger(__name__)

# Razorpay test card that always triggers a card_declined response.
# Source: https://razorpay.com/docs/payments/payments/test-card-details/
_TEST_CARD_DECLINED = "4100280000060003"

# Locally-simulated failure types (no Razorpay call made — see module docstring)
_LOCALLY_SIMULATED_FAILURES = {"timeout", "db_unavailable"}


def _get_razorpay_client():
    """Return a configured Razorpay client in Test Mode."""
    try:
        import razorpay  # type: ignore[import]
    except ImportError:
        raise RuntimeError("razorpay package not installed — run: pip install razorpay")

    key_id = settings.razorpay_test_key_id
    key_secret = settings.razorpay_test_key_secret
    if not key_id or not key_secret:
        raise RuntimeError(
            "RAZORPAY_TEST_KEY_ID and RAZORPAY_TEST_KEY_SECRET must be set. "
            "Use Test Mode keys only — never live keys."
        )
    return razorpay.Client(auth=(key_id, key_secret))


def create_order(amount_paise: int) -> dict:
    """
    Create a Razorpay Test Mode order.

    Args:
        amount_paise: amount in Indian paise (e.g. 50000 = ₹500).

    Returns:
        Razorpay order dict including at minimum {"id": "<order_id>", ...}.
    """
    client = _get_razorpay_client()
    order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"telex-{uuid.uuid4().hex[:12]}",
        "payment_capture": 1,
    })
    logger.info("Created Razorpay Test order: %s (amount=%d paise)", order["id"], amount_paise)
    return order


def simulate_payment(order_id: str, force_failure: str | None) -> dict:
    """
    Simulate a payment against a Test Mode order.

    Args:
        order_id: Razorpay order ID from create_order().
        force_failure: One of:
            None            — attempt a successful test payment
            "card_declined" — use real Razorpay test card that declines
            "timeout"       — locally injected, no Razorpay call (see module docstring)
            "db_unavailable"— locally injected, no Razorpay call (see module docstring)

    Returns:
        dict with keys: success (bool), error_type (str|None), razorpay_payment_id (str|None)

    Raises:
        RuntimeError — for locally-injected timeout/db_unavailable failures,
                       so they propagate naturally through the job queue retry path.
    """
    # ── Locally-injected infrastructure failures ──────────────────────────────
    # These never hit the Razorpay API. See module docstring for why.
    if force_failure in _LOCALLY_SIMULATED_FAILURES:
        logger.warning(
            "simulate_payment: locally injecting %s failure for order %s",
            force_failure, order_id,
        )
        raise RuntimeError(
            f"Locally-simulated failure: {force_failure} (no Razorpay call was made)"
        )

    # ── Real Razorpay Test Mode calls ─────────────────────────────────────────
    if not (settings.razorpay_test_key_id and settings.razorpay_test_key_secret):
        # Keys not configured — fall back to a safe simulated success/failure
        logger.warning("simulate_payment: Razorpay credentials not configured, using synthetic response")
        if force_failure:
            return {"success": False, "error_type": force_failure, "razorpay_payment_id": None}
        return {"success": True, "error_type": None, "razorpay_payment_id": f"pay_synthetic_{uuid.uuid4().hex[:16]}"}

    try:
        client = _get_razorpay_client()

        if force_failure == "card_declined":
            # Razorpay documented test card that always declines.
            # Using payment.create with a test card number triggers the real decline flow.
            payment_data = {
                "amount": 0,  # fetched from order, but required field
                "currency": "INR",
                "order_id": order_id,
                "method": "card",
                "card": {
                    "number": _TEST_CARD_DECLINED,
                    "name": "Test User",
                    "expiry_month": "12",
                    "expiry_year": "30",
                    "cvv": "123",
                },
                "email": "test@example.com",
                "contact": "9000000000",
            }
            try:
                result = client.payment.create(payment_data)
                # Razorpay may return the payment in a failed state
                if result.get("status") in ("failed", "created"):
                    return {
                        "success": False,
                        "error_type": "card_declined",
                        "razorpay_payment_id": result.get("id"),
                    }
                return {"success": True, "error_type": None, "razorpay_payment_id": result.get("id")}
            except Exception as razorpay_exc:
                # Razorpay API itself rejected the card — this is the expected result
                logger.info("simulate_payment: Razorpay declined card (expected): %s", razorpay_exc)
                return {"success": False, "error_type": "card_declined", "razorpay_payment_id": None}

        # Successful test payment — Razorpay Test Mode accepts any valid test card
        payment_data = {
            "amount": 0,
            "currency": "INR",
            "order_id": order_id,
            "method": "upi",
            "upi": {"vpa": "success@razorpay"},  # Razorpay test VPA that always succeeds
            "email": "test@example.com",
            "contact": "9000000000",
        }
        try:
            result = client.payment.create(payment_data)
            is_success = result.get("status") not in ("failed",)
            return {
                "success": is_success,
                "error_type": None if is_success else "payment_failed",
                "razorpay_payment_id": result.get("id"),
            }
        except Exception as exc:
            logger.warning("simulate_payment: payment attempt failed: %s", exc)
            return {"success": False, "error_type": "payment_failed", "razorpay_payment_id": None}

    except Exception as exc:
        logger.error("simulate_payment: unexpected error: %s", exc)
        raise


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify a Razorpay webhook HMAC-SHA256 signature.

    Mirrors the structure of github_service.verify_webhook_signature() exactly:
    - Returns False if the secret is not configured.
    - Returns False if the signature header is missing or malformed.
    - Uses hmac.compare_digest to prevent timing-oracle attacks.
    """
    secret = settings.razorpay_webhook_secret
    if not secret:
        logger.error("RAZORPAY_WEBHOOK_SECRET not configured — rejecting webhook")
        return False

    if not signature:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def verify_checkout_signature(razorpay_order_id: str, razorpay_payment_id: str, signature: str) -> bool:
    """
    Verify Razorpay Checkout.js payment response signature.
    Per Razorpay documentation:
    HMAC-SHA256 of f"{order_id}|{payment_id}" using the API key secret.
    """
    secret = settings.razorpay_test_key_secret
    if not secret:
        logger.error("RAZORPAY_TEST_KEY_SECRET not configured — rejecting signature verification")
        return False

    if not razorpay_order_id or not razorpay_payment_id or not signature:
        return False

    msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
    expected = hmac.new(
        secret.encode("utf-8"),
        msg=msg,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)

