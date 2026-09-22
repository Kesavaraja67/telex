"""
Append-only incident event log helper.

Usage pattern (all call sites follow this exactly):

    # Inside a handler, before session.commit():
    await record_event(
        session,
        event_type="change_detected",
        repo_id=str(repo_id),
        detected_change_id=str(dc.id),
        payload={"symbol_old": dc.symbol_old, ...},
    )
    await session.commit()

    # AFTER commit succeeds — never before:
    try:
        await event_bus.publish({
            "event_type": "change_detected",
            "repo_id": str(repo_id),
            "detected_change_id": str(dc.id),
            ...same payload fields...,
        })
    except Exception as exc:
        logger.warning("event_bus publish failed (non-fatal): %s", exc)

Design choices:
- record_event() does NOT commit — it rides the caller's existing transaction.
- record_event() does NOT publish to the bus — caller publishes after commit
  so the bus never shows an event whose DB row didn't persist.
- All UUID/datetime values are stringified at call sites (not here) so the
  event dict is always JSON-serializable for bus.publish().
"""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import IncidentEvent

logger = logging.getLogger(__name__)


async def record_event(
    session: AsyncSession,
    *,
    event_type: str,
    repo_id: uuid.UUID | str | None = None,
    detected_change_id: uuid.UUID | str | None = None,
    code_usage_id: uuid.UUID | str | None = None,
    job_id: uuid.UUID | str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Add an IncidentEvent row to session without committing.

    The caller is responsible for session.commit(). After commit, the caller
    should publish the same data to event_bus so live SSE clients receive it.
    """
    # Normalise UUIDs to uuid.UUID objects for the ORM
    def _to_uuid(v: uuid.UUID | str | None) -> uuid.UUID | None:
        if v is None:
            return None
        if isinstance(v, uuid.UUID):
            return v
        try:
            v_str: str = v if isinstance(v, str) else str(v)
            return uuid.UUID(v_str)
        except (ValueError, AttributeError):
            return None

    ev = IncidentEvent(
        repo_id=_to_uuid(repo_id),
        detected_change_id=_to_uuid(detected_change_id),
        code_usage_id=_to_uuid(code_usage_id),
        job_id=_to_uuid(job_id),
        event_type=event_type,
        payload=payload or {},
    )
    session.add(ev)
    logger.debug(
        "incident_events.record_event: queued %s (repo=%s, change=%s, usage=%s)",
        event_type,
        repo_id,
        detected_change_id,
        code_usage_id,
    )
