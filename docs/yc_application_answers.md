# Y Combinator Application — Grounded Evidence & Code Truth (Phase 11)

**Company**: Telex  
**Founders**: Telex Engineering Team  
**Verification Date**: September 27, 2026  
**Core Technical Contract**: Autonomous AST-guided dependency migration with isolated sandbox verification. Never auto-merge.

---

### 1. What is your company going to make? What does your product do?
Telex is the autonomous maintenance engine for software dependencies. When an open-source library or upstream package (npm, PyPI, Go, Rust, Java, etc.) publishes a breaking version, Telex automatically:
1. Detects breaking API changes from changelogs, release notes, and AST diffs.
2. Scans user repositories using Tree-sitter AST queries with strict import binding resolution to discover exact call sites.
3. Synthesizes minimal unified diff patches that rewrite call sites to the new API.
4. Executes the repository's test and typecheck suite inside an isolated sandbox.
5. Opens a production-ready Pull Request containing the cryptographic verification receipt (base SHA and commit SHA) and risk classification.
6. Hands the PR to the human engineering team for final review. **Telex never auto-merges.**

---

### 2. Why did you choose this idea? What is your domain expertise?
Upstream dependency upgrades are responsible for billions of dollars in developer toil each year. Dependabot and Renovate alert developers when a version bump is available, but they open dumb PRs that simply bump `package.json` or `pyproject.toml` by a single line. When the new version contains breaking API changes, the build breaks, and engineers spend hours reading migration guides and rewriting call sites.

We built Telex because language-aware static analysis (Tree-sitter ASTs) combined with LLM code synthesis and isolated ephemeral test runners can eliminate 90% of this mechanical migration work without introducing hallucination risk.

---

### 3. What is new about what you're doing? Why hasn't this been done before?
Existing dependency tools are dumb version-bumpers:
- **Dependabot / Renovate**: Only touch manifest files (`package.json`, `Cargo.toml`). They have zero knowledge of call sites, ASTs, or API rewrites.
- **LLM Coding Agents**: Generic AI agents rewrite code blindly without package boundary isolation or fail-closed verification, often changing business logic or inventing non-existent APIs.

Telex bridges the gap:
1. **Deterministic AST Boundaries**: Tree-sitter queries guarantee that only symbols imported from the target package are rewritten. If `axios.get` and `lodash.get` are both in a file, Telex never confuses them.
2. **Fail-Closed Sandbox Verification**: A patch is only submitted if the repository's test suite and typecheck gates pass 100% in a secure sandbox.
3. **Cryptographic Verification Receipts**: Every PR embeds the exact `base_sha` and `commit_sha` on which CI passed, preventing stale or drifted patches.

---

### 4. Who are your competitors, and what do you understand that they don't?
- **Competitors**: Dependabot, Renovate, Snyk, Codemod.com.
- **What We Understand**:
  1. *Version bumping is not maintenance.* Opening a broken PR creates engineering friction, not value. The value is in fixing the call sites and proving they work before notification.
  2. *Developers will never trust an autonomous tool that auto-merges.* Semantic risk is real. Our architecture separates mechanical renaming from semantic risk, enforcing human signoff on all PRs.
  3. *Supply chain security must be fail-closed.* Lifecycle install scripts (`postinstall`, `setup.py`) must be disabled by default during sandbox verification to prevent supply-chain attacks.

---

### 5. How will you make money? What is your pricing model?
- **Open Source / Individual Developers**: Free tier for public repositories and local CLI usage (`telex-core scan`, `telex-core verify`).
- **Team & Enterprise (B2B SaaS)**:
  - $49/seat/month: Automated background registry watching, managed ephemeral sandbox runners, pull request dispatch, and human review triage digest.
  - Enterprise ($2,500/mo+): Self-hosted sandbox runners (BYOK credentials, VPC isolation), custom internal package registry support, and SLA compliance.

---

### 6. How do you acquire users and distribution?
- **Developer-First Open Source CLI**: `npx @telex/core` and `poetry add telex-core` allow developers to scan their repos locally in seconds with zero configuration.
- **GitHub Marketplace App**: 1-click installation to monitor fleet repositories.
- **Open Source Migration Public PRs**: When popular packages release major versions (e.g. OpenAI v1, Next.js v15, Pydantic v2), Telex generates verified PRs for high-impact open-source projects, demonstrating value directly to maintainers.

---

### 7. What are the key technical risks, and how are they mitigated?

| Technical Risk | Telex Architecture Mitigation |
|---|---|
| **AI Hallucination in Code Patches** | Tree-sitter restricts rewrites strictly to matching call sites; sandbox test suite must pass 100%; human review is mandatory. |
| **Supply Chain Code Execution in Sandbox** | `allow_install_scripts` defaults to `False`; execution is ephemeral and network-restricted. |
| **Silent Failures on Test Files** | `detect_symbol_in_tests` actively checks test suites to ensure migration covers all test files. |
| **Repository Authorization & Credential Leaks** | Strict multi-tenant isolation; BYOK keys encrypted with AES-256-GCM; webhook HMAC SHA-256 verification. |

---

### 8. Verifiable System Proof Points (Code Truth)
- **Active Test Suite**: 294 passing automated unit and integration tests (`apps/api` + `telex-core`).
- **Frontend Quality**: Zero TypeScript compilation errors in production web console.
- **Supported Ecosystems**: Node/npm, Python/PyPI, Go (`go.mod`), Rust (`Cargo.toml`), Java (`pom.xml`), Ruby (`Gemfile`), C# (`.csproj`).
