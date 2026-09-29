"""
Tests for Evidence-Based Run Analysis Engine — Phase 4.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from db.models import Installation, Repo, RepoAnalysisRun, RepoAtlasGraph
from main import app
from services.analysis_weights import (
    compute_change_safety_score,
    compute_composite_score,
    compute_dependency_score,
    compute_structure_score,
    compute_verification_score,
)
from services.repo_analysis import (
    compute_deepest_dependency_chain,
    extract_structure_signals,
    find_cycles_tarjan,
    generate_findings,
    run_repo_analysis,
)


def test_tarjan_cycle_detection():
    # A -> B -> C -> A
    adj = {
        "A": ["B"],
        "B": ["C"],
        "C": ["A"],
        "D": ["A"],
    }
    nodes = ["A", "B", "C", "D"]
    cycles = find_cycles_tarjan(nodes, adj)
    assert len(cycles) == 1
    cycle = cycles[0]
    assert "A" in cycle and "B" in cycle and "C" in cycle
    assert "D" not in cycle


def test_tarjan_acyclic():
    # A -> B -> C
    adj = {
        "A": ["B"],
        "B": ["C"],
        "C": [],
    }
    nodes = ["A", "B", "C"]
    cycles = find_cycles_tarjan(nodes, adj)
    assert len(cycles) == 0


def test_deepest_dependency_chain():
    # A -> B -> C -> D (depth 4)
    adj = {
        "A": ["B", "E"],
        "B": ["C"],
        "C": ["D"],
        "D": [],
        "E": [],
    }
    nodes = ["A", "B", "C", "D", "E"]
    longest = compute_deepest_dependency_chain(nodes, adj, cycle_nodes=set())
    assert len(longest) == 4
    assert longest == ["A", "B", "C", "D"]


def test_extract_structure_signals():
    nodes = [
        {"path": "src/a.ts", "ext": ".ts", "unresolved_specifiers": []},
        {"path": "src/b.ts", "ext": ".ts", "unresolved_specifiers": ["./missing"]},
        {"path": "src/c.ts", "ext": ".ts", "unresolved_specifiers": []},
        {"path": "src/orphan.ts", "ext": ".ts", "unresolved_specifiers": []},
    ]
    edges = [
        {"source_path": "src/a.ts", "target_path": "src/b.ts"},
        {"source_path": "src/b.ts", "target_path": "src/c.ts"},
        {"source_path": "src/c.ts", "target_path": "src/a.ts"},
    ]
    sig = extract_structure_signals(nodes, edges)
    assert sig["node_count"] == 4
    assert sig["edge_count"] == 3
    assert sig["cycles_count"] == 1
    assert "src/orphan.ts" in sig["orphans"]
    assert sig["unresolved_imports_count"] == 1


def test_scoring_weights():
    # Structure score
    struct_score = compute_structure_score(
        cycles_count=1,
        hub_files_count=0,
        orphan_ratio=0.05,
        has_unresolved_imports=True,
        node_count=20,
    )
    # 90 - 10 (cycle) - 0 - 1.5 (orphan) = 78
    assert struct_score == 78

    # Dependency score
    dep_score = compute_dependency_score(
        breaking_pkgs_count=1,
        outdated_pkgs_count=2,
        total_dependencies=5,
    )
    # 100 - 20 - 10 = 70
    assert dep_score == 70

    # Composite score
    sub: dict[str, int | None] = {
        "structure": 80,
        "dependency": 80,
        "change_safety": 80,
        "verification": 80,
    }
    composite = compute_composite_score(sub)
    assert composite == 80

    # Boundary and null states
    assert compute_structure_score(0, 0, 0.0, True, node_count=0) is None
    assert compute_dependency_score(0, 0, total_dependencies=0) is None
    assert compute_change_safety_score(True, True, 0, signals_available=False) is None
    assert compute_verification_score(None, None, 0, total_patches_evaluated=0) is None
    assert compute_composite_score({"structure": None, "dependency": None}) == 75


@pytest.mark.asyncio
async def test_run_repo_analysis_e2e():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)

    graph_row = RepoAtlasGraph(
        repo_id=repo_id,
        commit_sha="c0ffee1",
        status="ready",
        graph_json={
            "nodes": [
                {"id": "src/main.ts", "name": "main.ts", "dir": "src", "ext": ".ts"},
                {"id": "src/api.ts", "name": "api.ts", "dir": "src", "ext": ".ts"},
            ],
            "edges": [
                {"source": "src/main.ts", "target": "src/api.ts"},
            ],
        },
    )

    with patch("services.repo_analysis.AsyncSessionLocal") as mock_ctx:
        mock_session = MagicMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        async def fake_get(model, pk):
            if model is Repo:
                return repo
            return None

        mock_session.get = AsyncMock(side_effect=fake_get)

        call_count = 0

        def fake_execute(stmt):
            r = MagicMock()
            s = str(stmt).lower()
            if "atlas_nodes" in s:
                r.scalars.return_value.all.return_value = []
            elif "atlas_edges" in s:
                r.scalars.return_value.all.return_value = []
            elif "repo_atlas_graphs" in s:
                r.scalar_one_or_none.return_value = graph_row
            elif "code_usages" in s and "validation_runs" in s:
                r.scalars.return_value.all.return_value = []
            elif "code_usages" in s:
                r.all.return_value = []
            elif "pull_requests" in s:
                r.scalars.return_value.all.return_value = []
            elif "repo_analysis_runs" in s:
                r.scalar_one_or_none.return_value = None
            else:
                r.scalars.return_value.all.return_value = []
                r.scalar_one_or_none.return_value = None
                r.all.return_value = []
            return r

        mock_session.execute = AsyncMock(side_effect=fake_execute)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_ctx.return_value = mock_session

        res = await run_repo_analysis(repo_id, "c0ffee1")
        assert res["latest"]["score"] > 50
        assert res["delta_score"] == 0
        assert "findings" in res["latest"]
        assert mock_session.add.called
        added_run = mock_session.add.call_args[0][0]
        assert isinstance(added_run, RepoAnalysisRun)
        assert added_run.head_sha == "c0ffee1"


@pytest.mark.asyncio
async def test_get_repo_analysis_endpoint():
    repo_id = uuid.uuid4()
    inst_id = uuid.uuid4()
    repo = Repo(id=repo_id, full_name="owner/repo", installation_id=inst_id)
    inst = Installation(id=inst_id, github_installation_id=123)

    run1 = RepoAnalysisRun(
        id=uuid.uuid4(),
        repo_id=repo_id,
        head_sha="sha1",
        score=85,
        sub_scores={"structure": 85, "dependency": 90},
        findings=[],
        signals={},
        executive_summary="All nominal",
        do_this_first=["No action needed"],
    )

    with patch("routers.repos.get_authorized_repo", AsyncMock(return_value=(repo, inst))):
        with patch("routers.repos.AsyncSessionLocal") as mock_ctx:
            mock_session = MagicMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None

            mock_res = MagicMock()
            mock_res.scalars.return_value.all.return_value = [run1]
            mock_session.execute = AsyncMock(return_value=mock_res)
            mock_ctx.return_value = mock_session

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/repos/{repo_id}/analysis",
                    headers={"X-Demo-Key": "telex_demo_secret_2026"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["latest"]["score"] == 85
                assert data["delta_score"] == 0
                assert data["latest"]["executive_summary"] == "All nominal"
