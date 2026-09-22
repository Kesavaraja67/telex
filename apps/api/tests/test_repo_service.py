"""
Unit tests for services/repo_service.py — repo metadata fetching, benchmark isolation, and core repos loading.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.repo_service import (
    BENCHMARK_REPOS,
    fetch_repo_metadata_from_github,
    get_core_repositories_async,
)


def test_benchmark_repos_structure():
    assert len(BENCHMARK_REPOS) == 4
    ids = [b["id"] for b in BENCHMARK_REPOS]
    assert "next-js" in ids
    assert "openai-python" in ids
    assert "stripe-node" in ids
    assert "fastapi" in ids
    for b in BENCHMARK_REPOS:
        assert b["category"] == "benchmark"


def test_fetch_repo_metadata_fallback():
    # If GitHub network calls fail, returns default dictionary safely
    with patch("urllib.request.urlopen", side_effect=Exception("network error")):
        meta = fetch_repo_metadata_from_github("some/repo")
        assert "TypeScript" in meta["languages"]
        assert meta["dependencies"] == ["typescript"]


@pytest.mark.asyncio
async def test_get_core_repositories_benchmark_isolation():
    # When include_benchmarks=False and DB is empty, should return 0 repos
    with patch("services.repo_service.sync_github_app_repositories_async"):
        with patch("db.session.AsyncSessionLocal") as mock_session_ctx:
            mock_session = MagicMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_session.execute.return_value = MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            )
            mock_session_ctx.return_value = mock_session

            repos_default = await get_core_repositories_async(
                force_sync=False, include_benchmarks=False
            )
            assert len(repos_default) == 0

            with patch("services.repo_service.fetch_live_github_commits", return_value=[]):
                repos_with_benchmarks = await get_core_repositories_async(
                    force_sync=False, include_benchmarks=True
                )
                assert len(repos_with_benchmarks) == 4
                assert all(r["category"] == "benchmark" for r in repos_with_benchmarks)


def test_parse_github_datetime():
    from services.repo_service import _parse_github_datetime

    assert _parse_github_datetime(None) == "recently"
    assert _parse_github_datetime("") == "recently"
    assert (
        "ago" in _parse_github_datetime("2026-09-17T12:00:00Z")
        or _parse_github_datetime("2026-09-17T12:00:00Z") != ""
    )


def test_fetch_live_github_commits_mocked():
    from services.repo_service import fetch_live_github_commits
    import json

    mock_payload = [
        {
            "sha": "1234567890abcdef",
            "commit": {
                "message": "fix: resolve edge case",
                "author": {
                    "name": "Alice",
                    "email": "alice@test.com",
                    "date": "2026-09-17T10:00:00Z",
                },
            },
            "author": {"login": "alice"},
        }
    ]
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_payload).encode()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        commits = fetch_live_github_commits("owner/test-repo", limit=1)
        assert len(commits) == 1
        assert commits[0]["short_hash"] == "1234567"
        assert commits[0]["author"] == "alice"
        assert commits[0]["message"] == "fix: resolve edge case"


def test_fetch_repo_metadata_package_json():
    import json
    from services.repo_service import fetch_repo_metadata_from_github

    mock_desc_resp = MagicMock()
    mock_desc_resp.read.return_value = json.dumps(
        {"description": "Test Repo", "language": "TypeScript"}
    ).encode()
    mock_desc_resp.__enter__.return_value = mock_desc_resp
    mock_desc_resp.__exit__.return_value = None

    mock_lang_resp = MagicMock()
    mock_lang_resp.read.return_value = json.dumps({"TypeScript": 5000, "JavaScript": 1000}).encode()
    mock_lang_resp.__enter__.return_value = mock_lang_resp
    mock_lang_resp.__exit__.return_value = None

    mock_pkg_resp = MagicMock()
    mock_pkg_resp.read.return_value = json.dumps(
        {"dependencies": {"react": "^18.0.0", "next": "^14.0.0"}}
    ).encode()
    mock_pkg_resp.__enter__.return_value = mock_pkg_resp
    mock_pkg_resp.__exit__.return_value = None

    def fake_urlopen(req, timeout=4):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "languages" in url:
            return mock_lang_resp
        elif "package.json" in url:
            return mock_pkg_resp
        return mock_desc_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        meta = fetch_repo_metadata_from_github("owner/ts-app")
        assert meta["description"] == "Test Repo"
        assert "TypeScript" in meta["languages"]
        assert "react" in meta["dependencies"]
        assert "next" in meta["dependencies"]


@pytest.mark.asyncio
async def test_sync_github_app_repositories_no_credentials():
    from services.repo_service import sync_github_app_repositories_async

    with patch("services.repo_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(github_app_id="", github_app_private_key="")
        # Should return early without error
        await sync_github_app_repositories_async()


@pytest.mark.asyncio
async def test_sync_github_app_repositories_success():
    import uuid
    from db.models import Repo
    from services.repo_service import sync_github_app_repositories_async

    mock_inst = MagicMock()
    mock_inst.id = 101
    mock_inst.raw_data = {"account": {"login": "test-org", "type": "Organization"}}

    mock_integration = MagicMock()
    mock_integration.get_installations.return_value = [mock_inst]
    mock_integration.get_access_token.return_value = MagicMock(token="fake-token")

    existing_repo = Repo(
        id=uuid.uuid4(),
        installation_id=uuid.uuid4(),
        github_repo_id=1,
        full_name="test-org/repo-1",
        default_branch="main",
        is_active=True,
    )
    stale_repo = Repo(
        id=uuid.uuid4(),
        installation_id=uuid.uuid4(),
        github_repo_id=999,
        full_name="test-org/old-repo",
        default_branch="main",
        is_active=True,
    )

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    inst_result = MagicMock()
    inst_result.scalar_one_or_none.return_value = None

    repo1_result = MagicMock()
    repo1_result.scalar_one_or_none.return_value = existing_repo

    repo2_result = MagicMock()
    repo2_result.scalar_one_or_none.return_value = None

    all_repos_result = MagicMock()
    all_repos_result.scalars.return_value = MagicMock(
        all=MagicMock(return_value=[existing_repo, stale_repo])
    )

    mock_session.execute = AsyncMock(
        side_effect=[inst_result, repo1_result, repo2_result, all_repos_result]
    )
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    resp1 = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value={
                "total_count": 2,
                "repositories": [
                    {"id": 1, "full_name": "test-org/repo-1", "default_branch": "main"}
                ],
            }
        ),
    )
    resp2 = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value={
                "total_count": 2,
                "repositories": [
                    {"id": 2, "full_name": "test-org/repo-2", "default_branch": "main"}
                ],
            }
        ),
    )

    mock_http_client = AsyncMock()
    mock_http_client.__aenter__.return_value = mock_http_client
    mock_http_client.__aexit__.return_value = None
    mock_http_client.get = AsyncMock(side_effect=[resp1, resp2])

    with patch("services.repo_service.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            github_app_id="12345",
            github_app_private_key="fake-pem-key",
        )
        with patch("github.GithubIntegration", return_value=mock_integration):
            with patch("db.session.AsyncSessionLocal", return_value=mock_session):
                with patch("httpx.AsyncClient", return_value=mock_http_client):
                    await sync_github_app_repositories_async()

    assert existing_repo.is_active is True
    assert stale_repo.is_active is False


@pytest.mark.asyncio
async def test_get_core_repositories_with_db_repos():
    import uuid
    from datetime import datetime, timezone
    from db.models import Repo

    mock_db_repo = Repo(
        id=uuid.uuid4(),
        full_name="org/live-repo",
        default_branch="main",
        is_active=True,
        requires_tests=True,
        requires_typecheck=True,
        created_at=datetime.now(timezone.utc),
    )

    with patch("services.repo_service.sync_github_app_repositories_async"):
        with patch("services.repo_service.fetch_live_github_commits", return_value=[]):
            with patch(
                "services.repo_service.fetch_repo_metadata_from_github",
                return_value={
                    "description": "Live repo",
                    "languages": ["Python"],
                    "dependencies": ["fastapi"],
                },
            ):
                with patch("db.session.AsyncSessionLocal") as mock_session_ctx:
                    mock_session = MagicMock()
                    mock_session.__aenter__.return_value = mock_session
                    mock_session.__aexit__.return_value = None

                    call_idx = 0

                    def fake_execute(stmt):
                        nonlocal call_idx
                        call_idx += 1
                        mock_res = MagicMock()
                        if call_idx == 1:
                            mock_res.scalars.return_value = MagicMock(
                                all=MagicMock(return_value=[mock_db_repo])
                            )
                        else:
                            mock_res.all.return_value = [(mock_db_repo.id, 2)]
                            mock_res.scalar_one.return_value = 2  # PR count
                        return mock_res

                    mock_session.execute = AsyncMock(side_effect=fake_execute)
                    mock_session_ctx.return_value = mock_session

                    repos = await get_core_repositories_async(
                        force_sync=False, include_benchmarks=False
                    )
                    assert len(repos) == 1
                    r = repos[0]
                    assert r["full_name"] == "org/live-repo"
                    assert r["patch_count"] == 2
                    assert r["requires_tests"] is True
                    assert r["category"] == "personal"
