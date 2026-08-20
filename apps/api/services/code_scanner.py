"""
Tree-sitter based code scanner — Section 7.6.

Finds usages of a changed API symbol inside a TypeScript/JavaScript file.
Two patterns are supported:
  1. Identifier calls:       createCompletion(...)
  2. Member-expression calls: client.createCompletion(...)
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def find_usages(file_path: str, source: bytes, symbol_name: str) -> list[dict]:
    """
    Scan `source` (raw bytes of a TypeScript/JS file) for call sites of
    `symbol_name` using tree-sitter AST queries.

    Returns a list of dicts:
        {
            "file_path": str,
            "line_start": int,   # 1-indexed
            "line_end": int,     # 1-indexed
            "snippet": str,
        }
    """
    try:
        import tree_sitter_languages as tsl
    except ImportError:
        logger.error(
            "tree_sitter_languages not installed — run: pip install tree-sitter-languages"
        )
        return []

    # Detect language from extension (TypeScript default, fall back to javascript)
    suffix = Path(file_path).suffix.lower()
    lang_name = "typescript" if suffix in (".ts", ".tsx") else "javascript"

    try:
        parser = tsl.get_parser(lang_name)
        language = tsl.get_language(lang_name)
    except Exception as exc:
        logger.error("tree-sitter language setup failed for %s: %s", lang_name, exc)
        return []

    tree = parser.parse(source)

    # Encode the symbol name once for byte-level comparison
    symbol_bytes = symbol_name.encode("utf-8")

    # ── Query 1: plain identifier call — createCompletion(...) ──────────────
    # NOTE: We do NOT interpolate symbol_name into the query string.
    # py-tree-sitter does not evaluate #eq? predicates at capture time;
    # we filter by node.text in Python instead.
    identifier_query_src = """
        (call_expression
          function: (identifier) @fn) @call
    """

    # ── Query 2: member-expression call — obj.createCompletion(...) ─────────
    member_query_src = """
        (call_expression
          function: (member_expression
            property: (property_identifier) @prop)) @call
    """

    usages: list[dict] = []

    for query_src, filter_capture in (
        (identifier_query_src, "fn"),
        (member_query_src, "prop"),
    ):
        try:
            query = language.query(query_src)
            captures = query.captures(tree.root_node)
            # captures() returns list of (node, capture_name) tuples
            # Build a map so we can look up @call nodes alongside @fn/@prop nodes
            capture_map: dict[str, list] = {}
            for node, cap_name in captures:
                capture_map.setdefault(cap_name, []).append(node)

            filter_nodes = capture_map.get(filter_capture, [])
            call_nodes = capture_map.get("call", [])

            # Match: for each @call node, check whether the corresponding filter
            # node text equals symbol_name.  We pair them by position.
            for fn_node, call_node in zip(filter_nodes, call_nodes):
                if fn_node.text == symbol_bytes:
                    usages.append(
                        {
                            "file_path": file_path,
                            "line_start": call_node.start_point[0] + 1,
                            "line_end": call_node.end_point[0] + 1,
                            "snippet": source[call_node.start_byte : call_node.end_byte].decode(
                                "utf-8", errors="replace"
                            ),
                        }
                    )
        except Exception as exc:
            logger.warning("tree-sitter query failed: %s", exc)

    # Deduplicate by (line_start, line_end) — both queries can match the same node
    seen: set[tuple[int, int]] = set()
    unique: list[dict] = []
    for u in usages:
        key = (u["line_start"], u["line_end"])
        if key not in seen:
            seen.add(key)
            unique.append(u)

    return unique
