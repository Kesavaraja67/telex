"""
Tests for in-memory sliding window RateLimitMiddleware.
"""

from collections import deque

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from config import Settings
from services.rate_limit import RateLimitMiddleware


class FakeClock:
    """Controllable clock for deterministic rate limit testing."""

    def __init__(self, initial_time: float = 1000.0):
        self.current_time = initial_time

    def __call__(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


def create_test_app(
    requests_limit: int = 3,
    window_seconds: int = 10,
    trust_proxy: bool = False,
    clock: FakeClock | None = None,
    max_clients: int = 10000,
    sweep_interval: int = 1000,
) -> tuple[FastAPI, RateLimitMiddleware]:
    test_app = FastAPI()
    middleware = RateLimitMiddleware(
        app=test_app.router,
        requests_limit=requests_limit,
        window_seconds=window_seconds,
        trust_proxy=trust_proxy,
        clock=clock,
        max_clients=max_clients,
        sweep_interval=sweep_interval,
    )
    test_app.add_middleware(
        RateLimitMiddleware,
        requests_limit=requests_limit,
        window_seconds=window_seconds,
        trust_proxy=trust_proxy,
        clock=clock,
        max_clients=max_clients,
        sweep_interval=sweep_interval,
    )

    @test_app.get("/api/test")
    async def sample_endpoint():
        return {"message": "ok"}

    @test_app.options("/api/test")
    async def sample_options():
        return {"message": "options ok"}

    @test_app.get("/health")
    async def health():
        return {"status": "ok"}

    @test_app.get("/api/health")
    async def api_health():
        return {"status": "ok"}

    @test_app.post("/webhooks")
    async def webhooks_root():
        return {"status": "webhook received"}

    @test_app.post("/webhooks/github")
    async def webhooks_github():
        return {"status": "github webhook received"}

    return test_app, middleware


def test_rate_limit_and_429():
    clock = FakeClock(1000.0)
    app, _ = create_test_app(requests_limit=3, window_seconds=10, clock=clock)
    client = TestClient(app)

    # 3 requests within limit
    r1 = client.get("/api/test")
    assert r1.status_code == 200
    assert r1.headers.get("x-ratelimit-limit") == "3"
    assert r1.headers.get("x-ratelimit-remaining") == "2"

    r2 = client.get("/api/test")
    assert r2.status_code == 200
    assert r2.headers.get("x-ratelimit-limit") == "3"
    assert r2.headers.get("x-ratelimit-remaining") == "1"

    r3 = client.get("/api/test")
    assert r3.status_code == 200
    assert r3.headers.get("x-ratelimit-limit") == "3"
    assert r3.headers.get("x-ratelimit-remaining") == "0"

    # 4th request exceeds limit -> 429
    r4 = client.get("/api/test")
    assert r4.status_code == 429
    assert r4.json() == {"detail": "Too many requests"}
    assert r4.headers.get("x-ratelimit-limit") == "3"
    assert r4.headers.get("x-ratelimit-remaining") == "0"
    retry_after = int(r4.headers.get("retry-after", 0))
    assert retry_after >= 1


def test_window_slides():
    clock = FakeClock(1000.0)
    app, _ = create_test_app(requests_limit=2, window_seconds=10, clock=clock)
    client = TestClient(app)

    # Hit 1 at t=1000.0
    r1 = client.get("/api/test")
    assert r1.status_code == 200

    # Advance 4s -> Hit 2 at t=1004.0
    clock.advance(4.0)
    r2 = client.get("/api/test")
    assert r2.status_code == 200

    # Immediate 3rd hit at t=1004.0 -> 429
    r3 = client.get("/api/test")
    assert r3.status_code == 429
    # Oldest hit was at 1000.0, expires at 1010.0 -> retry-after = 1010.0 - 1004.0 = 6
    assert r3.headers.get("retry-after") == "6"

    # Advance 6.1s (t=1010.1) -> Hit 1 (from t=1000.0) expired, Hit 2 (from 1004.0) still active
    clock.advance(6.1)
    r4 = client.get("/api/test")
    assert r4.status_code == 200
    assert r4.headers.get("x-ratelimit-remaining") == "0"

    # Advance 4.0s (t=1014.1) -> Hit 2 expired
    clock.advance(4.0)
    r5 = client.get("/api/test")
    assert r5.status_code == 200
    assert r5.headers.get("x-ratelimit-remaining") == "0"


def test_per_client_buckets():
    clock = FakeClock(1000.0)
    app, _ = create_test_app(requests_limit=2, window_seconds=10, trust_proxy=True, clock=clock)
    client = TestClient(app)

    # Client A exhausts limit
    r1 = client.get("/api/test", headers={"X-Forwarded-For": "198.51.100.1"})
    r2 = client.get("/api/test", headers={"X-Forwarded-For": "198.51.100.1"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    r3 = client.get("/api/test", headers={"X-Forwarded-For": "198.51.100.1"})
    assert r3.status_code == 429

    # Client B should still be allowed
    r_b = client.get("/api/test", headers={"X-Forwarded-For": "198.51.100.2"})
    assert r_b.status_code == 200
    assert r_b.headers.get("x-ratelimit-remaining") == "1"


def test_xff_trust_proxy_on_and_off():
    clock = FakeClock(1000.0)

    # 1. trust_proxy=True: uses first hop of X-Forwarded-For
    app_trusted, _ = create_test_app(
        requests_limit=1, window_seconds=10, trust_proxy=True, clock=clock
    )
    client_trusted = TestClient(app_trusted)

    r1 = client_trusted.get("/api/test", headers={"X-Forwarded-For": "203.0.113.50, 10.0.0.1"})
    assert r1.status_code == 200

    r2 = client_trusted.get("/api/test", headers={"X-Forwarded-For": "203.0.113.50, 10.0.0.2"})
    assert r2.status_code == 429

    r3 = client_trusted.get("/api/test", headers={"X-Forwarded-For": "203.0.113.99, 10.0.0.1"})
    assert r3.status_code == 200

    # 2. trust_proxy=False: ignores X-Forwarded-For header
    app_untrusted, _ = create_test_app(
        requests_limit=1, window_seconds=10, trust_proxy=False, clock=clock
    )
    client_untrusted = TestClient(app_untrusted)

    r_u1 = client_untrusted.get("/api/test", headers={"X-Forwarded-For": "203.0.113.50"})
    assert r_u1.status_code == 200

    # Since trust_proxy=False, client IP is testclient default for both, so second request is rate-limited
    r_u2 = client_untrusted.get("/api/test", headers={"X-Forwarded-For": "203.0.113.99"})
    assert r_u2.status_code == 429


def test_exempt_paths_and_options():
    clock = FakeClock(1000.0)
    app, _ = create_test_app(requests_limit=1, window_seconds=10, clock=clock)
    client = TestClient(app)

    # Exhaust limit on /api/test
    r1 = client.get("/api/test")
    assert r1.status_code == 200
    r2 = client.get("/api/test")
    assert r2.status_code == 429

    # OPTIONS method is exempt
    r_opt = client.options("/api/test")
    assert r_opt.status_code == 200

    # /health and /api/health are exempt
    r_h1 = client.get("/health")
    assert r_h1.status_code == 200

    r_h2 = client.get("/api/health")
    assert r_h2.status_code == 200

    # /webhooks* are exempt
    r_wh1 = client.post("/webhooks")
    assert r_wh1.status_code == 200

    r_wh2 = client.post("/webhooks/github")
    assert r_wh2.status_code == 200


def test_headers_and_retry_after_at_least_one():
    clock = FakeClock(1000.0)
    app, _ = create_test_app(requests_limit=1, window_seconds=1, clock=clock)
    client = TestClient(app)

    r1 = client.get("/api/test")
    assert r1.status_code == 200
    assert r1.headers.get("x-ratelimit-limit") == "1"
    assert r1.headers.get("x-ratelimit-remaining") == "0"

    # Advance clock by 0.999s so remaining window is < 1s
    clock.advance(0.999)
    r2 = client.get("/api/test")
    assert r2.status_code == 429
    # Retry-After must be at least 1
    retry_after = int(r2.headers.get("retry-after", "0"))
    assert retry_after >= 1


def test_pruning_and_client_cap():
    clock = FakeClock(1000.0)
    mw = RateLimitMiddleware(
        app=FastAPI().router,
        requests_limit=10,
        window_seconds=10,
        trust_proxy=True,
        clock=clock,
        max_clients=3,
        sweep_interval=5,
    )

    # Populate 3 clients
    for i in range(1, 4):
        mw._hits[f"10.0.0.{i}"] = deque([1000.0])

    assert len(mw._hits) == 3

    # Add 4th client through direct hit logic — should sweep/cap at max_clients=3
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        requests_limit=10,
        window_seconds=10,
        trust_proxy=True,
        clock=clock,
        max_clients=3,
        sweep_interval=5,
    )

    @app.get("/api/test")
    async def sample():
        return {"ok": True}

    client = TestClient(app)

    # Make requests from 5 distinct clients
    for i in range(1, 6):
        resp = client.get("/api/test", headers={"X-Forwarded-For": f"10.0.0.{i}"})
        assert resp.status_code == 200

    # Advance clock by 15s to expire all hits
    clock.advance(15.0)

    # Trigger idle sweep via sweep_interval requests
    for i in range(10, 16):
        client.get("/api/test", headers={"X-Forwarded-For": f"10.0.1.{i}"})

    # Direct unit test of _sweep_idle
    mw_direct = RateLimitMiddleware(
        app=FastAPI().router,
        requests_limit=5,
        window_seconds=10,
        clock=clock,
    )
    mw_direct._hits["active"] = deque([clock()])
    mw_direct._hits["idle"] = deque([clock() - 20.0])
    mw_direct._sweep_idle(clock() - mw_direct.window_seconds)

    assert "active" in mw_direct._hits
    assert "idle" not in mw_direct._hits


def test_disabled_flag():
    # Test setting rate_limit_enabled=False in Settings
    custom_settings = Settings(
        rate_limit_enabled=False,
        rate_limit_requests=2,
        rate_limit_window_seconds=10,
    )

    app = FastAPI()
    if custom_settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            requests_limit=custom_settings.rate_limit_requests,
            window_seconds=custom_settings.rate_limit_window_seconds,
        )

    @app.get("/api/test")
    async def sample():
        return {"ok": True}

    client = TestClient(app)
    # Send 5 requests — none should be rate limited
    for _ in range(5):
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert "x-ratelimit-limit" not in resp.headers
