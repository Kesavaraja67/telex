"""
Unit tests for services/registry_watcher.py — npm registry polling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.registry_watcher import fetch_latest_version, fetch_package_versions


@pytest.mark.asyncio
async def test_fetch_latest_version_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "dist-tags": {"latest": "2.0.0"},
        "time": {"2.0.0": "2026-09-01T12:00:00.000Z"},
        "versions": {
            "2.0.0": {
                "homepage": "https://axios-http.com",
            }
        },
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)):
        result = await fetch_latest_version("axios")
        assert result is not None
        assert result["version"] == "2.0.0"
        assert result["changelog_url"] == "https://axios-http.com"


@pytest.mark.asyncio
async def test_fetch_latest_version_error_returns_none():
    with patch("httpx.AsyncClient.get", AsyncMock(side_effect=Exception("HTTP 500"))):
        result = await fetch_latest_version("broken-pkg")
        assert result is None


@pytest.mark.asyncio
async def test_fetch_package_versions_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "versions": {
            "1.0.0": {},
            "1.1.0": {},
            "2.0.0": {},
        }
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)):
        versions = await fetch_package_versions("my-lib")
        assert versions == ["2.0.0", "1.1.0", "1.0.0"]


@pytest.mark.asyncio
async def test_fetch_package_versions_error_returns_empty():
    with patch("httpx.AsyncClient.get", AsyncMock(side_effect=Exception("Network error"))):
        versions = await fetch_package_versions("unknown")
        assert versions == []


@pytest.mark.asyncio
async def test_fetch_latest_version_pypi_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "info": {
            "version": "1.5.0",
            "project_urls": {"Changelog": "https://pypi.org/project/requests/#changelog"},
            "description": "## 1.5.0 Release\n- Breaking: removed old auth API",
        },
        "releases": {"1.5.0": [{"upload_time_iso_8601": "2026-09-10T15:30:00Z"}]},
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)):
        result = await fetch_latest_version("requests", ecosystem="pypi")
        assert result is not None
        assert result["version"] == "1.5.0"
        assert result["changelog_url"] == "https://pypi.org/project/requests/#changelog"
        assert "removed old auth API" in result["changelog_raw"]


@pytest.mark.asyncio
async def test_fetch_package_versions_pypi_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "releases": {
            "1.0.0": [],
            "1.1.0": [],
            "1.5.0": [],
        }
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)):
        versions = await fetch_package_versions("requests", ecosystem="pypi")
        assert versions == ["1.5.0", "1.1.0", "1.0.0"]


@pytest.mark.asyncio
async def test_fetch_unsupported_ecosystem():
    result = await fetch_latest_version("foo", ecosystem="unsupported-eco")
    assert result is None
    versions = await fetch_package_versions("foo", ecosystem="unsupported-eco")
    assert versions == []
