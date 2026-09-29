"""
repo_analysis.py — Evidence-Based Run Analysis Engine (Phase 4).

Core Principle: Score is computed strictly from verified facts.
LLM only writes prose about those facts. LLM never invents a number.
Weights: services/analysis_weights.py
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from db.models import (
    AtlasEdge,
    AtlasNode,
    CodeUsage,
    DetectedChange,
    Patch,
    PullRequest,
    Repo,
    RepoAnalysisRun,
    RepoAtlasGraph,
    ValidationRun,
)
from db.session import AsyncSessionLocal
from services.analysis_weights import (
    compute_change_safety_score,
    compute_composite_score,
    compute_dependency_score,
    compute_structure_score,
    compute_verification_score,
)

logger = logging.getLogger(__name__)


# ─── Graph Algorithms ─────────────────────────────────────────────────────────


def find_cycles_tarjan(nodes: list[str], adj: dict[str, list[str]]) -> list[list[str]]:
    """
    Find all strongly connected components (SCCs) with size > 1 using Tarjan's algorithm.
    Returns cycle paths.
    """
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    sccs: list[list[str]] = []

    def strongconnect(v: str):
        nonlocal index
        indices[v] = index
        lowlinks[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in adj.get(v, []):
            if w not in indices:
                strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in on_stack:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if lowlinks[v] == indices[v]:
            scc: list[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == v:
                    break
            # Filter non-trivial SCCs (size > 1 or self loop)
            if len(scc) > 1 or (len(scc) == 1 and v in adj.get(v, [])):
                sccs.append(scc)

    for n in nodes:
        if n not in indices:
            strongconnect(n)

    # Reconstruct readable cycle sequences
    cycle_paths: list[list[str]] = []
    for scc in sccs:
        scc_set = set(scc)
        start = scc[0]
        path = [start]
        visited_in_path = {start}
        curr = start
        found = False

        for _ in range(len(scc) + 2):
            next_hop = None
            for nbr in adj.get(curr, []):
                if nbr == start and len(path) > 1:
                    path.append(start)
                    found = True
                    break
                if nbr in scc_set and nbr not in visited_in_path:
                    next_hop = nbr
                    break
            if found:
                break
            if next_hop:
                path.append(next_hop)
                visited_in_path.add(next_hop)
                curr = next_hop
            else:
                break

        cycle_paths.append(path if found else scc)

    return cycle_paths


def compute_deepest_dependency_chain(
    nodes: list[str], adj: dict[str, list[str]], cycle_nodes: set[str]
) -> list[str]:
    """
    Finds the longest acyclic path in the DAG (ignoring cycle nodes to prevent infinite loops).
    """
    memo: dict[str, list[str]] = {}
    visiting: set[str] = set()

    def dfs(node: str) -> list[str]:
        if node in memo:
            return memo[node]
        if node in visiting or node in cycle_nodes:
            return [node]

        visiting.add(node)
        best_tail: list[str] = []
        for nbr in adj.get(node, []):
            if nbr not in cycle_nodes:
                tail = dfs(nbr)
                if len(tail) > len(best_tail):
                    best_tail = tail
        visiting.remove(node)

        result = [node] + best_tail
        memo[node] = result
        return result

    longest: list[str] = []
    for n in nodes:
        chain = dfs(n)
        if len(chain) > len(longest):
            longest = chain

    return longest


# ─── Signal Extractors ────────────────────────────────────────────────────────


def extract_structure_signals(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Computes structural graph signals:
    - circular import cycles
    - hub files (fan-in / fan-out)
    - orphan files
    - unresolved internal specifiers
    - deepest dependency chain
    - cross-folder coupling
    """
    node_paths = [n["path"] for n in nodes]
    node_set = set(node_paths)

    adj: dict[str, list[str]] = {p: [] for p in node_paths}
    rev: dict[str, list[str]] = {p: [] for p in node_paths}

    cross_folder_edges = 0
    total_edges = 0

    for e in edges:
        src = e["source_path"]
        tgt = e["target_path"]
        if src in node_set and tgt in node_set:
            adj[src].append(tgt)
            rev[tgt].append(src)
            total_edges += 1

            src_folder = src.rsplit("/", 1)[0] if "/" in src else ""
            tgt_folder = tgt.rsplit("/", 1)[0] if "/" in tgt else ""
            if src_folder != tgt_folder:
                cross_folder_edges += 1

    # 1. Circular import cycles
    cycle_paths = find_cycles_tarjan(node_paths, adj)
    cycle_nodes = {n for path in cycle_paths for n in path}

    # 2. Hub files (fan-in > 10, or top 10 files)
    file_fan_in = [
        {
            "path": p,
            "fan_in": len(rev[p]),
            "fan_out": len(adj[p]),
        }
        for p in node_paths
    ]
    file_fan_in.sort(key=lambda x: x["fan_in"], reverse=True)
    top_hubs = [f for f in file_fan_in[:10] if f["fan_in"] > 0]
    critical_hubs = [f for f in top_hubs if f["fan_in"] > 30]

    # 3. Orphan files (0 in, 0 out, excluding config/docs/binaries)
    orphans = []
    for n in nodes:
        p = n["path"]
        ext = n.get("ext", "")
        if ext in [".md", ".json", ".yaml", ".yml", ".txt", ".toml", ".svg", ".png"]:
            continue
        if len(rev[p]) == 0 and len(adj[p]) == 0:
            orphans.append(p)

    orphan_ratio = len(orphans) / max(1, len(nodes))

    # 4. Unresolved internal imports
    unresolved_summary: list[dict[str, Any]] = []
    total_unresolved = 0
    for n in nodes:
        specs = n.get("unresolved_specifiers") or []
        if specs:
            total_unresolved += len(specs)
            unresolved_summary.append({"path": n["path"], "unresolved": specs})

    # 5. Deepest dependency chain
    deepest_chain = compute_deepest_dependency_chain(node_paths, adj, cycle_nodes)

    # 6. Folder coupling ratio
    folder_coupling_ratio = (
        round(cross_folder_edges / max(1, total_edges), 3) if total_edges > 0 else 0.0
    )

    return {
        "node_count": len(nodes),
        "edge_count": total_edges,
        "cycles": cycle_paths,
        "cycles_count": len(cycle_paths),
        "hub_files": top_hubs,
        "critical_hubs_count": len(critical_hubs),
        "orphans": orphans[:25],
        "orphans_count": len(orphans),
        "orphan_ratio": round(orphan_ratio, 3),
        "unresolved_imports": unresolved_summary[:20],
        "unresolved_imports_count": total_unresolved,
        "deepest_chain": deepest_chain,
        "deepest_chain_depth": len(deepest_chain),
        "folder_coupling_ratio": folder_coupling_ratio,
    }


