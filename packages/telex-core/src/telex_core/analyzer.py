"""
Registry change extractor and breaking change analyzer.

Fetches release metadata from npm and PyPI and extracts breaking API changes.
Can run completely offline if a local changelog or release notes file is provided.
"""

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def fetch_npm_metadata(package_name: str, timeout: float = 10.0) -> dict[str, Any]:
    """Fetch package metadata from npm registry (full packument without abbreviated Accept header)."""
    url = f"https://registry.npmjs.org/{package_name}"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:
        logger.warning("Could not fetch npm metadata for %s: %s", package_name, exc)
    return {}


def fetch_pypi_metadata(
    package_name: str, version: str | None = None, timeout: float = 10.0
) -> dict[str, Any]:
    """Fetch package metadata from PyPI, using the release-specific endpoint when version is given."""
    if version:
        url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    else:
        url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:
        logger.warning("Could not fetch pypi metadata for %s: %s", package_name, exc)
    return {}


def parse_changelog_changes(changelog_text: str) -> list[dict[str, Any]]:
    """
    Parse breaking changes from raw changelog markdown or text.

    Detects:
      - Removed / dropped functions
      - Renamed functions (e.g. `foo` renamed to `bar` or `foo` -> `bar`)
      - Signature changes / parameter changes
      - Deprecations
      - General breaking behavior changes
    """
    changes: list[dict[str, Any]] = []
    lines = changelog_text.splitlines()

    in_breaking_section = False
    symbol_pat = re.compile(r"`([a-zA-Z0-9_\.\$]+)`|(?:\b([a-zA-Z_][a-zA-Z0-9_]*)\(\))")

    for line in lines:
        line_clean = line.strip()
        lower_line = line_clean.lower()

        # Section detection
        if any(
            h in lower_line
            for h in ["### breaking", "## breaking", "breaking changes", "breaking:"]
        ):
            in_breaking_section = True
            continue
        elif lower_line.startswith("#") and "breaking" not in lower_line:
            in_breaking_section = False

        if not line_clean.startswith(("-", "*", "•")) and not in_breaking_section:
            continue

        # Detect Renamed: `oldFunc` is renamed to `newFunc` or `old` -> `new`
        rename_match = re.search(
            r"(?:rename[d]?|moved)\s+[`']?([a-zA-Z0-9_\.]+)['`]?\s+(?:to|as|->)\s+[`']?([a-zA-Z0-9_\.]+)['`]?",
            line_clean,
            re.IGNORECASE,
        )
        if rename_match:
            old_sym, new_sym = rename_match.group(1), rename_match.group(2)
            changes.append(
                {
                    "symbol": old_sym,
                    "symbol_new": new_sym,
                    "change_type": "renamed",
                    "description": line_clean,
                    "confidence": 0.95,
                }
            )
            continue

        # Arrow rename: `old` -> `new`
        arrow_match = re.search(
            r"[`']([a-zA-Z0-9_\.]+)['`]\s*->\s*[`']([a-zA-Z0-9_\.]+)['`]", line_clean
        )
        if arrow_match:
            old_sym, new_sym = arrow_match.group(1), arrow_match.group(2)
            changes.append(
                {
                    "symbol": old_sym,
                    "symbol_new": new_sym,
                    "change_type": "renamed",
                    "description": line_clean,
                    "confidence": 0.9,
                }
            )
            continue

        # Detect Removed / Dropped
        if any(k in lower_line for k in ["remove", "dropped", "delete"]):
            syms = [
                m.group(1) or m.group(2)
                for m in symbol_pat.finditer(line_clean)
                if (m.group(1) or m.group(2))
            ]
            for sym in syms:
                if sym.lower() not in {
                    "the",
                    "a",
                    "an",
                    "all",
                    "none",
                    "deprecated",
                    "removed",
                }:
                    changes.append(
                        {
                            "symbol": sym,
                            "symbol_new": None,
                            "change_type": "removed",
                            "description": line_clean,
                            "confidence": 0.85,
                        }
                    )
            if syms:
                continue

        # Detect Deprecated
        if "deprecat" in lower_line:
            syms = [
                m.group(1) or m.group(2)
                for m in symbol_pat.finditer(line_clean)
                if (m.group(1) or m.group(2))
            ]
            for sym in syms:
                if sym.lower() not in {"the", "a", "an", "all", "none", "deprecated"}:
                    changes.append(
                        {
                            "symbol": sym,
                            "symbol_new": None,
                            "change_type": "deprecated",
                            "description": line_clean,
                            "confidence": 0.8,
                        }
                    )
            if syms:
                continue

        # Detect Signature Change or In-Breaking Section Symbol Changes
        if in_breaking_section or any(
            k in lower_line
            for k in ["signature", "parameter", "argument", "now returns"]
        ):
            syms = [
                m.group(1) or m.group(2)
                for m in symbol_pat.finditer(line_clean)
                if (m.group(1) or m.group(2))
            ]
            for sym in syms:
                if sym.lower() not in {
                    "the",
                    "a",
                    "an",
                    "all",
                    "none",
                    "breaking",
                    "change",
                }:
                    changes.append(
                        {
                            "symbol": sym,
                            "symbol_new": sym,
                            "change_type": (
                                "signature_change"
                                if any(
                                    k in lower_line
                                    for k in ["param", "arg", "signature"]
                                )
                                else "behavior_change"
                            ),
                            "description": line_clean,
                            "confidence": 0.8,
                        }
                    )

    # Deduplicate changes by symbol and change_type
    seen = set()
    unique = []
    for c in changes:
        key = (c["symbol"], c["change_type"])
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique


def extract_breaking_changes(
    package_name: str,
    old_version: str,
    new_version: str,
    ecosystem: str = "npm",
    changelog_text: str | None = None,
) -> list[dict[str, Any]]:
    """
    Extract breaking changes for package_name between old_version and new_version.
    """
    raw_changelog = changelog_text or ""

    if not raw_changelog:
        if ecosystem == "npm":
            meta = fetch_npm_metadata(package_name)
            if not meta:
                raise RuntimeError(
                    f"Failed to fetch npm metadata for package '{package_name}'"
                )
            versions = meta.get("versions", {})
            v_meta = versions.get(new_version, {})
            # Look for release notes in description or readme
            raw_changelog = v_meta.get("description", "") or meta.get("readme", "")
        elif ecosystem == "pypi":
            meta = fetch_pypi_metadata(package_name, version=new_version)
            if not meta:
                raise RuntimeError(
                    f"Failed to fetch PyPI metadata for package '{package_name}' at version '{new_version}'"
                )
            info = meta.get("info", {})
            raw_changelog = info.get("description", "")

    if not raw_changelog:
        logger.warning(
            "No changelog or release text available for %s (%s -> %s)",
            package_name,
            old_version,
            new_version,
        )
        raise ValueError(
            f"No changelog or release text available for {package_name} ({old_version} -> {new_version})"
        )

    return parse_changelog_changes(raw_changelog)
