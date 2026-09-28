"""
Tree-sitter based code scanner — Section 7.6.

Finds usages of a changed API symbol inside TypeScript, TSX, JavaScript, and Python files.
Resolves import bindings, module aliases, CommonJS requires, and local function definitions to
ensure call sites belong strictly to the target dependency package.
"""

import logging
import re
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
    "go": {
        "parser_name": "go",
        "extensions": {".go"},
        "call_node_type": "call_expression",
    },
    "rust": {
        "parser_name": "rust",
        "extensions": {".rs"},
        "call_node_type": "call_expression",
    },
    "java": {
        "parser_name": "java",
        "extensions": {".java"},
        "call_node_type": "method_invocation",
    },
    "ruby": {
        "parser_name": "ruby",
        "extensions": {".rb"},
        "call_node_type": "call",
    },
    "c_sharp": {
        "parser_name": "c_sharp",
        "extensions": {".cs"},
        "call_node_type": "invocation_expression",
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
            mod_name = (
                source_bytes[source_node.start_byte : source_node.end_byte]
                .decode("utf-8")
                .strip("'\"")
            )
            is_target = (mod_name == target_pkg) or mod_name.startswith(f"{target_pkg}/")

            for c in child.children:
                if c.type == "import_clause":
                    for clause_child in c.children:
                        # Default import: import foo from 'bar'
                        if clause_child.type == "identifier":
                            local_name = source_bytes[
                                clause_child.start_byte : clause_child.end_byte
                            ].decode("utf-8")
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
                                    local_name = source_bytes[
                                        ns_c.start_byte : ns_c.end_byte
                                    ].decode("utf-8")
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
                                        source_bytes[
                                            name_node.start_byte : name_node.end_byte
                                        ].decode("utf-8")
                                        if name_node
                                        else None
                                    )
                                    local_name = (
                                        source_bytes[
                                            alias_node.start_byte : alias_node.end_byte
                                        ].decode("utf-8")
                                        if alias_node
                                        else orig_name
                                    )
                                    if is_target:
                                        if orig_name == target_symbol:
                                            direct_bindings.add(local_name)
                                        else:
                                            # Track imported classes/members as potential namespaces/receivers
                                            namespace_bindings.add(local_name)
                                    else:
                                        if (
                                            orig_name == target_symbol
                                            or local_name == target_symbol
                                        ):
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
                            source_bytes[fn_node.start_byte : fn_node.end_byte].decode("utf-8")
                            if fn_node
                            else ""
                        )
                        if fn_text == "require":
                            args_node = val_node.child_by_field_name("arguments")
                            mod_name = ""
                            if args_node:
                                for arg in args_node.children:
                                    if arg.type == "string":
                                        mod_name = (
                                            source_bytes[arg.start_byte : arg.end_byte]
                                            .decode("utf-8")
                                            .strip("'\"")
                                        )
                                        break
                            is_target = (mod_name == target_pkg) or mod_name.startswith(
                                f"{target_pkg}/"
                            )
                            if name_node.type == "identifier":
                                local_name = source_bytes[
                                    name_node.start_byte : name_node.end_byte
                                ].decode("utf-8")
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
                                            source_bytes[
                                                k_node.start_byte : k_node.end_byte
                                            ].decode("utf-8")
                                            if k_node
                                            else ""
                                        )
                                        v_text = (
                                            source_bytes[
                                                v_node.start_byte : v_node.end_byte
                                            ].decode("utf-8")
                                            if v_node
                                            else ""
                                        )
                                        if is_target and k_text == target_symbol:
                                            direct_bindings.add(v_text)
                                        elif not is_target:
                                            foreign_bindings.add(v_text)
                                    elif pat.type in (
                                        "shorthand_property_identifier_pattern",
                                        "identifier",
                                    ):
                                        t = source_bytes[pat.start_byte : pat.end_byte].decode(
                                            "utf-8"
                                        )
                                        if is_target and t == target_symbol:
                                            direct_bindings.add(t)
                                        elif not is_target:
                                            foreign_bindings.add(t)
                    elif val_node.type == "new_expression":
                        # Track instance assignments: const openai = new OpenAIApi(...)
                        ctor = val_node.child_by_field_name("constructor")
                        ctor_text = (
                            source_bytes[ctor.start_byte : ctor.end_byte].decode("utf-8")
                            if ctor
                            else ""
                        )
                        ctor_base = ctor_text.split(".")[-1].strip()
                        if ctor_text in namespace_bindings or ctor_base in namespace_bindings:
                            if name_node and name_node.type == "identifier":
                                var_name = source_bytes[
                                    name_node.start_byte : name_node.end_byte
                                ].decode("utf-8")
                                namespace_bindings.add(var_name)

        # Local function declarations: function get(x) { ... }
        elif child.type == "function_declaration":
            fn_name_node = child.child_by_field_name("name")
            if fn_name_node:
                fn_name = source_bytes[fn_name_node.start_byte : fn_name_node.end_byte].decode(
                    "utf-8"
                )
                local_definitions.add((fn_name, child.start_byte, child.end_byte))

    return direct_bindings, namespace_bindings, foreign_bindings, local_definitions