def extract_delivery_safety_signals(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Checks for test coverage presence and CI workflows."""
    test_files = [
        n["path"]
        for n in nodes
        if any(tok in n["path"].lower() for tok in ["test", "spec", "__tests__"])
    ]
    ci_workflows = [
        n["path"]
        for n in nodes
        if n["path"].startswith(".github/workflows/")
        and (n["path"].endswith(".yml") or n["path"].endswith(".yaml"))
    ]

    return {
        "has_tests": len(test_files) > 0,
        "test_files_count": len(test_files),
        "has_ci": len(ci_workflows) > 0,
        "ci_workflow_files": ci_workflows,
    }


async def extract_dependency_signals(session, repo_id: uuid.UUID) -> dict[str, Any]:
    """Queries pending code usages and breaking changes for this repo."""
    usages_res = await session.execute(
        select(CodeUsage, DetectedChange)
        .join(DetectedChange, CodeUsage.detected_change_id == DetectedChange.id)
        .where(
            CodeUsage.repo_id == repo_id,
            CodeUsage.status == "pending",
        )
    )
    breaking_rows = usages_res.all()

    breaking_pkgs = list(
        {dc.description.split()[0] if dc.description else "dependency" for cu, dc in breaking_rows}
    )

    return {
        "breaking_changes_count": len(breaking_rows),
        "breaking_packages": breaking_pkgs,
        "total_dependencies": len(breaking_pkgs),
        "outdated_packages_count": 0,
    }


async def extract_verification_signals(session, repo_id: uuid.UUID) -> dict[str, Any]:
    """Queries pull request acceptance and test outcome history."""
    prs_res = await session.execute(select(PullRequest).where(PullRequest.repo_id == repo_id))
    all_prs = prs_res.scalars().all()

    total_prs = len(all_prs)
    merged_prs = [p for p in all_prs if p.merged or p.status == "merged"]
    open_prs = [p for p in all_prs if p.status == "open"]

    merge_rate = (len(merged_prs) / total_prs) if total_prs > 0 else None

    # Query empirical test outcomes from ValidationRuns for this repo
    val_res = await session.execute(
        select(ValidationRun.tests_pass)
        .join(Patch, ValidationRun.patch_id == Patch.id)
        .join(CodeUsage, Patch.code_usage_id == CodeUsage.id)
        .where(
            CodeUsage.repo_id == repo_id,
            ValidationRun.tests_pass.is_not(None),
        )
    )
    test_outcomes = val_res.scalars().all()

    pass_rate: float | None = None
    if test_outcomes and len(test_outcomes) > 0:
        passed = sum(1 for t in test_outcomes if t)
        pass_rate = round(passed / len(test_outcomes), 3)

    return {
        "total_prs": total_prs,
        "merged_prs_count": len(merged_prs),
        "open_review_prs_count": len(open_prs),
        "merge_rate": round(merge_rate, 3) if merge_rate is not None else None,
        "pass_rate": pass_rate,
    }


# ─── Findings Synthesizer ─────────────────────────────────────────────────────


def generate_findings(
    structure: dict[str, Any],
    dependency: dict[str, Any],
    change_safety: dict[str, Any],
    verification: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Generates actionable, fact-grounded findings with deep-links to 3D Atlas.
    """
    findings: list[dict[str, Any]] = []

    # 1. Circular Imports (Critical)
    if structure.get("cycles_count", 0) > 0:
        cycles = structure["cycles"]
        first_cycle = cycles[0]
        focus_target = first_cycle[0] if first_cycle else ""
        cycle_str = " → ".join([c.split("/")[-1] for c in first_cycle[:4]])
        if len(first_cycle) > 4:
            cycle_str += " …"

        findings.append(
            {
                "severity": "critical",
                "title": f"Circular dependency cycle detected ({structure['cycles_count']} total)",
                "evidence": {
                    "cycles_count": structure["cycles_count"],
                    "sample_cycle": first_cycle,
                },
                "why_it_matters": f"Cycle in module graph ({cycle_str}) causes execution order race conditions and memory leaks.",
                "what_to_do": f"Refactor shared exports into a separate module to break the cycle at {focus_target}.",
                "atlas_deep_link": f"?focus={focus_target}",
            }
        )

    # 2. Critical Breaking Changes (Critical/Warning)
    if dependency.get("breaking_changes_count", 0) > 0:
        findings.append(
            {
                "severity": "critical",
                "title": f"{dependency['breaking_changes_count']} upstream breaking changes pending patch validation",
                "evidence": {
                    "packages": dependency["breaking_packages"],
                    "count": dependency["breaking_changes_count"],
                },
                "why_it_matters": "Active runtime or signature discrepancies in imported dependencies threaten build stability.",
                "what_to_do": "Review and merge automated synthetic AST patches generated by Telex engine.",
                "atlas_deep_link": "",
            }
        )

    # 3. High-Churn Hub Files (Warning)
    critical_hubs = [h for h in structure.get("hub_files", []) if h["fan_in"] >= 15]
    if critical_hubs:
        top_hub = critical_hubs[0]
        findings.append(
            {
                "severity": "warning",
                "title": f"High fan-in architectural nexus: {top_hub['path'].split('/')[-1]}",
                "evidence": {
                    "path": top_hub["path"],
                    "fan_in": top_hub["fan_in"],
                    "fan_out": top_hub["fan_out"],
                },
                "why_it_matters": f"{top_hub['path']} is imported by {top_hub['fan_in']} files. Any breaking modification propagates widely.",
                "what_to_do": "Decouple core interfaces and protect with strict unit test coverage.",
                "atlas_deep_link": f"?focus={top_hub['path']}",
            }
        )

    # 4. Missing Test Suite (Warning)
    if not change_safety.get("has_tests", True):
        findings.append(
            {
                "severity": "warning",
                "title": "No automated test suite detected in repository",
                "evidence": {"test_files_count": 0},
                "why_it_matters": "Automated patch verification and regression prevention require test verification suites.",
                "what_to_do": "Add test suites (e.g. pytest, vitest, jest) matching project runtime.",
                "atlas_deep_link": "",
            }
        )

    # 5. Missing CI Pipeline (Info)
    if not change_safety.get("has_ci", True):
        findings.append(
            {
                "severity": "info",
                "title": "GitHub Actions CI pipeline not configured",
                "evidence": {"ci_workflows": []},
                "why_it_matters": "Pushing changes without automated CI gates risks landing undetected breakage.",
                "what_to_do": "Add a .github/workflows/ci.yml workflow for continuous verification.",
                "atlas_deep_link": "",
            }
        )

    # 6. Unresolved Internal Imports (Info)
    if structure.get("unresolved_imports_count", 0) > 0:
        first_unres = structure["unresolved_imports"][0]
        findings.append(
            {
                "severity": "info",
                "title": f"{structure['unresolved_imports_count']} unresolved static import specifiers",
                "evidence": {
                    "sample_file": first_unres["path"],
                    "specifiers": first_unres["unresolved"],
                },
                "why_it_matters": "Dynamic requires or missing alias path mappings limit static boundary analysis.",
                "what_to_do": "Ensure tsconfig/jsconfig paths are synchronized and avoid dynamic imports in core files.",
                "atlas_deep_link": f"?focus={first_unres['path']}",
            }
        )

    return findings


# ─── LLM Synthesis ────────────────────────────────────────────────────────────


def _validate_recommendations(
    do_first: list[str],
    findings: list[dict[str, Any]],
    signals: dict[str, Any],
) -> bool:
    if not do_first:
        return False

    # Extract all known files and packages from input
    known_packages = set(signals.get("dependency", {}).get("breaking_packages", []))
    known_files = set()
    for f in findings:
        link = f.get("atlas_deep_link", "")
        if "focus=" in link:
            known_files.add(link.split("focus=")[-1].split("&")[0])
        title = f.get("title", "")
        for word in title.split():
            if "/" in word or any(
                word.endswith(ext) for ext in (".ts", ".js", ".py", ".go", ".rs", ".json")
            ):
                known_files.add(word.strip("`'\",():"))

    # Also build a set of valid finding concepts/topics
    finding_texts = [
        f"{f.get('title', '')} {f.get('why_it_matters', '')} {f.get('what_to_do', '')}".lower()
        for f in findings
    ]

    for item in do_first:
        item_lower = item.lower()
        # Check if the item relates to at least one finding
        grounded_in_finding = any(
            any(
                w in item_lower
                for w in [
                    "cycle",
                    "circular",
                    "import",
                    "hub",
                    "test",
                    "ci",
                    "workflow",
                    "orphan",
                    "breaking",
                    "package",
                    "dependency",
                    "pr",
                    "merge",
                    "review",
                    "gate",
                    "typecheck",
                ]
            )
            and any(kw in f_text for kw in item_lower.split() if len(kw) > 3)
            for f_text in finding_texts
        )
        if not grounded_in_finding and findings:
            logger.warning("Rejecting LLM recommendation not grounded in findings: %s", item)
            return False

        # Check for invented file paths or packages
        for token in item.split():
            clean_tok = token.strip("`'\",():;")
            if clean_tok.startswith("@") and "/" in clean_tok:
                if clean_tok not in known_packages:
                    logger.warning(
                        "Rejecting LLM recommendation with unknown package: %s", clean_tok
                    )
                    return False
            if (
                "/" in clean_tok
                or any(clean_tok.endswith(ext) for ext in (".ts", ".tsx", ".js", ".jsx", ".py"))
            ) and not clean_tok.startswith("http"):
                if clean_tok not in known_files and not any(clean_tok in kf for kf in known_files):
                    logger.warning(
                        "Rejecting LLM recommendation with unknown file entity: %s", clean_tok
                    )
                    return False

    return True


async def synthesize_analysis_prose(
    repo_name: str,
    score: int,
    sub_scores: dict[str, int | None],
    findings: list[dict[str, Any]],
    signals: dict[str, Any],
) -> tuple[str, list[str]]:
    """
    Synthesizes executive summary and prioritized action items via Gemini.
    Strictly follows zero-hallucination contract with deterministic fallback.
    """
    fallback_summary = (
        f"Repository {repo_name} scored {score}/100 across architectural structure, "
        f"dependency health, and change safety. "
        f"{len(findings)} actionable findings identified across {signals.get('structure', {}).get('node_count', 0)} files."
    )
    fallback_do_first = [f["what_to_do"] for f in findings if f.get("what_to_do")][:3] or [
        "Maintain continuous integration verification gates."
    ]

    try:
        from services.patch_providers import get_patch_provider

        try:
            gemini = get_patch_provider("gemini")
        except Exception as key_err:
            logger.warning("No Gemini API key available for analysis prose synthesis: %s", key_err)
            return fallback_summary, fallback_do_first

        findings_payload = [
            {
                "severity": f["severity"],
                "title": f["title"],
                "why_it_matters": f["why_it_matters"],
                "what_to_do": f["what_to_do"],
            }
            for f in findings
        ]

        prompt = f"""
You are an expert software architect reviewing an automated repository scan.
Repository: {repo_name}
Computed Score: {score}/100
Sub-Scores: {json.dumps(sub_scores)}
Identified Findings: {json.dumps(findings_payload)}

Write a concise executive summary and prioritized action items.
Rules:
1. Executive summary must be <= 150 words, professional, technical, and objective.
2. 'do_this_first' must contain 2 to 4 actionable bullet items derived STRICTLY from the findings.
3. NEVER invent numbers or reference packages/files not in the input.

Return ONLY valid JSON with this schema:
{{
  "executive_summary": "concise summary",
  "do_this_first": ["action 1", "action 2"]
}}
"""
        response = await asyncio.wait_for(
            gemini.client.aio.models.generate_content(
                model=gemini._model_name,
                contents=prompt,
            ),
            timeout=8.0,
        )
        text = response.text or "{}"
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        summary = str(data.get("executive_summary") or fallback_summary)
        do_first = data.get("do_this_first")
        if isinstance(do_first, list) and len(do_first) > 0:
            cleaned_actions = [str(item) for item in do_first[:4]]
            if _validate_recommendations(cleaned_actions, findings, signals):
                return summary, cleaned_actions
            logger.warning("LLM recommendations failed grounding validation, falling back")
        return summary, fallback_do_first

    except Exception as exc:
        logger.warning("LLM analysis prose synthesis fallback: %s", exc)
        return fallback_summary, fallback_do_first


# ─── Main Pipeline ────────────────────────────────────────────────────────────


async def run_repo_analysis(
    repo_id: uuid.UUID | str, commit_sha: str | None = None
) -> dict[str, Any]:
    """
    Executes a complete evidence-based run analysis for the specified repo:
    1. Loads structure from atlas tables (or fallback to RepoAtlasGraph)
    2. Gathers dependency and verification signals
    3. Calculates deterministic sub-scores and composite score
    4. Generates findings and LLM prose
    5. Persists to repo_analysis_runs table
    """
    repo_uuid = uuid.UUID(str(repo_id))

    async with AsyncSessionLocal() as session:
        repo = await session.get(Repo, repo_uuid)
        if not repo:
            raise ValueError(f"Repo {repo_id} not found")

        resolved_sha = commit_sha or "HEAD"

        # 1. Load Atlas Nodes & Edges
        nodes_res = await session.execute(select(AtlasNode).where(AtlasNode.repo_id == repo_uuid))
        raw_nodes = nodes_res.scalars().all()

        edges_res = await session.execute(select(AtlasEdge).where(AtlasEdge.repo_id == repo_uuid))
        raw_edges = edges_res.scalars().all()

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        if raw_nodes:
            nodes = [
                {
                    "path": n.path,
                    "name": n.name,
                    "dir": n.dir,
                    "ext": n.ext,
                    "depth": n.depth,
                    "unresolved_specifiers": n.unresolved_specifiers or [],
                }
                for n in raw_nodes
            ]
            edges = [
                {
                    "source_path": e.source_path,
                    "target_path": e.target_path,
                    "kind": e.kind,
                }
                for e in raw_edges
            ]
        else:
            # Fallback to latest ready RepoAtlasGraph
            graph_res = await session.execute(
                select(RepoAtlasGraph)
                .where(
                    RepoAtlasGraph.repo_id == repo_uuid,
                    RepoAtlasGraph.status == "ready",
                )
                .order_by(RepoAtlasGraph.created_at.desc())
                .limit(1)
            )
            latest_graph = graph_res.scalar_one_or_none()
            if latest_graph and latest_graph.graph_json:
                gjson = latest_graph.graph_json
                resolved_sha = latest_graph.commit_sha
                nodes = [
                    {
                        "path": n.get("id") or n.get("path"),
                        "name": n.get("name", ""),
                        "dir": n.get("dir", ""),
                        "ext": n.get("ext", ""),
                        "depth": n.get("depth", 0),
                        "unresolved_specifiers": n.get("unresolved_specifiers", []),
                    }
                    for n in gjson.get("nodes", [])
                    if n.get("id") or n.get("path")
                ]
                edges = [
                    {
                        "source_path": e.get("source"),
                        "target_path": e.get("target"),
                        "kind": e.get("kind", "static"),
                    }
                    for e in gjson.get("edges", [])
                    if e.get("source") and e.get("target")
                ]

        # 2. Extract Signals
        structure_signals = extract_structure_signals(nodes, edges)
        safety_signals = extract_delivery_safety_signals(nodes)
        dependency_signals = await extract_dependency_signals(session, repo_uuid)
        verification_signals = await extract_verification_signals(session, repo_uuid)

        signals_bundle = {
            "structure": structure_signals,
            "dependency": dependency_signals,
            "change_safety": safety_signals,
            "verification": verification_signals,
        }

        # 3. Compute Deterministic Sub-Scores
        structure_score = compute_structure_score(
            cycles_count=structure_signals["cycles_count"],
            hub_files_count=structure_signals["critical_hubs_count"],
            orphan_ratio=structure_signals["orphan_ratio"],
            has_unresolved_imports=structure_signals["unresolved_imports_count"] > 0,
            node_count=structure_signals["node_count"],
        )

        dependency_score = compute_dependency_score(
            breaking_pkgs_count=len(dependency_signals["breaking_packages"]),
            outdated_pkgs_count=dependency_signals["outdated_packages_count"],
            total_dependencies=dependency_signals["total_dependencies"],
        )

        change_safety_score = compute_change_safety_score(
            has_tests=safety_signals["has_tests"],
            has_ci=safety_signals["has_ci"],
            high_churn_hubs_count=structure_signals["critical_hubs_count"],
            signals_available=len(nodes) > 0,
        )

        verification_score = compute_verification_score(
            merge_rate=verification_signals["merge_rate"],
            pass_rate=verification_signals["pass_rate"],
            open_review_prs_count=verification_signals["open_review_prs_count"],
            total_patches_evaluated=verification_signals["total_prs"],
        )

        sub_scores = {
            "structure": structure_score,
            "dependency": dependency_score,
            "change_safety": change_safety_score,
            "verification": verification_score,
        }

        composite_score = compute_composite_score(sub_scores)

        # 4. Synthesize Findings
        findings = generate_findings(
            structure_signals, dependency_signals, safety_signals, verification_signals
        )

        # 5. Fetch previous run for delta comparison
        prev_res = await session.execute(
            select(RepoAnalysisRun)
            .where(RepoAnalysisRun.repo_id == repo_uuid)
            .order_by(RepoAnalysisRun.created_at.desc())
            .limit(1)
        )
        prev_run = prev_res.scalar_one_or_none()
        delta_score = (composite_score - prev_run.score) if prev_run else 0
        repo_full_name = repo.full_name

    # 6. Synthesize Prose outside AsyncSessionLocal to release connection before Gemini request
    summary, do_first = await synthesize_analysis_prose(
        repo_name=repo_full_name,
        score=composite_score,
        sub_scores=sub_scores,
        findings=findings,
        signals=signals_bundle,
    )

    # 7. Persist Run to Database in fresh transaction
    async with AsyncSessionLocal() as session:
        run_record = RepoAnalysisRun(
            id=uuid.uuid4(),
            repo_id=repo_uuid,
            head_sha=resolved_sha,
            score=composite_score,
            sub_scores=sub_scores,
            findings=findings,
            signals=signals_bundle,
            executive_summary=summary,
            do_this_first=do_first,
            created_at=datetime.now(timezone.utc),
        )
        session.add(run_record)
        await session.commit()

        run_dict = {
            "id": str(run_record.id),
            "repo_id": str(run_record.repo_id),
            "head_sha": run_record.head_sha,
            "score": run_record.score,
            "sub_scores": run_record.sub_scores,
            "findings": run_record.findings,
            "signals": run_record.signals,
            "executive_summary": run_record.executive_summary,
            "do_this_first": run_record.do_this_first,
            "created_at": run_record.created_at.isoformat(),
        }

        prev_dict = (
            {
                "id": str(prev_run.id),
                "head_sha": prev_run.head_sha,
                "score": prev_run.score,
                "created_at": prev_run.created_at.isoformat(),
            }
            if prev_run
            else None
        )

        logger.info(
            "run_repo_analysis complete: repo=%s score=%d delta=%+d findings=%d",
            repo.full_name,
            composite_score,
            delta_score,
            len(findings),
        )

        return {
            "latest": run_dict,
            "previous": prev_dict,
            "delta_score": delta_score,
            # Backward-compatible fields for AIExplainOut
            "summary": summary,
            "risk_score": max(0, 100 - composite_score),
            "architecture_verdict": f"Score {composite_score}/100 — {len(findings)} findings detected.",
            "recommended_actions": do_first,
            "commit_insights": [],
        }
