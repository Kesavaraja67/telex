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


def _specifier_matches_added(spec: str, node_path: str, added_paths: set[str]) -> bool:
    clean = spec.strip("<>\"'")
    if not clean:
        return False
    if clean.startswith("."):
        from_dir = PurePosixPath(node_path).parent
        cand = (from_dir / clean).as_posix().lstrip("/")
        norm = os.path.normpath(cand).replace("\\", "/").lstrip("/")
        if norm in added_paths:
            return True
        for ext in (
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".py",
            ".go",
            ".rs",
            "/index.ts",
            "/index.tsx",
            "/index.js",
        ):
            if f"{norm}{ext}" in added_paths:
                return True
    else:
        clean_norm = clean.replace("@/", "").lstrip("/")
        for ap in added_paths:
            if ap == clean_norm or ap.endswith(f"/{clean_norm}"):
                return True
            for ext in (
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".py",
                ".go",
                ".rs",
                "/index.ts",
                "/index.tsx",
                "/index.js",
            ):
                if f"{clean_norm}{ext}" == ap or ap.endswith(f"/{clean_norm}{ext}"):
                    return True
    return False


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

        # Check base_sha and head_sha against state
        if state and state.head_sha:
            if base_sha and state.head_sha != base_sha:
                if state.head_sha == head_sha:
                    logger.info(
                        "Graph already at head_sha %s for %s, skipping",
                        head_sha[:8],
                        repo_full_name,
                    )
                    return {
                        "mode": "incremental",
                        "head_sha": head_sha,
                        "status": "ready",
                        "skipped": True,
                    }
                logger.warning(
                    "Stale push or head mismatch for %s: base_sha=%s != current head_sha=%s (job head=%s). Aborting job.",
                    repo_full_name,
                    base_sha[:8],
                    state.head_sha[:8],
                    head_sha[:8],
                )
                return {
                    "mode": "aborted",
                    "head_sha": state.head_sha,
                    "status": "stale",
                    "reason": f"base_sha mismatch: expected {state.head_sha}, got {base_sha}",
                }

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
            expected_head = base_sha if base_sha else (state.head_sha if state else None)
            await build_atlas_graph.run(
                {
                    "repo_id": str(repo_uuid),
                    "commit_sha": head_sha,
                    "from_incremental": True,
                    "expected_head_sha": expected_head,
                    "base_sha": base_sha,
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

            # A. Track importers needing re-parse
            reparse_importers: set[str] = set()

            # Handle Removed files
            for rem_path in removed:
                norm_rem = rem_path.replace("\\", "/").lstrip("/")
                # Collect incoming edge source_paths before deleting edges
                inc_edges_res = await session.execute(
                    select(AtlasEdge.source_path).where(
                        AtlasEdge.repo_id == repo_uuid,
                        AtlasEdge.target_path == norm_rem,
                    )
                )
                for src in inc_edges_res.scalars().all():
                    src_str = getattr(src, "source_path", src)
                    if isinstance(src_str, str) and src_str not in removed:
                        reparse_importers.add(src_str)

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

            # Check if any existing nodes imported newly added paths
            added_norm_set = {ap.replace("\\", "/").lstrip("/") for ap in added}
            if added_norm_set:
                for npath, nnode in node_map.items():
                    if npath not in removed and nnode.unresolved_specifiers:
                        for spec in nnode.unresolved_specifiers:
                            if _specifier_matches_added(spec, npath, added_norm_set):
                                reparse_importers.add(npath)
                                break

            files_to_process = list(dict.fromkeys(added + modified + list(reparse_importers)))
            parsed_results: list[dict[str, Any]] = []

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
                    logger.warning(
                        "Failed to fetch content for %s @ %s, falling back to full scan",
                        norm_path,
                        head_sha[:8],
                    )
                    from jobs.handlers import build_atlas_graph

                    expected_head = base_sha if base_sha else (state.head_sha if state else None)
                    await build_atlas_graph.run(
                        {
                            "repo_id": str(repo_uuid),
                            "commit_sha": head_sha,
                            "from_incremental": True,
                            "expected_head_sha": expected_head,
                            "base_sha": base_sha,
                        }
                    )
                    return {"mode": "full", "head_sha": head_sha, "status": "ready"}

                source_bytes = content_text.encode("utf-8")
                chash = compute_content_hash(source_bytes)
                lang = LANGUAGE_BY_EXT.get(ext, "plaintext")
                posix = PurePosixPath(norm_path)

                existing_node = node_map.get(norm_path)
                if (
                    existing_node
                    and existing_node.content_hash == chash
                    and norm_path not in reparse_importers
                ):
                    continue

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

                parsed_results.append(
                    {
                        "path": norm_path,
                        "targets": resolved_targets,
                    }
                )

            # Flush nodes first so foreign key constraints on atlas_edges are satisfied
            if hasattr(session, "flush"):
                flush_res = session.flush()
                if asyncio.iscoroutine(flush_res) or hasattr(flush_res, "__await__"):
                    await flush_res

            # Now update edges for all parsed files
            for pr in parsed_results:
                src_path = pr["path"]
                await session.execute(
                    delete(AtlasEdge).where(
                        AtlasEdge.repo_id == repo_uuid,
                        AtlasEdge.source_path == src_path,
                    )
                )
                for target in pr["targets"]:
                    if target in node_map:
                        session.add(
                            AtlasEdge(
                                repo_id=repo_uuid,
                                source_path=src_path,
                                target_path=target,
                                kind="static",
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
                "build_mode": "incremental",
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

            # Atomic publication check on AtlasState
            state_query = (
                select(AtlasState).where(AtlasState.repo_id == repo_uuid).with_for_update()
            )
            cur_state_res = await session.execute(state_query)
            cur_candidate = cur_state_res.scalar_one_or_none()
            if isinstance(cur_candidate, AtlasState):
                cur_state = cur_candidate
            else:
                cur_state = await session.get(AtlasState, repo_uuid)

            expected_head = base_sha if base_sha else (state.head_sha if state else None)
            if cur_state and cur_state.head_sha:
                if cur_state.head_sha != head_sha:
                    if expected_head is not None and cur_state.head_sha != expected_head:
                        logger.warning(
                            "AtlasState head_sha changed concurrently to %s (expected %s), aborting",
                            cur_state.head_sha,
                            expected_head,
                        )
                        await session.rollback()
                        return {
                            "mode": "aborted",
                            "head_sha": cur_state.head_sha,
                            "status": "conflict",
                        }
                    elif expected_head is None:
                        logger.warning(
                            "AtlasState head_sha set concurrently to %s, aborting",
                            cur_state.head_sha,
                        )
                        await session.rollback()
                        return {
                            "mode": "aborted",
                            "head_sha": cur_state.head_sha,
                            "status": "conflict",
                        }

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
