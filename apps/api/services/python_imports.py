"""Distribution-to-import candidates for Python dependency scans."""

import re
from importlib.metadata import packages_distributions

# These aliases also work when the scanned dependency isn't installed in the worker.
_KNOWN_IMPORT_NAMES = {
    "beautifulsoup4": ("bs4",),
    "opencv-python": ("cv2",),
    "pillow": ("PIL",),
    "python-dateutil": ("dateutil",),
    "pyyaml": ("yaml",),
    "scikit-learn": ("sklearn",),
}


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def resolve_import_names(distribution_name: str) -> tuple[str, ...]:
    """Combine normalization, known aliases, and installed package metadata.

    Unknown, uninstalled distributions retain the normalized-name fallback.
    Import names keep their case because Python imports are case sensitive.
    """
    normalized = _normalize(distribution_name)
    candidates = {
        normalized.replace("-", "_"),
        *_KNOWN_IMPORT_NAMES.get(normalized, ()),
    }
    for import_name, distributions in packages_distributions().items():
        if any(_normalize(name) == normalized for name in distributions):
            candidates.add(import_name)
    return tuple(sorted(candidates))
