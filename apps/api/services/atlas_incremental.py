"""
atlas_incremental.py — Incremental AST scanning and graph synchronization engine (Phase 3).

Instead of re-downloading and re-parsing the whole repository tarball on every commit,
this service handles small diffs (<= 40% of codebase) by fetching only changed files via GitHub API,
re-parsing import specifiers, and updating the normalized atlas_nodes and atlas_edges tables.
Falls back to full snapshot scan when diff > 40%, on first run, or when last full scan is > 7 days old.
"""

import asyncio
import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import tree_sitter_languages as tsl
from sqlalchemy import delete, func, select

from db.models import AtlasEdge, AtlasNode, AtlasState, Installation, Repo, RepoAtlasGraph
from db.session import AsyncSessionLocal
from services.github_service import fetch_file_content
from services.import_graph import (
    BINARY_EXTENSIONS,
    LANGUAGE_BY_EXT,
    _extract_specifiers,
    _looks_internal,
    _resolve_specifier,
)

logger = logging.getLogger(__name__)


def compute_content_hash(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def parse_single_file_imports(
    rel_path: str,
    source: str | bytes,
    existing_paths: set[str] | dict[str, Any],
) -> tuple[list[dict[str, str]], list[str]]:
    source_bytes = source.encode("utf-8") if isinstance(source, str) else source
    known_nodes = (
        {p: True for p in existing_paths} if isinstance(existing_paths, set) else existing_paths
    )
    targets, unresolved = parse_file_imports(rel_path, source_bytes, known_nodes)
    edges = [{"source_path": rel_path, "target_path": t, "kind": "static"} for t in targets]
    return edges, unresolved


def parse_file_imports(
    rel_path: str,
    source_bytes: bytes,
    known_nodes: dict[str, Any],
    repo_root: Path | None = None,
) -> tuple[list[str], list[str]]:
    """
    Parses a single file's source code and extracts:
    - resolved_target_paths: list[str] (edges)
    - unresolved_specifiers: list[str]
    """
    ext = os.path.splitext(rel_path)[1].lower()
    lang = LANGUAGE_BY_EXT.get(ext)
    if not lang or ext in BINARY_EXTENSIONS or len(source_bytes) > 2 * 1024 * 1024:
        return [], []

    try:
        parser = tsl.get_parser(lang)
        language = tsl.get_language(lang)
    except Exception as exc:
        logger.debug("Tree-sitter parser unavailable for %s: %s", lang, exc)
        return [], []

    tree = parser.parse(source_bytes)
    specifiers = _extract_specifiers(language, tree, lang)

    resolved_targets: list[str] = []
    unresolved_specifiers: list[str] = []
    dummy_root = repo_root or Path("/")
    alias_cache: dict[str, dict] = {}

    for spec_text, is_dynamic in specifiers:
        if is_dynamic:
            unresolved_specifiers.append(spec_text)
            continue

        resolved = _resolve_specifier(
            spec_text,
            rel_path,
            dummy_root,
            lang,
            known_nodes,
            alias_cache,
        )
        if resolved is not None:
            resolved_targets.append(resolved)
        elif _looks_internal(spec_text, lang):
            unresolved_specifiers.append(spec_text)

    # De-duplicate
    return list(dict.fromkeys(resolved_targets)), list(dict.fromkeys(unresolved_specifiers))


async def update_incremental_graph(
    repo_id: uuid.UUID | str,
    head_sha: str = "",
    base_sha: str | None = None,
    changed: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """
    Executes incremental AST update for a repository after a push or refresh.
    Returns: {"mode": "incremental" | "full", "head_sha": head_sha, "node_count": int, "edge_count": int}
    """
    repo_uuid = uuid.UUID(str(repo_id))
    changed_dict = changed or {}
    added = changed_dict.get("added", [])
    modified = changed_dict.get("modified", [])
    removed = changed_dict.get("removed", [])
    total_changed = len(added) + len(modified) + len(removed)

    async with AsyncSessionLocal() as session:
        repo = await session.get(Repo, repo_uuid)
        if not repo:
            raise ValueError(f"Repo {repo_id} not found")

        installation = await session.get(Installation, repo.installation_id)
        if not installation:
            raise ValueError(f"Installation for repo {repo_id} not found")

        repo_full_name = repo.full_name
        github_inst_id = installation.github_installation_id

        # 1. Check existing state
        state = await session.get(AtlasState, repo_uuid)
        count_res = await session.execute(
            select(func.count()).select_from(AtlasNode).where(AtlasNode.repo_id == repo_uuid)
        )
        node_count = count_res.scalar() or 0

        now = datetime.now(timezone.utc)
        needs_full_scan = False

        if not state or node_count == 0:
            needs_full_scan = True
            logger.info("Atlas fallback: First scan for %s", repo_full_name)
        elif state.last_full_scan_at and (now - state.last_full_scan_at) > timedelta(days=7):
            needs_full_scan = True
            logger.info("Atlas fallback: Periodic 7-day refresh for %s", repo_full_name)
        elif node_count > 0 and (total_changed / node_count) > 0.40:
            needs_full_scan = True
            logger.info(
                "Atlas fallback: Changed files (%d) exceeds 40%% of total nodes (%d)",
                total_changed,
                node_count,
            )

        if needs_full_scan:
            from jobs.handlers import build_atlas_graph

            logger.info("Running full scan for %s @ %s", repo_full_name, head_sha[:8])
            await build_atlas_graph.run(
                {
                    "repo_id": str(repo_uuid),
                    "commit_sha": head_sha,
                }
            )
            return {"mode": "full", "head_sha": head_sha, "status": "ready"}

        # 2. Mark state as updating
        if state is None:
            state = AtlasState(
                repo_id=repo_uuid,
                head_sha=head_sha,
                status="updating",
            )
            session.add(state)
        else:
            state.status = "updating"
            state.error_message = None
        await session.commit()

    # 3. Incremental Processing
    try:
        async with AsyncSessionLocal() as session:
            # Load existing nodes for resolution
            existing_nodes_res = await session.execute(
                select(AtlasNode).where(AtlasNode.repo_id == repo_uuid)
            )
            node_map = {n.path: n for n in existing_nodes_res.scalars().all()}

            # A. Handle Removed files
            for rem_path in removed:
                norm_rem = rem_path.replace("\\", "/").lstrip("/")
                await session.execute(
                    delete(AtlasEdge).where(
                        AtlasEdge.repo_id == repo_uuid,
                        (AtlasEdge.source_path == norm_rem) | (AtlasEdge.target_path == norm_rem),
                    )
                )
                await session.execute(
                    delete(AtlasNode).where(
                        AtlasNode.repo_id == repo_uuid,
                        AtlasNode.path == norm_rem,
                    )
                )
                node_map.pop(norm_rem, None)

            # B. Handle Added & Modified files
            files_to_process = list(dict.fromkeys(added + modified))
            for fpath in files_to_process:
                norm_path = fpath.replace("\\", "/").lstrip("/")
                ext = os.path.splitext(norm_path)[1].lower()
                is_binary = ext in BINARY_EXTENSIONS

                # Fetch file content from GitHub via thread
                content_text = await asyncio.to_thread(
                    fetch_file_content,
                    repo_full_name,
                    github_inst_id,
                    norm_path,
                    ref=head_sha,
                )
                if content_text is None:
                    continue

                source_bytes = content_text.encode("utf-8")
                chash = compute_content_hash(source_bytes)
                lang = LANGUAGE_BY_EXT.get(ext, "plaintext")
                posix = PurePosixPath(norm_path)

                # Skip re-parsing if content hash is unchanged
                existing_node = node_map.get(norm_path)
                if existing_node and existing_node.content_hash == chash:
                    continue

                # Parse imports
                resolved_targets, unresolved = parse_file_imports(norm_path, source_bytes, node_map)

                # Upsert node
                if existing_node:
                    existing_node.size_bytes = len(source_bytes)
                    existing_node.content_hash = chash
                    existing_node.unresolved_specifiers = unresolved
                    existing_node.updated_sha = head_sha
                else:
                    new_node = AtlasNode(
                        repo_id=repo_uuid,
                        path=norm_path,
                        name=posix.name,
                        dir=str(posix.parent) if str(posix.parent) != "." else "",
                        depth=len(posix.parts) - 1,
                        ext=ext,
                        language=lang,
                        is_binary=is_binary,
                        size_bytes=len(source_bytes),
                        content_hash=chash,
                        unresolved_specifiers=unresolved,
                        updated_sha=head_sha,
                    )
                    session.add(new_node)
                    node_map[norm_path] = new_node

                # Update outgoing edges
                await session.execute(
                    delete(AtlasEdge).where(
                        AtlasEdge.repo_id == repo_uuid,
                        AtlasEdge.source_path == norm_path,
                    )
                )
                for target in resolved_targets:
                    session.add(
                        AtlasEdge(
                            repo_id=repo_uuid,
                            source_path=norm_path,
                            target_path=target,
                            kind="import",
                            updated_sha=head_sha,
                        )
                    )

            # C. Reassemble JSONB snapshot in repo_atlas_graphs for fast reads
            all_nodes_res = await session.execute(
                select(AtlasNode).where(AtlasNode.repo_id == repo_uuid)
            )
            final_nodes = all_nodes_res.scalars().all()

            all_edges_res = await session.execute(
                select(AtlasEdge).where(AtlasEdge.repo_id == repo_uuid)
            )
            final_edges = all_edges_res.scalars().all()

            # Build folders
            folders_dict = {
                "": {"id": "", "name": repo_full_name.split("/")[-1], "parent": None, "depth": 0}
            }
            for n in final_nodes:
                parts = n.path.split("/")[:-1]
                built = ""
                parent = ""
                for part in parts:
                    built = f"{built}/{part}" if built else part
                    if built not in folders_dict:
                        folders_dict[built] = {
                            "id": built,
                            "name": part,
                            "parent": parent,
                            "depth": built.count("/"),
                        }
                    parent = built

            graph_payload = {
                "nodes": [
                    {
                        "id": n.path,
                        "name": n.name,
                        "dir": n.dir,
                        "depth": n.depth,
                        "ext": n.ext,
                        "language": n.language,
                        "is_binary": n.is_binary,
                        "size_bytes": n.size_bytes,
                        "unresolved_import_count": len(n.unresolved_specifiers or []),
                        "unresolved_specifiers": n.unresolved_specifiers or [],
                    }
                    for n in final_nodes
                ],
                "edges": [
                    {"source": e.source_path, "target": e.target_path, "kind": e.kind}
                    for e in final_edges
                ],
                "folders": list(folders_dict.values()),
                "truncated": False,
            }

            # Upsert RepoAtlasGraph
            graph_row_res = await session.execute(
                select(RepoAtlasGraph).where(
                    RepoAtlasGraph.repo_id == repo_uuid,
                    RepoAtlasGraph.commit_sha == head_sha,
                )
            )
            graph_row = graph_row_res.scalar_one_or_none()
            if not graph_row:
                graph_row = RepoAtlasGraph(
                    id=uuid.uuid4(),
                    repo_id=repo_uuid,
                    commit_sha=head_sha,
                    status="ready",
                    node_count=len(final_nodes),
                    edge_count=len(final_edges),
                    truncated=False,
                    graph_json=graph_payload,
                    completed_at=datetime.now(timezone.utc),
                )
                session.add(graph_row)
            else:
                graph_row.status = "ready"
                graph_row.graph_json = graph_payload
                graph_row.node_count = len(final_nodes)
                graph_row.edge_count = len(final_edges)
                graph_row.completed_at = datetime.now(timezone.utc)

            # Update AtlasState
            cur_state = await session.get(AtlasState, repo_uuid)
            if cur_state:
                cur_state.head_sha = head_sha
                cur_state.status = "idle"
                cur_state.error_message = None

            await session.commit()

            logger.info(
                "Incremental update complete for %s @ %s: %d nodes, %d edges",
                repo_full_name,
                head_sha[:8],
                len(final_nodes),
                len(final_edges),
            )
            return {
                "mode": "incremental",
                "head_sha": head_sha,
                "node_count": len(final_nodes),
                "edge_count": len(final_edges),
                "delta": {
                    "added": added,
                    "modified": modified,
                    "removed": removed,
                },
            }

    except Exception as exc:
        logger.exception("Incremental update failed for repo %s @ %s", repo_id, head_sha)
        async with AsyncSessionLocal() as err_session:
            cur_state = await err_session.get(AtlasState, repo_uuid)
            if cur_state:
                cur_state.status = "failed"
                cur_state.error_message = str(exc)[:2000]
                await err_session.commit()
        raise


update_atlas_incremental = update_incremental_graph
