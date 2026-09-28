"""
Registry watcher — polls package registries (npm, PyPI) for new versions of tracked packages.
"""

import logging
from datetime import datetime
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

NPM_REGISTRY = "https://registry.npmjs.org"
PYPI_REGISTRY = "https://pypi.org/pypi"


async def fetch_latest_version_npm(package_name: str) -> dict | None:
    """Fetch the latest version metadata for an npm package."""
    encoded_name = quote(package_name, safe="@/")
    url = f"{NPM_REGISTRY}/{encoded_name}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            latest_version = data.get("dist-tags", {}).get("latest", "")
            if not latest_version:
                return None

            published_raw = data.get("time", {}).get(latest_version)
            published_at = (
                datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                if published_raw
                else None
            )
            version_data = data.get("versions", {}).get(latest_version, {})
            changelog_url = version_data.get("homepage") or (
                version_data.get("repository", {}).get("url")
                if isinstance(version_data.get("repository"), dict)
                else None
            )
            # Raw changelog only from a version-specific release-note source (e.g. release_notes or changelog field)
            changelog_raw = (
                version_data.get("release_notes") or version_data.get("changelog") or None
            )

            return {
                "version": latest_version,
                "published_at": published_at,
                "changelog_url": changelog_url,
                "changelog_raw": changelog_raw,
            }
    except Exception as exc:
        logger.error("fetch_latest_version_npm(%s) failed: %s", package_name, exc)
        return None


async def fetch_latest_version_pypi(package_name: str) -> dict | None:
    """Fetch the latest version metadata for a PyPI package."""
    encoded_name = quote(package_name.strip())
    url = f"{PYPI_REGISTRY}/{encoded_name}/json"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            info = data.get("info", {})
            latest_version = info.get("version", "")
            if not latest_version:
                return None

            # Attempt to extract publication time from releases or urls
            published_at = None
            release_files = data.get("releases", {}).get(latest_version, [])
            if not release_files and "urls" in data:
                release_files = data.get("urls", [])

            if release_files and isinstance(release_files, list):
                first_file = release_files[0]
                upload_time = first_file.get("upload_time_iso_8601")
                if upload_time:
                    try:
                        published_at = datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
                    except Exception:
                        pass

            # Extract changelog URL from project_urls or home_page
            project_urls = info.get("project_urls") or {}
            changelog_url = (
                project_urls.get("Changelog")
                or project_urls.get("Change Log")
                or project_urls.get("Changes")
                or project_urls.get("Release Notes")
                or project_urls.get("History")
                or info.get("home_page")
                or info.get("project_url")
            )
            changelog_raw = info.get("description")

            return {
                "version": latest_version,
                "published_at": published_at,
                "changelog_url": changelog_url,
                "changelog_raw": changelog_raw,
            }
    except Exception as exc:
        logger.error("fetch_latest_version_pypi(%s) failed: %s", package_name, exc)
        return None


async def fetch_latest_version(package_name: str, ecosystem: str = "npm") -> dict | None:
    """
    Dispatch registry lookup by ecosystem.

    Returns:
        {
            "version": str,
            "published_at": datetime | None,
            "changelog_url": str | None,
            "changelog_raw": str | None,
        }
        or None on error or unsupported ecosystem.
    """
    eco = (ecosystem or "npm").strip().lower()
    if eco == "npm":
        return await fetch_latest_version_npm(package_name)
    elif eco == "pypi":
        return await fetch_latest_version_pypi(package_name)
    else:
        logger.warning("Unsupported registry ecosystem: %s", ecosystem)
        return None


async def fetch_package_versions_npm(package_name: str) -> list[str]:
    """Return all published versions for an npm package, newest first."""
    encoded_name = quote(package_name, safe="@/")
    url = f"{NPM_REGISTRY}/{encoded_name}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            versions = list(data.get("versions", {}).keys())
            return list(reversed(versions))
    except Exception as exc:
        logger.error("fetch_package_versions_npm(%s) failed: %s", package_name, exc)
        return []


async def fetch_package_versions_pypi(package_name: str) -> list[str]:
    """Return all published versions for a PyPI package, newest first."""
    encoded_name = quote(package_name.strip())
    url = f"{PYPI_REGISTRY}/{encoded_name}/json"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            releases = data.get("releases", {})
            versions = list(releases.keys())
            return list(reversed(versions))
    except Exception as exc:
        logger.error("fetch_package_versions_pypi(%s) failed: %s", package_name, exc)
        return []


async def fetch_package_versions(package_name: str, ecosystem: str = "npm") -> list[str]:
    """Return all published versions for a package, newest first, dispatched by ecosystem."""
    eco = (ecosystem or "npm").strip().lower()
    if eco == "npm":
        return await fetch_package_versions_npm(package_name)
    elif eco == "pypi":
        return await fetch_package_versions_pypi(package_name)
    else:
        logger.warning("Unsupported registry ecosystem: %s", ecosystem)
        return []
