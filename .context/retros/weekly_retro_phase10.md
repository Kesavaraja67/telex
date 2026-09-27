# Weekly Engineering Retrospective — Sprint End (Phase 10)

**Date**: September 27, 2026  
**Sprint Scope**: Phases -1 through 12 Hardening, Polyglot AST Engine, Security Shielding, and GitHub Issues Triage  
**Team**: Telex Core Systems & Autonomous Agentic Pairing  

---

## 1. What We Shipped (Velocity & Deliverables)

- **Polyglot AST Code Scanner (Phase 12)**:
  - Added support for 9 languages: TypeScript, TSX, JavaScript, Python, Go, Rust, Java, Ruby, C#.
  - Implemented language-specific Tree-sitter import binding resolution:
    - Go: `selector_expression` (`gin.Default()`), import alias handling.
    - Rust: `scoped_identifier` (`serde_json::to_string`), `use_as_clause`.
    - Java: `method_invocation` (`g.toJson()`) with local variable type tracking.
    - Ruby: `call` with `require` and constant resolution.
    - C#: `invocation_expression` with `member_access_expression` (`JsonSerializer.Serialize()`).
- **Complete GitHub Issue Resolution (#29–#41)**:
  - GFI-1 (#32): Default `allow_install_scripts = False` on backend and database.
  - GFI-2 (#33): Interactive toggle switch in web dashboard with optimistic updates.
  - GFI-3 (#34): Visual `[semantic-risk]` badge on PRs and patch cards.
  - GFI-4 (#35): Fail-closed, idempotent label creation (`ensure_repo_labels`).
  - GFI-5 (#36): Risk classification & install script defense documented in README.
  - ISSUE-1 (#37): Real test file call-site detection (`is_test_file`, `detect_symbol_in_tests`).
  - ISSUE-2 (#38): Full end-to-end integration test for dual-change mechanical vs semantic pipeline.
  - ISSUE-3 (#39): API and CLI query parameters for risk filtering and sorting.
  - ISSUE-4 (#40): Human-review digest endpoint `GET /api/repos/digest/human-review`.
  - ISSUE-5 (#41): Verification receipts (Commit SHA / Base SHA) displayed in Web UI and PRs.
- **Test Metrics & Zero-Regression Benchmark**:
  - `apps/api/tests`: **270 passed**, 0 failures.
  - `packages/telex-core/tests`: **24 passed**, 0 failures.
  - Total Test Suite: **294 passed**.
  - Frontend Web: `tsc --noEmit` exited **0 (clean, zero TypeScript errors)**.

---

## 2. What Went Well

1. **Deterministic AST Tree-sitter Resolution**:
   - Rather than relying on unreliable regex or fragile LLM search, the Tree-sitter AST queries consistently locate exact call sites down to the byte offset.
   - Foreign import rejection prevents false positives (e.g. `axios.get` is never confused with `lodash.get`).
2. **Fail-Closed Security Posture**:
   - Webhook HMAC verification, OAuth token storage, BYOK API keys, and lifecycle install script blocking all fail closed safely.
3. **Receipt Traceability**:
   - Verification runs log exact `base_sha` and `commit_sha` hashes, giving human reviewers unshakeable cryptographic proof of test execution.

---

## 3. What Was Painful (Learnings & Gotchas)

1. **Tree-sitter Byte vs String Buffer Trap**:
   - On Windows, `parser.parse(source)` throws `TypeError` if given `str` instead of `bytes`. Fixed universally with defensive encoding guards.
2. **JSX Tree Depth in Complex Dashboards**:
   - Deep nested flex containers and ternaries in Next.js pages can easily incur closing tag mismatches during rapid feature additions. Caught immediately by continuous `tsc --noEmit` checks.
3. **Test-Only Call Site Gating**:
   - Dependencies whose API changes only broke unit tests previously evaded breaking change classification. Implementing `detect_symbol_in_tests` closed this gap completely.

---

## 4. Key Decisions & Non-Negotiable Rules Maintained

- **Strict Non-Negotiable Contract**: Telex will **NEVER** auto-merge a pull request. Every patch requires human signoff.
- **Truth Discovery**: Zero fabricated traction numbers, stars, or ecosystem claims.
- **Isolated Sandbox Execution**: Untrusted third-party code is never executed outside containerized sandboxes with lifecycle script restrictions.

---

## 5. Action Items for Next Sprint

- [ ] Complete crates.io and pkg.go.dev registry polling hooks in `registry_watcher.py`.
- [ ] Implement browser-based visual regression checks for Repo Atlas 3D cartographic canvas.
- [ ] Add automated PR review comment listening for patch revision (`@telex retry`).