def _extract_bindings_python(
    root,
    source_bytes: bytes,
    target_pkg: str,
    target_symbol: str,
    import_names: tuple[str, ...] = (),
):
    """
    Extract direct function bindings, namespace bindings, foreign bindings,
    and local definitions for Python.
    """
    candidates = {target_pkg, *import_names}

    def is_target_module(module):
        return any(module == name or module.startswith(f"{name}.") for name in candidates)

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
                    if is_target_module(mod):
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
                    if is_target_module(mod):
                        namespace_bindings.add(alias)
                    else:
                        foreign_bindings.add(alias)

        # from foo import bar, from foo import bar as baz
        elif child.type == "import_from_statement":
            mod_node = child.child_by_field_name("module_name")
            mod = (
                source_bytes[mod_node.start_byte : mod_node.end_byte].decode("utf-8")
                if mod_node
                else ""
            )
            is_target = is_target_module(mod)
            for c in child.children:
                if c.type == "dotted_name" and c != mod_node:
                    sym = source_bytes[c.start_byte : c.end_byte].decode("utf-8")
                    if is_target:
                        if sym == target_symbol:
                            direct_bindings.add(sym)
                        else:
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
                        else:
                            namespace_bindings.add(alias)
                    else:
                        foreign_bindings.add(alias)

        # Local function definitions: def get(x): ...
        elif child.type == "function_definition":
            fn_name_node = child.child_by_field_name("name")
            if fn_name_node:
                fn_name = source_bytes[fn_name_node.start_byte : fn_name_node.end_byte].decode(
                    "utf-8"
                )
                local_definitions.add((fn_name, child.start_byte, child.end_byte))

    return direct_bindings, namespace_bindings, foreign_bindings, local_definitions


def _extract_bindings_go(root, source_bytes: bytes, target_pkg: str, target_symbol: str):
    """Extract bindings for Go (import specs and local funcs)."""
    direct_bindings = set()
    namespace_bindings = set()
    foreign_bindings = set()
    local_definitions = set()

    for child in root.children:
        if child.type == "import_declaration":

            def process_import_spec(spec_node):
                alias_node = spec_node.child_by_field_name("name")
                path_node = spec_node.child_by_field_name("path") or (
                    spec_node.children[-1] if spec_node.children else None
                )
                if not path_node:
                    return
                path_val = (
                    source_bytes[path_node.start_byte : path_node.end_byte]
                    .decode("utf-8")
                    .strip("\"'")
                )
                base_pkg = path_val.split("/")[-1]
                alias = (
                    source_bytes[alias_node.start_byte : alias_node.end_byte].decode("utf-8")
                    if alias_node
                    else base_pkg
                )
                is_target = (
                    (path_val == target_pkg)
                    or (base_pkg == target_pkg)
                    or path_val.endswith(f"/{target_pkg}")
                )
                if is_target:
                    if alias == ".":
                        direct_bindings.add(target_symbol)
                    else:
                        namespace_bindings.add(alias)
                        namespace_bindings.add(base_pkg)
                else:
                    foreign_bindings.add(alias)

            for c in child.children:
                if c.type == "import_spec":
                    process_import_spec(c)
                elif c.type == "import_spec_list":
                    for sc in c.children:
                        if sc.type == "import_spec":
                            process_import_spec(sc)

        elif child.type == "function_declaration":
            fn_name_node = child.child_by_field_name("name")
            if fn_name_node:
                fn_name = source_bytes[fn_name_node.start_byte : fn_name_node.end_byte].decode(
                    "utf-8"
                )
                local_definitions.add((fn_name, child.start_byte, child.end_byte))

    return direct_bindings, namespace_bindings, foreign_bindings, local_definitions


