import json
import tempfile
from pathlib import Path

from services.import_graph import build_import_graph


def test_build_import_graph_fixture():
    """
    Test import_graph extraction against a temporary directory with:
    - a relative import: src/index.ts -> ./utils
    - an alias import: src/index.ts -> @/components/button
    - a dynamic import: src/index.ts -> import(dynModule)
    - a broken relative import: src/index.ts -> ./non_existent
    - a binary asset: assets/logo.png
    - a non-code file: README.md
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # tsconfig.json with path alias
        tsconfig = {"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]}}}
        (root / "tsconfig.json").write_text(json.dumps(tsconfig))

        # create directories
        (root / "src").mkdir(parents=True)
        (root / "src" / "components").mkdir(parents=True)
        (root / "assets").mkdir(parents=True)

        # files
        (root / "src" / "utils.ts").write_text(
            "export const add = (a: number, b: number) => a + b;"
        )
        (root / "src" / "components" / "button.tsx").write_text("export const Button = () => null;")
        (root / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (root / "README.md").write_text("# Test Repo")

        index_code = """
import { add } from './utils';
import { Button } from '@/components/button';
import { missing } from './non_existent';

const dyn = 'something';
import(dyn);
"""
        (root / "src" / "index.ts").write_text(index_code)

        graph = build_import_graph(root)

        # Check nodes
        node_map = {n.id: n for n in graph.nodes}
        assert "src/index.ts" in node_map
        assert "src/utils.ts" in node_map
        assert "src/components/button.tsx" in node_map
        assert "assets/logo.png" in node_map
        assert "README.md" in node_map

        # Binary checks
        assert node_map["assets/logo.png"].is_binary is True
        assert node_map["src/index.ts"].is_binary is False

        # Language checks
        assert node_map["src/index.ts"].language == "typescript"
        assert node_map["src/components/button.tsx"].language == "tsx"
        assert node_map["README.md"].language is None

        # Unresolved imports check on src/index.ts
        # Expect at least 2 unresolved: './non_existent' (broken internal) and dynamic import
        index_node = node_map["src/index.ts"]
        assert index_node.unresolved_import_count >= 2

        # Edges check
        edge_pairs = {(e.source, e.target) for e in graph.edges}
        assert ("src/index.ts", "src/utils.ts") in edge_pairs
        assert ("src/index.ts", "src/components/button.tsx") in edge_pairs
        # non_existent and logo.png should NOT be target edges
        assert ("src/index.ts", "src/non_existent.ts") not in edge_pairs
        assert ("src/index.ts", "assets/logo.png") not in edge_pairs

        # Folders check
        folder_ids = {f.id for f in graph.folders}
        assert "" in folder_ids
        assert "src" in folder_ids
        assert "src/components" in folder_ids
        assert "assets" in folder_ids


def test_build_import_graph_python_and_manifests():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        (root / "pkg").mkdir(parents=True)
        (root / "pkg" / "__init__.py").write_text("")
        (root / "pkg" / "helper.py").write_text("def helper(): pass")
        (root / "pkg" / "main.py").write_text(
            "from .helper import helper\nimport sys\nfrom nonexistent import x"
        )

        # Manifests
        (root / "package.json").write_text(
            json.dumps(
                {
                    "name": "my-app",
                    "dependencies": {"react": "^18.0.0"},
                    "devDependencies": {"typescript": "^5.0.0"},
                }
            )
        )
        (root / "requirements.txt").write_text("fastapi>=0.100.0\nuvicorn\n# comment\n")
        (root / "Cargo.toml").write_text(
            '[package]\nname = "my_crate"\n[dependencies]\nserde = "1.0"\n'
        )
        (root / "go.mod").write_text(
            "module example.com/mod\n\ngo 1.20\n\nrequire github.com/gin-gonic/gin v1.9.0\n"
        )

        graph = build_import_graph(root)
        node_map = {n.id: n for n in graph.nodes}

        assert "pkg/main.py" in node_map
        assert "pkg/helper.py" in node_map
        assert "package.json" in node_map
        assert "requirements.txt" in node_map

        edge_pairs = {(e.source, e.target) for e in graph.edges}
        assert ("pkg/main.py", "pkg/helper.py") in edge_pairs


def test_build_import_graph_rust_go_and_c():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        (root / "src").mkdir(parents=True)
        (root / "src" / "main.rs").write_text("use crate::utils;\n")
        (root / "src" / "utils.rs").write_text("pub fn helper() {}")

        (root / "src" / "main.c").write_text('#include "utils.h"\n')
        (root / "src" / "utils.h").write_text("")

        (root / "main.go").write_text('package main\nimport "./sub"\n')
        (root / "sub").mkdir(parents=True)
        (root / "sub" / "sub.go").write_text("package sub\n")

        graph = build_import_graph(root)
        node_map = {n.id: n for n in graph.nodes}

        assert "src/main.rs" in node_map
        assert "src/utils.rs" in node_map
        assert "src/main.c" in node_map
        assert "src/utils.h" in node_map

        edge_pairs = {(e.source, e.target) for e in graph.edges}
        assert ("src/main.rs", "src/utils.rs") in edge_pairs
        assert ("src/main.c", "src/utils.h") in edge_pairs
