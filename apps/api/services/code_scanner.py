"""
Tree-sitter based code scanner — Section 7.6.

Finds usages of a changed API symbol inside TypeScript, TSX, JavaScript, and Python files.
Resolves import bindings, module aliases, CommonJS requires, and local function definitions to
ensure call sites belong strictly to the target dependency package.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


LANGUAGE_CONFIG = {
    "typescript": {
        "parser_name": "typescript",
        "extensions": {".ts", ".mts", ".cts"},
        "call_node_type": "call_expression",
    },
    "tsx": {
        "parser_name": "tsx",
        "extensions": {".tsx"},
        "call_node_type": "call_expression",
    },
    "javascript": {
        "parser_name": "javascript",
        "extensions": {".js", ".jsx", ".mjs", ".cjs"},
        "call_node_type": "call_expression",
    },
    "python": {
        "parser_name": "python",
        "extensions": {".py"},
        "call_node_type": "call",
    },
}


def _extract_bindings_js_ts(root, source_bytes: bytes, target_pkg: str, target_symbol: str):
    """
    Extract direct function bindings, namespace bindings, foreign bindings,
    and local definitions for JS/TS/TSX.
    """
    direct_bindings = set()
    namespace_bindings = set()
    foreign_bindings = set()
    local_definitions = set()

    for child in root.children:
        # ES Module Imports: import ... from '...'
        if child.type == "import_statement":
            source_node = None
            for c in child.children:
                if c.type == "string":
                    source_node = c
                    break
            if not source_node:
                continue
            mod_name = source_bytes[source_node.start_byte : source_node.end_byte].decode("utf-8").strip("'\"")
            is_target = (mod_name == target_pkg) or mod_name.startswith(f"{target_pkg}/")

            for c in child.children:
                if c.type == "import_clause":
                    for clause_child in c.children:
                        # Default import: import foo from 'bar'
                        if clause_child.type == "identifier":
                            local_name = source_bytes[clause_child.start_byte : clause_child.end_byte].decode("utf-8")
                            if is_target:
                                if mod_name == f"{target_pkg}/{target_symbol}":
                                    direct_bindings.add(local_name)
                                else:
                                    namespace_bindings.add(local_name)
                            else:
                                foreign_bindings.add(local_name)
                        # Namespace import: import * as foo from 'bar'
                        elif clause_child.type == "namespace_import":
                            for ns_c in clause_child.children:
                                if ns_c.type == "identifier":
                                    local_name = source_bytes[ns_c.start_byte : ns_c.end_byte].decode("utf-8")
                                    if is_target:
                                        namespace_bindings.add(local_name)
                                    else:
                                        foreign_bindings.add(local_name)
                        # Named imports: import { a, b as c } from 'bar'
                        elif clause_child.type == "named_imports":
                            for spec in clause_child.children:
                                if spec.type == "import_specifier":
                                    name_node = spec.child_by_field_name("name")
                                    alias_node = spec.child_by_field_name("alias")
                                    orig_name = (
                                        source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                                        if name_node
                                        else None
                                    )
                                    local_name = (
                                        source_bytes[alias_node.start_byte : alias_node.end_byte].decode("utf-8")
                                        if alias_node
                                        else orig_name
                                    )
                                    if is_target:
                                        if orig_name == target_symbol:
                                            direct_bindings.add(local_name)
                                        # Track imported classes/members as potential namespaces/receivers
                                        namespace_bindings.add(local_name)
                                    else:
                                        if orig_name == target_symbol or local_name == target_symbol:
                                            foreign_bindings.add(local_name)
                                        foreign_bindings.add(local_name)

        # CommonJS: const foo = require('bar') or const { foo } = require('bar')
        elif child.type in ("lexical_declaration", "variable_declaration"):
            for decl in child.children:
                if decl.type == "variable_declarator":
                    name_node = decl.child_by_field_name("name")
                    val_node = decl.child_by_field_name("value")
                    if not val_node:
                        continue
                    if val_node.type == "call_expression":
                        fn_node = val_node.child_by_field_name("function")
                        fn_text = (
                            source_bytes[fn_node.start_byte : fn_node.end_byte].decode("utf-8") if fn_node else ""
                        )
                        if fn_text == "require":
                            args_node = val_node.child_by_field_name("arguments")
                            mod_name = ""
                            if args_node:
                                for arg in args_node.children:
                                    if arg.type == "string":
                                        mod_name = source_bytes[arg.start_byte : arg.end_byte].decode("utf-8").strip("'\"")
                                        break
                            is_target = (mod_name == target_pkg) or mod_name.startswith(f"{target_pkg}/")
                            if name_node.type == "identifier":
                                local_name = source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                                if is_target:
                                    if mod_name == f"{target_pkg}/{target_symbol}":
                                        direct_bindings.add(local_name)
                                    else:
                                        namespace_bindings.add(local_name)
                                else:
                                    foreign_bindings.add(local_name)
                            elif name_node.type == "object_pattern":
                                for pat in name_node.children:
                                    if pat.type == "pair_pattern":
                                        k_node = pat.child_by_field_name("key")
                                        v_node = pat.child_by_field_name("value")
                                        k_text = (
                                            source_bytes[k_node.start_byte : k_node.end_byte].decode("utf-8")
                                            if k_node
                                            else ""
                                        )
                                        v_text = (
                                            source_bytes[v_node.start_byte : v_node.end_byte].decode("utf-8")
                                            if v_node
                                            else ""
                                        )
                                        if is_target and k_text == target_symbol:
                                            direct_bindings.add(v_text)
                                        elif not is_target:
                                            foreign_bindings.add(v_text)
                                    elif pat.type in ("shorthand_property_identifier_pattern", "identifier"):
                                        t = source_bytes[pat.start_byte : pat.end_byte].decode("utf-8")
                                        if is_target and t == target_symbol:
                                            direct_bindings.add(t)
                                        elif not is_target:
                                            foreign_bindings.add(t)
                    elif val_node.type == "new_expression":
                        # Track instance assignments: const openai = new OpenAIApi(...)
                        ctor = val_node.child_by_field_name("constructor")
                        ctor_text = (
                            source_bytes[ctor.start_byte : ctor.end_byte].decode("utf-8") if ctor else ""
                        )
                        if any(ns in ctor_text for ns in namespace_bindings):
                            if name_node and name_node.type == "identifier":
                                var_name = source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                                namespace_bindings.add(var_name)

        # Local function declarations: function get(x) { ... }
        elif child.type == "function_declaration":
            fn_name_node = child.child_by_field_name("name")
            if fn_name_node:
                local_definitions.add(
                    source_bytes[fn_name_node.start_byte : fn_name_node.end_byte].decode("utf-8")
                )

    return direct_bindings, namespace_bindings, foreign_bindings, local_definitions


def _extract_bindings_python(root, source_bytes: bytes, target_pkg: str, target_symbol: str):
    """
    Extract direct function bindings, namespace bindings, foreign bindings,
    and local definitions for Python.
    """
    direct_bindings = set()
    namespace_bindings = set()
    foreign_bindings = set()
    local_definitions = set()

    for child in root.children:
        # import foo, import foo as bar
        if child.type == "import_statement":
            for c in child.children:
                if c.type == "dotted_name":
                    mod = source_bytes[c.start_byte : c.end_byte].decode("utf-8")
                    if mod == target_pkg:
                        namespace_bindings.add(mod)
                    else:
                        foreign_bindings.add(mod)
                elif c.type == "aliased_import":
                    name_node = c.child_by_field_name("name")
                    alias_node = c.child_by_field_name("alias")
                    mod = (
                        source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                        if name_node
                        else ""
                    )
                    alias = (
                        source_bytes[alias_node.start_byte : alias_node.end_byte].decode("utf-8")
                        if alias_node
                        else ""
                    )
                    if mod == target_pkg:
                        namespace_bindings.add(alias)
                    else:
                        foreign_bindings.add(alias)

        # from foo import bar, from foo import bar as baz
        elif child.type == "import_from_statement":
            mod_node = child.child_by_field_name("module_name")
            mod = source_bytes[mod_node.start_byte : mod_node.end_byte].decode("utf-8") if mod_node else ""
            is_target = (mod == target_pkg) or mod.startswith(f"{target_pkg}.")
            for c in child.children:
                if c.type == "dotted_name" and c != mod_node:
                    sym = source_bytes[c.start_byte : c.end_byte].decode("utf-8")
                    if is_target:
                        if sym == target_symbol:
                            direct_bindings.add(sym)
                        namespace_bindings.add(sym)
                    else:
                        foreign_bindings.add(sym)
                elif c.type == "aliased_import":
                    name_node = c.child_by_field_name("name")
                    alias_node = c.child_by_field_name("alias")
                    sym = (
                        source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                        if name_node
                        else ""
                    )
                    alias = (
                        source_bytes[alias_node.start_byte : alias_node.end_byte].decode("utf-8")
                        if alias_node
                        else ""
                    )
                    if is_target:
                        if sym == target_symbol:
                            direct_bindings.add(alias)
                        namespace_bindings.add(alias)
                    else:
                        foreign_bindings.add(alias)

        # Local function definitions: def get(x): ...
        elif child.type == "function_definition":
            fn_name_node = child.child_by_field_name("name")
            if fn_name_node:
                local_definitions.add(
                    source_bytes[fn_name_node.start_byte : fn_name_node.end_byte].decode("utf-8")
                )

    return direct_bindings, namespace_bindings, foreign_bindings, local_definitions


def find_usages(
    file_path: str,
    source: bytes,
    symbol_name: str,
    package_name: str | None = None,
) -> list[dict]:
    """
    Scan `source` (raw bytes of a code file) for call sites of `symbol_name`
    using tree-sitter AST parsing and import binding resolution.

    Args:
        file_path: Relative or absolute path to the file.
        source: Raw bytes of the file content.
        symbol_name: Name of the symbol to find (e.g. "get" or "lodash.get").
        package_name: Optional package name (e.g. "lodash", "requests"). If symbol_name
                      contains a dot and package_name is not provided, the package prefix
                      is inferred from symbol_name.

    Returns a list of dicts:
        {
            "file_path": str,
            "line_start": int,   # 1-indexed
            "line_end": int,     # 1-indexed
            "start_byte": int,
            "end_byte": int,
            "snippet": str,
        }
    """
    try:
        import tree_sitter_languages as tsl
    except ImportError:
        logger.error("tree_sitter_languages not installed — run: pip install tree-sitter-languages")
        return []

    # Detect language from extension
    suffix = Path(file_path).suffix.lower()
    selected_config = None
    for config in LANGUAGE_CONFIG.values():
        if suffix in config["extensions"]:
            selected_config = config
            break

    if selected_config is None:
        return []

    lang_name = selected_config["parser_name"]

    try:
        parser = tsl.get_parser(lang_name)
    except Exception as exc:
        logger.error("tree-sitter language setup failed for %s: %s", lang_name, exc)
        return []

    tree = parser.parse(source)
    root = tree.root_node

    # Determine target package and symbol
    if "." in symbol_name and not package_name:
        target_pkg, target_symbol = symbol_name.split(".", 1)
    else:
        target_pkg = package_name
        target_symbol = symbol_name

    # If package is known, extract import bindings and enforce package boundary
    if target_pkg:
        if lang_name in ("typescript", "tsx", "javascript"):
            direct, ns, foreign, local = _extract_bindings_js_ts(root, source, target_pkg, target_symbol)
        elif lang_name == "python":
            direct, ns, foreign, local = _extract_bindings_python(root, source, target_pkg, target_symbol)
        else:
            direct, ns, foreign, local = set(), set(), set(), set()

        # If the target package is never imported in the file, no usages can belong to it
        if not direct and not ns:
            return []
    else:
        direct = {target_symbol}
        ns = set()
        foreign = set()
        local = set()

    usages: list[dict] = []

    def check_call(node):
        is_call = (
            lang_name in ("typescript", "tsx", "javascript") and node.type == "call_expression"
        ) or (lang_name == "python" and node.type == "call")

        if is_call:
            fn_child = node.child_by_field_name("function")
            if fn_child:
                # Direct call: get(...)
                if fn_child.type == "identifier":
                    callee = source[fn_child.start_byte : fn_child.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    if target_pkg:
                        if callee in direct and callee not in foreign and callee not in local:
                            _record_usage(node)
                    else:
                        if callee == target_symbol:
                            _record_usage(node)

                # Member expression / attribute call: lodash.get(...) or req.get(...)
                elif (
                    lang_name in ("typescript", "tsx", "javascript")
                    and fn_child.type == "member_expression"
                ) or (lang_name == "python" and fn_child.type == "attribute"):
                    obj_node = fn_child.child_by_field_name("object")
                    prop_node = fn_child.child_by_field_name(
                        "property" if lang_name != "python" else "attribute"
                    )
                    prop_text = (
                        source[prop_node.start_byte : prop_node.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                        if prop_node
                        else ""
                    )
                    obj_text = (
                        source[obj_node.start_byte : obj_node.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                        if obj_node
                        else ""
                    )

                    if prop_text == target_symbol:
                        if not target_pkg:
                            _record_usage(node)
                        else:
                            base_obj = obj_text.split(".")[0].split("(")[0].strip()
                            if (obj_text in ns or base_obj in ns) and (
                                obj_text not in foreign and base_obj not in foreign
                            ):
                                _record_usage(node)

        for c in node.children:
            check_call(c)

    def _record_usage(call_node):
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

    check_call(root)

    # Deduplicate by unique byte range (start_byte, end_byte)
    seen: set[tuple[int, int]] = set()
    unique: list[dict] = []
    for u in usages:
        key = (u["start_byte"], u["end_byte"])
        if key not in seen:
            seen.add(key)
            unique.append(u)

    return unique
