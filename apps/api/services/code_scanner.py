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

    # ── Query 1: plain identifier call — createCompletion(...) ──────────────
    identifier_query_src = f"""
        (call_expression
          function: (identifier) @fn (#eq? @fn "{symbol_name}")) @call
    """

    # ── Query 2: member-expression call — obj.createCompletion(...) ─────────
    member_query_src = f"""
        (call_expression
          function: (member_expression
            property: (property_identifier) @prop (#eq? @prop "{symbol_name}"))) @call
    """

    usages: list[dict] = []

    for query_src in (identifier_query_src, member_query_src):
        try:
            query = language.query(query_src)
            captures = query.captures(tree.root_node)
            for node, capture_name in captures:
                if capture_name == "call":
                    usages.append(
                        {
                            "file_path": file_path,
                            "line_start": node.start_point[0] + 1,
                            "line_end": node.end_point[0] + 1,
                            "snippet": source[node.start_byte : node.end_byte].decode(
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
