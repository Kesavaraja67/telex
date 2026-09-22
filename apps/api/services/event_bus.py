"""
In-process pub/sub for live incident events.

Valid because the worker and the API share one event loop (see render.yaml:
EMBEDDED_WORKER=true, single instance). If Telex ever runs multiple API
instances or a dedicated worker process, replace this module's transport with
Postgres LISTEN/NOTIFY:

  Upgrade path (do NOT implement now — document only):
  1. Keep record_event() and the incident_events table exactly as-is
     (they're already process-agnostic Postgres data).
  2. After each session.commit() in the handlers, instead of calling
     event_bus.publish() call:
       await session.execute(
           text("SELECT pg_notify('incident_events', :payload)"),
           {"payload": json.dumps(event_dict)},
       )
  3. Each API instance runs one persistent asyncpg LISTEN connection on startup
     that receives the NOTIFY and fans out to its local _subscribers dict
     exactly like publish() does today.
  4. The SSE endpoint and snapshot endpoint do not change at all.

Do NOT add Redis for this. The incident_events Postgres table is already the
durable log — LISTEN/NOTIFY is just the transport layer on top of it, and it
only needs to exist when there is more than one OS process.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_MAX_QUEUE_PER_SUBSCRIBER = 200  # backpressure: drop oldest, don't block the worker


@dataclass
class IncidentEventBus:
    _subscribers: dict[asyncio.Queue, dict[str, Any]] = field(default_factory=dict)

    def subscribe(self, *, repo_id: str | None = None) -> asyncio.Queue:
        """Register a new SSE connection. Optionally scope to one repo_id.

        Pass repo_id=None to receive events for all repos (the SSE router
        passes the authed user's repo_id so this is always scoped for real
        clients — None is only used in tests and local debugging).
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE_PER_SUBSCRIBER)
        self._subscribers[q] = {"repo_id": repo_id}
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.pop(q, None)

    async def publish(self, event: dict[str, Any]) -> None:
        """Broadcast event to all matching subscribers.

        event must already be JSON-serializable (str/int/float/bool/None/
        dict/list only — no UUID or datetime objects; stringify them at the
        call site before publishing).

        NEVER raises into the calling worker loop — a dead SSE consumer or
        a full queue is not a job failure. Dropped intermediate frames are
        fine; the client's next /graph snapshot fetch will catch it up.
        """
        dead: list[asyncio.Queue] = []
        repo_id = event.get("repo_id")

        for q, meta in list(self._subscribers.items()):
            # Filter by repo_id if the subscriber scoped to one
            if meta["repo_id"] is not None and repo_id != meta["repo_id"]:
                continue
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow consumer — drop the oldest rather than blocking the
                # worker loop. A dropped intermediate frame is acceptable;
                # the client calls /graph to catch up.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    dead.append(q)
            except Exception as exc:
                logger.warning("event_bus: subscriber delivery failed: %s", exc)
                dead.append(q)

        for q in dead:
            self.unsubscribe(q)


# Module-level singleton — imported by incident_events.py and handlers
event_bus = IncidentEventBus()