def _extract_bindings_rust(root, source_bytes: bytes, target_pkg: str, target_symbol: str):
    """Extract bindings for Rust (use declarations and functions)."""
    direct_bindings = set()
    namespace_bindings = set()
    foreign_bindings = set()
    local_definitions = set()

    for child in root.children:
        if child.type == "use_declaration":
            raw_use = (
                source_bytes[child.start_byte : child.end_byte]
                .decode("utf-8")
                .replace("use", "")
                .replace(";", "")
                .strip()
            )
            is_target = target_pkg in raw_use
            if is_target:
                if "::" in raw_use:
                    parts = [p.strip() for p in raw_use.split("::")]
                    last_part = parts[-1]
                    if " as " in last_part:
                        orig, alias = [x.strip() for x in last_part.split(" as ")]
                        if orig == target_symbol:
                            direct_bindings.add(alias)
                    elif last_part == target_symbol:
                        direct_bindings.add(last_part)
                    namespace_bindings.add(parts[0])
                elif " as " in raw_use:
                    orig, alias = [x.strip() for x in raw_use.split(" as ")]
                    if orig == target_pkg:
                        namespace_bindings.add(alias)
                else:
                    namespace_bindings.add(raw_use)
            else:
                if "::" in raw_use:
                    foreign_bindings.add(raw_use.split("::")[0].strip())
                else:
                    foreign_bindings.add(raw_use)

        elif child.type == "function_item":
            fn_name_node = child.child_by_field_name("name")
            if fn_name_node:
                fn_name = source_bytes[fn_name_node.start_byte : fn_name_node.end_byte].decode(
                    "utf-8"
                )
                local_definitions.add((fn_name, child.start_byte, child.end_byte))

    return direct_bindings, namespace_bindings, foreign_bindings, local_definitions


def _extract_bindings_java(root, source_bytes: bytes, target_pkg: str, target_symbol: str):
    """Extract bindings for Java (import declarations and methods)."""
    direct_bindings = set()
    namespace_bindings = set()
    foreign_bindings = set()
    local_definitions = set()

    for child in root.children:
        if child.type == "import_declaration":
            raw_import = (
                source_bytes[child.start_byte : child.end_byte]
                .decode("utf-8")
                .replace("import", "")
                .replace("static", "")
                .replace(";", "")
                .strip()
            )
            is_target = target_pkg.lower() in raw_import.lower()
            last_part = raw_import.split(".")[-1]
            if is_target:
                if last_part == target_symbol:
                    direct_bindings.add(last_part)
                namespace_bindings.add(last_part)
                for segment in raw_import.split("."):
                    namespace_bindings.add(segment)
            else:
                foreign_bindings.add(last_part)

    def walk_java_vars(node):
        if node.type in ("local_variable_declaration", "field_declaration"):
            t_node = node.child_by_field_name("type")
            t_text = (
                source_bytes[t_node.start_byte : t_node.end_byte].decode("utf-8") if t_node else ""
            )
            if any(ns.lower() == t_text.lower() for ns in namespace_bindings):
                for c in node.children:
                    if c.type == "variable_declarator":
                        v_name = c.child_by_field_name("name")
                        if v_name:
                            namespace_bindings.add(
                                source_bytes[v_name.start_byte : v_name.end_byte].decode("utf-8")
                            )
        elif node.type == "method_declaration":
            m_name = node.child_by_field_name("name")
            if m_name:
                fn_name = source_bytes[m_name.start_byte : m_name.end_byte].decode("utf-8")
                local_definitions.add((fn_name, node.start_byte, node.end_byte))

        for c in node.children:
            walk_java_vars(c)

    walk_java_vars(root)
    return direct_bindings, namespace_bindings, foreign_bindings, local_definitions


