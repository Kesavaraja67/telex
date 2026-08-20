"""
npm registry watcher — polls for new versions of tracked packages.
"""
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

NPM_REGISTRY = "https://registry.npmjs.org"


async def fetch_latest_version(package_name: str) -> Optional[dict]:
    """
    Fetch the latest version metadata for an npm package.

    Returns:
        {
            "version": str,
            "published_at": datetime,
            "changelog_url": str | None,
        }
        or None on error.
    """
    # Use the full packument so we get dist-tags.latest and time[version]
    encoded_name = quote(package_name, safe="@/")
    url = f"{NPM_REGISTRY}/{encoded_name}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            latest_version = data.get("dist-tags", {}).get("latest", "")
            published_raw = data.get("time", {}).get(latest_version)
            published_at = (
                datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                if published_raw
                else None
            )
            version_data = data.get("versions", {}).get(latest_version, {})
            return {
                "version": latest_version,
                "published_at": published_at,
                "changelog_url": version_data.get("homepage") or (
                    version_data.get("repository", {}).get("url") if isinstance(version_data.get("repository"), dict) else None
                ),
            }
    except Exception as exc:
        logger.error("fetch_latest_version(%s) failed: %s", package_name, exc)
        return None


async def fetch_package_versions(package_name: str) -> list[str]:
    """Return all published versions for a package, newest first."""
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
        logger.error("fetch_package_versions(%s) failed: %s", package_name, exc)
        return []
