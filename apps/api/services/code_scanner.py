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

    # Detect language from extension
    suffix = Path(file_path).suffix.lower()
    if suffix == ".tsx":
        lang_name = "tsx"
    elif suffix in (".ts", ".mts", ".cts"):
        lang_name = "typescript"
    else:
        lang_name = "javascript"

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
    # Filter by node.text in Python, then traverse to enclosing call_expression.
    identifier_query_src = """
        (call_expression
          function: (identifier) @fn)
    """

    # ── Query 2: member-expression call — obj.createCompletion(...) ─────────
    member_query_src = """
        (call_expression
          function: (member_expression
            property: (property_identifier) @prop))
    """

    usages: list[dict] = []

    for query_src, filter_capture in (
        (identifier_query_src, "fn"),
        (member_query_src, "prop"),
    ):
        try:
            query = language.query(query_src)
            captures = query.captures(tree.root_node)
            for node, cap_name in captures:
                if cap_name == filter_capture and node.text == symbol_bytes:
                    # Traverse upward to find enclosing call_expression
                    curr = node.parent
                    while curr is not None and curr.type != "call_expression":
                        curr = curr.parent
                    call_node = curr if curr is not None else node

                    usages.append(
                        {
                            "file_path": file_path,
                            "line_start": call_node.start_point[0] + 1,
                            "line_end": call_node.end_point[0] + 1,
                            "start_byte": call_node.start_byte,
                            "end_byte": call_node.end_byte,
                            "snippet": source[call_node.start_byte : call_node.end_byte].decode(
                                "utf-8", errors="replace"
                            ),
                        }
                    )
        except Exception as exc:
            logger.warning("tree-sitter query failed: %s", exc)

    # Deduplicate by unique byte range (start_byte, end_byte)
    seen: set[tuple[int, int]] = set()
    unique: list[dict] = []
    for u in usages:
        key = (u["start_byte"], u["end_byte"])
        if key not in seen:
            seen.add(key)
            unique.append(u)

    return unique
