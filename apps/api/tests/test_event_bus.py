"""
Unit tests for services/event_bus.py and services/incident_events.py.
"""

import asyncio
import uuid
import pytest
from unittest.mock import MagicMock

from services.event_bus import IncidentEventBus
from services.incident_events import record_event


@pytest.mark.asyncio
async def test_event_bus_subscribe_and_publish_unscoped():
    bus = IncidentEventBus()
    q = bus.subscribe()
    assert q in bus._subscribers

    event = {"event_type": "change_detected", "repo_id": "repo-123", "data": "test"}
    await bus.publish(event)

    received = await asyncio.wait_for(q.get(), timeout=1.0)
    assert received == event

    bus.unsubscribe(q)
    assert q not in bus._subscribers


@pytest.mark.asyncio
async def test_event_bus_subscribe_scoped_to_repo():
    bus = IncidentEventBus()
    q_matching = bus.subscribe(repo_id="repo-1")
    q_other = bus.subscribe(repo_id="repo-2")

    event = {"event_type": "patch_generated", "repo_id": "repo-1"}
    await bus.publish(event)

    received = await asyncio.wait_for(q_matching.get(), timeout=1.0)
    assert received == event

    assert q_other.empty()

    bus.unsubscribe(q_matching)
    bus.unsubscribe(q_other)


@pytest.mark.asyncio
async def test_event_bus_queue_full_drops_oldest():
    bus = IncidentEventBus()
    q = bus.subscribe()
    maxsize = q.maxsize
    for i in range(maxsize):
        q.put_nowait({"index": i})

    assert q.full()

    new_event = {"index": "new"}
    await bus.publish(new_event)

    first = q.get_nowait()
    assert first["index"] == 1

    bus.unsubscribe(q)


@pytest.mark.asyncio
async def test_event_bus_subscriber_failure_removes_dead_queue():
    bus = IncidentEventBus()
    q = bus.subscribe()

    class BrokenQueue(asyncio.Queue):
        def put_nowait(self, item):
            raise RuntimeError("Fatal queue error")

    broken_q = BrokenQueue()
    bus._subscribers[broken_q] = {"repo_id": None}

    await bus.publish({"test": 123})

    assert broken_q not in bus._subscribers
    bus.unsubscribe(q)


@pytest.mark.asyncio
async def test_record_event_uuid_conversions():
    mock_session = MagicMock()
    real_uuid = uuid.uuid4()
    str_uuid = str(uuid.uuid4())
    invalid_uuid = "not-a-valid-uuid"

    await record_event(
        mock_session,
        event_type="test_event",
        repo_id=real_uuid,
        detected_change_id=str_uuid,
        code_usage_id=invalid_uuid,
        job_id=None,
        payload={"key": "value"},
    )

    assert mock_session.add.called
    added_ev = mock_session.add.call_args[0][0]
    assert added_ev.repo_id == real_uuid
    assert added_ev.detected_change_id == uuid.UUID(str_uuid)
    assert added_ev.code_usage_id is None
    assert added_ev.job_id is None
    assert added_ev.payload == {"key": "value"}
