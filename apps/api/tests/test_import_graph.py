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
        tsconfig = {
            "compilerOptions": {
                "baseUrl": ".",
                "paths": {
                    "@/*": ["src/*"]
                }
            }
        }
        (root / "tsconfig.json").write_text(json.dumps(tsconfig))

        # create directories
        (root / "src").mkdir(parents=True)
        (root / "src" / "components").mkdir(parents=True)
        (root / "assets").mkdir(parents=True)

        # files
        (root / "src" / "utils.ts").write_text("export const add = (a: number, b: number) => a + b;")
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
