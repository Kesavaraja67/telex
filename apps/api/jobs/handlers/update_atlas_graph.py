"""
update_atlas_graph — Incremental graph updater job handler.
Triggered on push events to default branch or on manual refresh with a small diff.
"""

import logging
import uuid
from typing import Any

from services.atlas_incremental import update_incremental_graph

logger = logging.getLogger(__name__)


async def run(payload_or_session, maybe_job=None) -> dict[str, Any]:
    if maybe_job is not None:
        payload = maybe_job.payload or {}
    elif isinstance(payload_or_session, dict):
        payload = payload_or_session
    elif hasattr(payload_or_session, "payload"):
        payload = payload_or_session.payload or {}
    else:
        payload = {}

    repo_id_str = payload["repo_id"]
    base_sha = payload.get("base_sha")
    head_sha = payload.get("head_sha") or payload.get("commit_sha") or ""
    changed = payload.get("changed", {})

    repo_uuid = uuid.UUID(repo_id_str) if isinstance(repo_id_str, str) else repo_id_str

    logger.info(
        "update_atlas_graph starting for repo=%s base=%s head=%s changes=(+%d ~%d -%d)",
        repo_id_str,
        (base_sha or "")[:8],
        head_sha[:8],
        len(changed.get("added", [])),
        len(changed.get("modified", [])),
        len(changed.get("removed", [])),
    )

    return await update_incremental_graph(
        repo_id=repo_uuid,
        base_sha=base_sha,
        head_sha=head_sha,
        changed=changed,
    )


update_atlas_incremental = update_incremental_graph
