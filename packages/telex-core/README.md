# `telex-core`

**Standalone automated dependency repair engine and AST code scanner.**

`telex-core` is the pure-Python, zero-infrastructure core of Telex. It runs completely locally on your machine or in CI pipelines without requiring a running API server, PostgreSQL database, Redis instance, or GitHub App credentials.

---

## Installation

```bash
cd packages/telex-core
pip install -e .
```

---

## Features

1. **AST Code Scanning**: Locates call sites of breaking API changes across TypeScript, TSX, JavaScript, and Python using Tree-Sitter AST queries and import binding resolution.
2. **Registry Change Analysis**: Fetches release metadata from npm and PyPI and extracts breaking API changes, deprecations, and renames.
3. **Deterministic Patch Application**: Applies unified diffs to source files with strict fail-closed guarantees.
4. **Local Verification Pipeline**: Validates AST parses, typechecks, and runs test suites locally before applying patches.

---

## CLI Usage

### 1. Scan a repository or directory for breaking API usages:
```bash
telex scan ./src --package lodash --symbol get
telex scan ./services --package requests --symbol get --json
```

### 2. Analyze breaking changes between two package versions:
```bash
telex analyze lodash --from 4.17.20 --to 4.17.21 --ecosystem npm
telex analyze requests --from 2.25.0 --to 2.26.0 --ecosystem pypi
telex analyze my-lib --from 1.0.0 --to 2.0.0 --changelog ./CHANGELOG.md
```

### 3. Test or apply a unified diff patch:
```bash
# Dry run test (does not modify file on disk)
telex patch ./src/index.ts --diff ./patch.diff --dry-run

# Apply patch directly
telex patch ./src/index.ts --diff ./patch.diff
```

### 4. Verify local repository integrity:
```bash
telex verify ./src --test-cmd "pytest" --typecheck-cmd "mypy src"
```

---

## License

Apache-2.0
