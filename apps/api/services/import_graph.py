"""
Import graph extraction for Atlas.

Produces a plain-data graph:
    nodes: list[AtlasNode]   — one per file in the repo (after exclusions)
    edges: list[AtlasEdge]   — resolved import relationships between nodes
    unresolved: list[UnresolvedImport]  — honest record of what couldn't be
                                           statically resolved (Section 1.14)

Reuses the tree-sitter language config from code_scanner.py's LANGUAGE_CONFIG
map but adds IMPORT queries (code_scanner.py's queries find call-sites of one
already-known symbol; Atlas needs every import statement in every file).
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Exclusions (Section 1.12 — non-code files still get nodes, but build
#    tooling / dependency directories never do; these aren't "files in the
#    user's repo", they're generated or vendored) ──────────────────────────
EXCLUDED_DIR_NAMES = {
    "node_modules",
    ".git",
    ".next",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    ".turbo",
    ".vercel",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    "target",
    ".terraform",
}
MAX_NODES = 6000  # hard safety ceiling well above the 2,000-file design target

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".bmp",
    ".mp4",
    ".mov",
    ".webm",
    ".avi",
    ".mp3",
    ".wav",
    ".ogg",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".pyc",
    ".so",
    ".dylib",
    ".dll",
    ".wasm",
    ".db",
    ".sqlite",
}

LANGUAGE_BY_EXT = {
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".py": "python",
}

# tree-sitter queries for import-style statements, per language.
# Each entry: (query_source, capture_name_for_the_specifier_string_node)
IMPORT_QUERIES: dict[str, list[tuple[str, str]]] = {
    "typescript": [
        ('(import_statement source: (string) @spec)', "spec"),
        ('(export_statement source: (string) @spec)', "spec"),
        (
            '(call_expression function: (identifier) @fn arguments: (arguments (string) @spec) (#eq? @fn "require"))',
            "spec",
        ),
        (
            '(call_expression function: (import) arguments: (arguments) @spec_dynamic)',
            "spec_dynamic",
        ),
    ],
    "tsx": [
        ('(import_statement source: (string) @spec)', "spec"),
        ('(export_statement source: (string) @spec)', "spec"),
        (
            '(call_expression function: (identifier) @fn arguments: (arguments (string) @spec) (#eq? @fn "require"))',
            "spec",
        ),
        (
            '(call_expression function: (import) arguments: (arguments) @spec_dynamic)',
            "spec_dynamic",
        ),
    ],
    "javascript": [
        ('(import_statement source: (string) @spec)', "spec"),
        ('(export_statement source: (string) @spec)', "spec"),
        (
            '(call_expression function: (identifier) @fn arguments: (arguments (string) @spec) (#eq? @fn "require"))',
            "spec",
        ),
        (
            '(call_expression function: (import) arguments: (arguments) @spec_dynamic)',
            "spec_dynamic",
        ),
    ],
    "python": [
        ('(import_from_statement module_name: (dotted_name) @spec)', "spec"),
        ('(import_from_statement module_name: (relative_import) @spec)', "spec"),
        ('(import_statement name: (dotted_name) @spec)', "spec"),
    ],
}


@dataclass
class AtlasNode:
    id: str  # repo-relative posix path, e.g. "apps/web/lib/api.ts"
    name: str  # filename only
    dir: str  # parent dir, repo-relative posix path ("" for root)
    depth: int  # folder depth from repo root (root files = 0)
    ext: str
    language: str | None  # None for non-code files
    is_binary: bool
    size_bytes: int
    unresolved_import_count: int = 0
    unresolved_specifiers: list[str] = field(default_factory=list)


@dataclass
class AtlasEdge:
    source: str  # AtlasNode.id
    target: str  # AtlasNode.id
    kind: str  # "import" — the only edge kind this module produces


@dataclass
class AtlasFolder:
    id: str  # repo-relative posix path, "" = root
    name: str
    parent: str | None  # parent folder id, None for root
    depth: int


@dataclass
class AtlasGraph:
    nodes: list[AtlasNode]
    edges: list[AtlasEdge]
    folders: list[AtlasFolder]
    truncated: bool  # True if MAX_NODES was hit — surfaced honestly in the UI


def build_import_graph(repo_root: Path) -> AtlasGraph:
    import tree_sitter_languages as tsl

    files = _walk_files(repo_root)
    if len(files) > MAX_NODES:
        logger.warning(
            "Repo has %d files, truncating to %d for Atlas", len(files), MAX_NODES
        )
        files = files[:MAX_NODES]
        truncated = True
    else:
        truncated = False

    nodes: dict[str, AtlasNode] = {}
    folders: dict[str, AtlasFolder] = {
        "": AtlasFolder(id="", name="/", parent=None, depth=0)
    }

    for abs_path in files:
        rel = abs_path.relative_to(repo_root).as_posix()
        _ensure_folder_chain(rel, folders)
        ext = abs_path.suffix.lower()
        lang = LANGUAGE_BY_EXT.get(ext)
        is_binary = ext in BINARY_EXTENSIONS
        try:
            size = abs_path.stat().st_size
        except OSError:
            size = 0
        nodes[rel] = AtlasNode(
            id=rel,
            name=abs_path.name,
            dir=os.path.dirname(rel),
            depth=rel.count("/"),
            ext=ext,
            language=lang,
            is_binary=is_binary,
            size_bytes=size,
        )

    # Load path-alias configs (tsconfig "paths") once per project root, cached.
    alias_cache: dict[str, dict] = {}

    edges: list[AtlasEdge] = []
    for rel, node in list(nodes.items()):
        if node.language is None or node.is_binary:
            continue
        abs_path = repo_root / rel
        try:
            source = abs_path.read_bytes()
        except OSError:
            continue
        if len(source) > 2 * 1024 * 1024:
            continue  # oversized generated file — list it, don't parse it

        try:
            parser = tsl.get_parser(node.language)
            language = tsl.get_language(node.language)
        except Exception as exc:
            logger.warning("tree-sitter unavailable for %s: %s", node.language, exc)
            continue

        tree = parser.parse(source)
        specifiers = _extract_specifiers(language, tree, node.language)

        for spec_text, is_dynamic_uncertain in specifiers:
            if is_dynamic_uncertain:
                node.unresolved_import_count += 1
                node.unresolved_specifiers.append(spec_text)
                continue

            resolved = _resolve_specifier(
                spec_text,
                rel,
                repo_root,
                node.language,
                nodes,
                alias_cache,
            )
            if resolved is None:
                if _looks_internal(spec_text, node.language):
                    node.unresolved_import_count += 1
                    node.unresolved_specifiers.append(spec_text)
                # else: resolves to an external package — deliberately not
                # rendered at all (Section 1.12 / product decision: only
                # real files in this repo become nodes and edges).
                continue

            edges.append(AtlasEdge(source=rel, target=resolved, kind="import"))

    # de-dup edges (same source→target can appear from multiple import lines)
    seen = set()
    unique_edges = []
    for e in edges:
        key = (e.source, e.target)
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    return AtlasGraph(
        nodes=list(nodes.values()),
        edges=unique_edges,
        folders=list(folders.values()),
        truncated=truncated,
    )


def _walk_files(repo_root: Path) -> list[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in EXCLUDED_DIR_NAMES and not d.startswith(".git")
        ]
        for fn in filenames:
            out.append(Path(dirpath) / fn)
    return out


def _ensure_folder_chain(rel_file_path: str, folders: dict[str, AtlasFolder]) -> None:
    parts = rel_file_path.split("/")[:-1]
    built = ""
    parent = ""
    for part in parts:
        built = f"{built}/{part}" if built else part
        if built not in folders:
            folders[built] = AtlasFolder(
                id=built,
                name=part,
                parent=parent,
                depth=built.count("/"),
            )
        parent = built


def _extract_specifiers(language, tree, lang_name: str) -> list[tuple[str, bool]]:
    """Returns list of (specifier_text, is_dynamic_uncertain)."""
    results = []
    for query_src, _capture in IMPORT_QUERIES.get(lang_name, []):
        try:
            query = language.query(query_src)
            captures = query.captures(tree.root_node)
        except Exception:
            continue
        for node, cap_name in captures:
            if cap_name == "spec_dynamic":
                arg_nodes = [child for child in node.children if child.type not in ("(", ")", ",")]
                first_arg = arg_nodes[0] if arg_nodes else None
                if first_arg is not None and first_arg.type == "string":
                    text = first_arg.text.decode("utf-8", errors="replace").strip("'\"")
                    results.append((text, False))
                else:
                    text = node.text.decode("utf-8", errors="replace").strip("()")
                    results.append((text, True))
            else:
                text = node.text.decode("utf-8", errors="replace").strip("'\"")
                results.append((text, False))
    return results


def _looks_internal(spec: str, lang: str) -> bool:
    if lang == "python":
        return spec.startswith(".")
    return spec.startswith(".") or spec.startswith("@/") or spec.startswith("~/")


def _resolve_specifier(
    spec: str,
    from_file_rel: str,
    repo_root: Path,
    lang: str,
    nodes: dict[str, AtlasNode],
    alias_cache: dict[str, dict],
) -> str | None:
    if lang == "python":
        return _resolve_python_specifier(spec, from_file_rel, repo_root, nodes)
    return _resolve_js_specifier(spec, from_file_rel, repo_root, nodes, alias_cache)


JS_TRY_EXTS = [
    "",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    "/index.ts",
    "/index.tsx",
    "/index.js",
    "/index.jsx",
]


def _resolve_js_specifier(
    spec: str,
    from_file_rel: str,
    repo_root: Path,
    nodes: dict[str, AtlasNode],
    alias_cache: dict[str, dict],
) -> str | None:
    from_dir = Path(from_file_rel).parent

    if spec.startswith("."):
        candidate_base = (from_dir / spec).as_posix()
        return _try_extensions(candidate_base, nodes)

    for alias_prefix, target_prefix in _load_aliases(
        from_file_rel, repo_root, alias_cache
    ).items():
        if spec == alias_prefix or spec.startswith(alias_prefix + "/"):
            remainder = spec[len(alias_prefix) :].lstrip("/")
            candidate_base = f"{target_prefix}/{remainder}".strip("/")
            resolved = _try_extensions(candidate_base, nodes)
            if resolved:
                return resolved

    return None  # bare specifier — external package, not resolved (by design)


def _try_extensions(candidate_base: str, nodes: dict[str, AtlasNode]) -> str | None:
    norm = os.path.normpath(candidate_base).replace("\\", "/")
    for suffix in JS_TRY_EXTS:
        key = f"{norm}{suffix}" if suffix else norm
        key = key.lstrip("/")
        if key in nodes:
            return key
    return None


def _load_aliases(from_file_rel: str, repo_root: Path, cache: dict) -> dict[str, str]:
    """
    Walk upward from the importing file to the nearest tsconfig.json with a
    "paths" map, parse it, cache by that tsconfig's directory. Returns a
    dict of {alias_prefix_without_wildcard: resolved_prefix_repo_relative}.
    E.g. tsconfig `"@/*": ["./*"]` in apps/web/tsconfig.json becomes
    {"@": "apps/web"}.
    """
    current = (repo_root / from_file_rel).parent
    while True:
        tsconfig_path = current / "tsconfig.json"
        cache_key = tsconfig_path.as_posix()
        if cache_key in cache:
            return cache[cache_key]
        if tsconfig_path.exists():
            try:
                raw = tsconfig_path.read_text(encoding="utf-8")
                # tsconfig.json commonly has comments; strip // line comments only
                cleaned = "\n".join(
                    line
                    for line in raw.splitlines()
                    if not line.strip().startswith("//")
                )
                data = json.loads(cleaned)
                paths = data.get("compilerOptions", {}).get("paths", {})
                base_url = data.get("compilerOptions", {}).get("baseUrl", ".")
                project_root_rel = current.relative_to(repo_root).as_posix()
                result = {}
                for alias_pattern, targets in paths.items():
                    if not targets:
                        continue
                    alias_prefix = alias_pattern.rstrip("/*")
                    target_pattern = targets[0].rstrip("/*")
                    target_prefix = os.path.normpath(
                        os.path.join(project_root_rel, base_url, target_pattern)
                    ).replace("\\", "/").strip("/")
                    if target_prefix == ".":
                        target_prefix = project_root_rel
                    result[alias_prefix] = target_prefix
                cache[cache_key] = result
                return result
            except Exception as exc:
                logger.debug("Failed to parse %s: %s", tsconfig_path, exc)
                cache[cache_key] = {}
                return {}
        if current == repo_root or current.parent == current:
            cache[cache_key] = {}
            return {}
        current = current.parent


def _resolve_python_specifier(
    spec: str, from_file_rel: str, repo_root: Path, nodes: dict[str, AtlasNode]
) -> str | None:
    from_dir = Path(from_file_rel).parent
    if spec.startswith("."):
        dots = len(spec) - len(spec.lstrip("."))
        remainder = spec[dots:]
        base_dir = from_dir
        for _ in range(dots - 1):
            base_dir = base_dir.parent
        module_path = remainder.replace(".", "/") if remainder else ""
        candidate = (
            (base_dir / module_path).as_posix().strip("/")
            if module_path
            else base_dir.as_posix()
        )
        for suffix in ["", ".py", "/__init__.py"]:
            key = f"{candidate}{suffix}".lstrip("/")
            if key in nodes:
                return key
        return None
    # Absolute dotted import — only resolve if it maps onto a real repo path
    # (covers first-party absolute imports in a src-layout project); anything
    # that isn't a real file in the repo is external stdlib/3rd-party, skip.
    candidate = spec.replace(".", "/")
    for suffix in ["", ".py", "/__init__.py"]:
        key = f"{candidate}{suffix}"
        if key in nodes:
            return key
    return None
