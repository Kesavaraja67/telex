"""
npm registry watcher — polls for new versions of tracked packages.
"""
import logging
from datetime import datetime
from typing import Optional

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
    url = f"{NPM_REGISTRY}/{package_name}/latest"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            published_raw = data.get("time", {}).get(data.get("version", ""), None)
            published_at = (
                datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                if published_raw
                else None
            )
            return {
                "version": data.get("version", ""),
                "published_at": published_at,
                "changelog_url": data.get("homepage") or data.get("repository", {}).get("url"),
            }
    except Exception as exc:
        logger.error("fetch_latest_version(%s) failed: %s", package_name, exc)
        return None


async def fetch_package_versions(package_name: str) -> list[str]:
    """Return all published versions for a package, newest first."""
    url = f"{NPM_REGISTRY}/{package_name}"
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
