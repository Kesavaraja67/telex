"""
In-memory sliding window rate limiting ASGI middleware.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from starlette.types import ASGIApp, Receive, Scope, Send


class RateLimitMiddleware:
    """
    In-memory sliding-window rate limiting middleware for ASGI applications.

    Tracks timestamps of incoming requests per client IP in a sliding time window.
    Resets on process restart (per-process in-memory store).
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_limit: int = 120,
        window_seconds: int = 60,
        trust_proxy: bool = False,
        clock: Callable[[], float] | None = None,
        max_clients: int = 10000,
        sweep_interval: int = 1000,
    ) -> None:
        self.app = app
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.trust_proxy = trust_proxy
        self.clock = clock if clock is not None else time.monotonic
        self.max_clients = max_clients
        self.sweep_interval = sweep_interval
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}
        self._request_count = 0

    def _get_client_ip(self, scope: Scope) -> str:
        if self.trust_proxy:
            headers = scope.get("headers", [])
            for key, val in headers:
                if key.lower() == b"x-forwarded-for":
                    try:
                        raw = val.decode("latin1")
                    except Exception:
                        raw = val.decode("utf-8", errors="ignore")
                    hops = [h.strip() for h in raw.split(",") if h.strip()]
                    if hops:
                        return hops[0]
        client = scope.get("client")
        if client and client[0]:
            return str(client[0])
        return "unknown"

    def _is_exempt(self, scope: Scope) -> bool:
        if scope.get("method") == "OPTIONS":
            return True
        path = scope.get("path", "")
        if path in ("/health", "/health/", "/api/health", "/api/health/"):
            return True
        if path.startswith("/webhooks"):
            return True
        return False

    def _sweep_idle(self, cutoff: float) -> None:
        # Assumes self._lock is held
        idle_keys = []
        for client, timestamps in self._hits.items():
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if not timestamps:
                idle_keys.append(client)
        for client in idle_keys:
            del self._hits[client]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        if self._is_exempt(scope):
            await self.app(scope, receive, send)
            return

        client_ip = self._get_client_ip(scope)
        now = self.clock()
        cutoff = now - self.window_seconds

        with self._lock:
            self._request_count += 1
            if self._request_count >= self.sweep_interval:
                self._request_count = 0
                self._sweep_idle(cutoff)

            hits = self._hits.get(client_ip)
            if hits is None:
                if len(self._hits) >= self.max_clients:
                    self._sweep_idle(cutoff)
                    while len(self._hits) >= self.max_clients:
                        oldest_key = next(iter(self._hits))
                        del self._hits[oldest_key]
                hits = deque()
                self._hits[client_ip] = hits
            else:
                while hits and hits[0] <= cutoff:
                    hits.popleft()

            if len(hits) >= self.requests_limit:
                # Rate limit exceeded
                oldest_hit = hits[0]
                retry_after = max(1, math.ceil((oldest_hit + self.window_seconds) - now))
                response_body = b'{"detail":"Too many requests"}'
                headers = [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(response_body)).encode("ascii")),
                    (b"retry-after", str(retry_after).encode("ascii")),
                    (b"x-ratelimit-limit", str(self.requests_limit).encode("ascii")),
                    (b"x-ratelimit-remaining", b"0"),
                ]

                await send(
                    {
                        "type": "http.response.start",
                        "status": 429,
                        "headers": headers,
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": response_body,
                        "more_body": False,
                    }
                )
                return

            # Allowed request
            hits.append(now)
            remaining = max(0, self.requests_limit - len(hits))

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-ratelimit-limit", str(self.requests_limit).encode("ascii")))
                headers.append((b"x-ratelimit-remaining", str(remaining).encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