def _extract_bindings_ruby(root, source_bytes: bytes, target_pkg: str, target_symbol: str):
    """Extract bindings for Ruby (require calls and methods)."""
    direct_bindings = set()
    namespace_bindings = set()
    foreign_bindings = set()
    local_definitions = set()

    for child in root.children:
        if child.type == "call":
            raw_text = source_bytes[child.start_byte : child.end_byte].decode("utf-8")
            if "require" in raw_text:
                if target_pkg.lower() in raw_text.lower():
                    namespace_bindings.add(target_pkg)
                    namespace_bindings.add(target_pkg.capitalize())
                    namespace_bindings.add(target_pkg.upper())

        elif child.type in ("method", "singleton_method"):
            m_name = child.child_by_field_name("name")
            if m_name:
                fn_name = source_bytes[m_name.start_byte : m_name.end_byte].decode("utf-8")
                local_definitions.add((fn_name, child.start_byte, child.end_byte))

    return direct_bindings, namespace_bindings, foreign_bindings, local_definitions


def _extract_bindings_csharp(root, source_bytes: bytes, target_pkg: str, target_symbol: str):
    """Extract bindings for C# (using directives and methods)."""
    direct_bindings = set()
    namespace_bindings = set()
    foreign_bindings = set()
    local_definitions = set()

    for child in root.children:
        if child.type == "using_directive":
            raw_using = (
                source_bytes[child.start_byte : child.end_byte]
                .decode("utf-8")
                .replace("using", "")
                .replace("static", "")
                .replace(";", "")
                .strip()
            )
            is_target = target_pkg.lower() in raw_using.lower()
            last_part = raw_using.split(".")[-1]
            if is_target:
                if last_part == target_symbol:
                    direct_bindings.add(last_part)
                namespace_bindings.add(last_part)
                namespace_bindings.add(target_pkg)
                for segment in raw_using.split("."):
                    namespace_bindings.add(segment)
            else:
                foreign_bindings.add(last_part)

    return direct_bindings, namespace_bindings, foreign_bindings, local_definitions


def find_usages(
    file_path: str,
    source: bytes | str,
    symbol_name: str,
    package_name: str | None = None,
    import_names: tuple[str, ...] = (),
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

        import_names: Known Python import names for the target distribution.

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

    if isinstance(source, str):
        source = source.encode("utf-8")

    tree = parser.parse(source)
    root = tree.root_node

    # Determine target package and symbol
    if "." in symbol_name and not package_name:
        target_pkg, target_symbol = symbol_name.split(".", 1)
    else:
        target_pkg = package_name
        if package_name and symbol_name.startswith(f"{package_name}."):
            target_symbol = symbol_name[len(package_name) + 1 :]
        else:
            target_symbol = symbol_name

    # Qualified Python symbols can use an import name that differs from the distribution.
    if target_pkg and lang_name == "python":
        for name in sorted(import_names, key=len, reverse=True):
            if symbol_name.startswith(f"{name}."):
                target_symbol = symbol_name[len(name) + 1 :]
                break

    # If package is known, extract import bindings and enforce package boundary
    if target_pkg:
        if lang_name in ("typescript", "tsx", "javascript"):
            direct, ns, foreign, local = _extract_bindings_js_ts(
                root, source, target_pkg, target_symbol
            )
        elif lang_name == "python":
            direct, ns, foreign, local = _extract_bindings_python(
                root, source, target_pkg, target_symbol, import_names
            )
        elif lang_name == "go":
            direct, ns, foreign, local = _extract_bindings_go(
                root, source, target_pkg, target_symbol
            )
        elif lang_name == "rust":
            direct, ns, foreign, local = _extract_bindings_rust(
                root, source, target_pkg, target_symbol
            )
        elif lang_name == "java":
            direct, ns, foreign, local = _extract_bindings_java(
                root, source, target_pkg, target_symbol
            )
        elif lang_name == "ruby":
            direct, ns, foreign, local = _extract_bindings_ruby(
                root, source, target_pkg, target_symbol
            )
        elif lang_name == "c_sharp":
            direct, ns, foreign, local = _extract_bindings_csharp(
                root, source, target_pkg, target_symbol
            )
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

    def _is_locally_shadowed(fn_name: str, call_node) -> bool:
        for item in local:
            if isinstance(item, tuple) and len(item) == 3:
                name, s_byte, e_byte = item
                if name == fn_name and s_byte <= call_node.start_byte <= e_byte:
                    return True
            elif isinstance(item, str) and item == fn_name:
                return True
        return False

    def check_call(node):
        call_type = selected_config.get("call_node_type", "call_expression")
        if node.type == call_type:
            fn_text = ""
            receiver_text = ""
            prop_text = ""

            if lang_name in ("typescript", "tsx", "javascript"):
                fn_child = node.child_by_field_name("function")
                if fn_child:
                    if fn_child.type == "identifier":
                        fn_text = source[fn_child.start_byte : fn_child.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                    elif fn_child.type == "member_expression":
                        p = fn_child.child_by_field_name("property")
                        o = fn_child.child_by_field_name("object")
                        prop_text = (
                            source[p.start_byte : p.end_byte].decode("utf-8", errors="replace")
                            if p
                            else ""
                        )
                        receiver_text = (
                            source[o.start_byte : o.end_byte].decode("utf-8", errors="replace")
                            if o
                            else ""
                        )
            elif lang_name == "python":
                fn_child = node.child_by_field_name("function")
                if fn_child:
                    if fn_child.type == "identifier":
                        fn_text = source[fn_child.start_byte : fn_child.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                    elif fn_child.type == "attribute":
                        p = fn_child.child_by_field_name("attribute")
                        o = fn_child.child_by_field_name("object")
                        prop_text = (
                            source[p.start_byte : p.end_byte].decode("utf-8", errors="replace")
                            if p
                            else ""
                        )
                        receiver_text = (
                            source[o.start_byte : o.end_byte].decode("utf-8", errors="replace")
                            if o
                            else ""
                        )
            elif lang_name == "go":
                fn_child = node.child_by_field_name("function")
                if fn_child:
                    if fn_child.type == "identifier":
                        fn_text = source[fn_child.start_byte : fn_child.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                    elif fn_child.type == "selector_expression":
                        o = fn_child.child_by_field_name("operand")
                        p = fn_child.child_by_field_name("field")
                        receiver_text = (
                            source[o.start_byte : o.end_byte].decode("utf-8", errors="replace")
                            if o
                            else ""
                        )
                        prop_text = (
                            source[p.start_byte : p.end_byte].decode("utf-8", errors="replace")
                            if p
                            else ""
                        )
            elif lang_name == "rust":
                fn_child = node.child_by_field_name("function")
                if fn_child:
                    if fn_child.type == "identifier":
                        fn_text = source[fn_child.start_byte : fn_child.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                    elif fn_child.type == "scoped_identifier":
                        path_node = fn_child.child_by_field_name("path")
                        name_node = fn_child.child_by_field_name("name")
                        receiver_text = (
                            source[path_node.start_byte : path_node.end_byte].decode(
                                "utf-8", errors="replace"
                            )
                            if path_node
                            else ""
                        )
                        prop_text = (
                            source[name_node.start_byte : name_node.end_byte].decode(
                                "utf-8", errors="replace"
                            )
                            if name_node
                            else ""
                        )
                    elif fn_child.type == "field_expression":
                        o = fn_child.child_by_field_name("value")
                        p = fn_child.child_by_field_name("field")
                        receiver_text = (
                            source[o.start_byte : o.end_byte].decode("utf-8", errors="replace")
                            if o
                            else ""
                        )
                        prop_text = (
                            source[p.start_byte : p.end_byte].decode("utf-8", errors="replace")
                            if p
                            else ""
                        )
            elif lang_name == "java":
                name_node = node.child_by_field_name("name")
                obj_node = node.child_by_field_name("object")
                prop_text = (
                    source[name_node.start_byte : name_node.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    if name_node
                    else ""
                )
                receiver_text = (
                    source[obj_node.start_byte : obj_node.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    if obj_node
                    else ""
                )
                if not receiver_text:
                    fn_text = prop_text
            elif lang_name == "ruby":
                m_node = node.child_by_field_name("method")
                r_node = node.child_by_field_name("receiver")
                prop_text = (
                    source[m_node.start_byte : m_node.end_byte].decode("utf-8", errors="replace")
                    if m_node
                    else ""
                )
                receiver_text = (
                    source[r_node.start_byte : r_node.end_byte].decode("utf-8", errors="replace")
                    if r_node
                    else ""
                )
                if not prop_text and not receiver_text:
                    c0 = node.children[0] if node.children else None
                    if c0 and c0.type == "identifier":
                        fn_text = source[c0.start_byte : c0.end_byte].decode(
                            "utf-8", errors="replace"
                        )
            elif lang_name == "c_sharp":
                expr_node = node.child_by_field_name("expression") or (
                    node.children[0] if node.children else None
                )
                if expr_node:
                    if expr_node.type == "identifier":
                        fn_text = source[expr_node.start_byte : expr_node.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                    elif (
                        expr_node.type == "member_access_expression"
                        and len(expr_node.children) >= 3
                    ):
                        receiver_text = source[
                            expr_node.children[0].start_byte : expr_node.children[0].end_byte
                        ].decode("utf-8", errors="replace")
                        prop_text = source[
                            expr_node.children[2].start_byte : expr_node.children[2].end_byte
                        ].decode("utf-8", errors="replace")

            # Check matches against bindings or target_symbol
            if fn_text:
                if target_pkg:
                    if (
                        fn_text in direct
                        and fn_text not in foreign
                        and not _is_locally_shadowed(fn_text, node)
                    ):
                        _record_usage(node)
                else:
                    if fn_text == target_symbol:
                        _record_usage(node)
            elif prop_text == target_symbol:
                if not target_pkg:
                    _record_usage(node)
                else:
                    base_obj = receiver_text.split(".")[0].split("(")[0].strip()
                    matches_ns = receiver_text in ns or base_obj in ns
                    if not matches_ns and lang_name == "c_sharp" and bool(ns):
                        if receiver_text and receiver_text[0].isupper():
                            matches_ns = True
                    if matches_ns and (receiver_text not in foreign and base_obj not in foreign):
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


def is_test_file(file_path: str) -> bool:
    """Return True if the file path matches standard test file patterns across languages."""
    raw_path = file_path.replace("\\", "/")
    parts = raw_path.split("/")
    raw_filename = parts[-1]
    filename_lower = raw_filename.lower()
    dirs_lower = [p.lower() for p in parts[:-1]]

    if any(part in ("tests", "test", "__tests__", "spec", "specs") for part in dirs_lower):
        return True
    if (
        filename_lower.startswith("test_")
        or filename_lower.endswith("_test.py")
        or filename_lower.endswith("_test.go")
    ):
        return True
    if (
        filename_lower.endswith(".test.ts")
        or filename_lower.endswith(".test.tsx")
        or filename_lower.endswith(".test.js")
        or filename_lower.endswith(".test.jsx")
    ):
        return True
    if (
        filename_lower.endswith(".spec.ts")
        or filename_lower.endswith(".spec.tsx")
        or filename_lower.endswith(".spec.js")
        or filename_lower.endswith(".spec.jsx")
    ):
        return True
    if filename_lower.endswith("_spec.rb") or filename_lower.endswith("_test.rb"):
        return True
    # Java and C#: inspect original-case basename and recognize Test or Tests only at a word boundary
    # so names like Latest.java and Contest.cs remain production files.
    if re.search(r"(?:^|[._-][Tt]est|[a-z0-9]Test)s?\.(?:java|cs)$", raw_filename):
        return True
    return False


def detect_symbol_in_tests(
    repo_files: dict[str, str],
    symbol_name: str,
    package_name: str | None = None,
) -> bool:
    """
    Scans test files in repo_files (dict of file_path -> source_content)
    to check whether symbol_name from package_name is referenced/called.
    Returns True if at least one test file has a usage.
    """
    for file_path, content in repo_files.items():
        if is_test_file(file_path):
            content_bytes = content.encode("utf-8") if isinstance(content, str) else content
            usages = find_usages(file_path, content_bytes, symbol_name, package_name)
            if usages:
                return True
    return False
