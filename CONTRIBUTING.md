<a id="top"></a>

<div align="center">

  <h1>Contributing to Telex</h1>
  <p><b>Guidelines for Engineering, Pull Requests, Code Style & Community Standards</b></p>

  <p>
    <a href="https://github.com/psf/black">
      <img src="https://img.shields.io/badge/Code%20Style-Black-050508?style=flat-square" alt="Black" />
    </a>
    <a href="https://github.com/astral-sh/ruff">
      <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square" alt="Ruff" />
    </a>
    <img src="https://img.shields.io/badge/Coverage-Enforced%20%E2%89%A580%25-10B981?style=flat-square" alt="Coverage >= 80%" />
    <img src="https://img.shields.io/badge/PRs-Welcome-14B8A6?style=flat-square" alt="PRs Welcome" />
  </p>

  <br>

  <p>
    <a href="#code-of-conduct"><b>Code of Conduct</b></a> &nbsp;•&nbsp;
    <a href="#workflow-policies"><b>Policies</b></a> &nbsp;•&nbsp;
    <a href="#local-setup"><b>Local Setup</b></a> &nbsp;•&nbsp;
    <a href="#coding-standards"><b>Standards</b></a> &nbsp;•&nbsp;
    <a href="#pr-guidelines"><b>PR Guidelines</b></a> &nbsp;•&nbsp;
    <a href="#pr-checklist"><b>Checklist</b></a>
  </p>

</div>

<br>

---

<br>

## <a id="code-of-conduct"></a>01. Code of Conduct

All contributors, maintainers, and community members are expected to uphold the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). We are committed to providing a polite, respectful, and harassment-free environment for everyone.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="workflow-policies"></a>02. Contribution Workflow & Policies

### 1. Large Features vs. Small Fixes
- **Substantial Features & Schema Migrations**: For major features or architectural modifications, please open an issue first to align with maintainers before writing code.
- **Bug Fixes, Typo Corrections & Tests**: Bug fixes, documentation updates, and test additions do not require prior approval—feel free to submit a pull request directly.

### 2. Respectful & Professional Communication
- All communication across issues, pull requests, and discussions must remain **polite, constructive, and professional**.
- Explain technical tradeoffs clearly and treat maintainers and fellow contributors with dignity.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="local-setup"></a>03. Local Setup & Verification

### Prerequisites
- **Python**: 3.11+
- **Node.js**: 20+ (`npm` 10+)
- **PostgreSQL**: 15+
- **Git**

### 1. Clone the Repository
```bash
git clone https://github.com/Kesavaraja67/telex.git
cd telex
```

### 2. Backend Setup (`apps/api`)
```bash
cd apps/api

python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

# Run database migrations
alembic upgrade head

# Launch development server
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup (`apps/web`)
```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```
Open `http://localhost:3000` in your browser.

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="coding-standards"></a>04. Engineering Standards

### 1. Python Code (`apps/api`)
- **Formatting**: We use [Black](https://github.com/psf/black) with a line length of 100 characters.
- **Linting & Imports**: We use [Ruff](https://github.com/astral-sh/ruff) for rapid linting and deterministic import sorting.
- **Type Annotations**: Comprehensive type annotations are required on all public functions, database models, and Pydantic schemas.

```bash
cd apps/api
ruff check --fix .
black .
```

### 2. Simple English Code Comments
- **Write code comments and docstrings in simple, plain English.**
- Keep sentences short, concise, and focused on *why* non-obvious logic exists.
- Avoid obscure jargon, idioms, or academic vocabulary.

### 3. Frontend Code (`apps/web`)
- Built with **Next.js 16 (App Router)** and **TypeScript Strict**.
- Follow the design system tokens in [`DESIGN.md`](DESIGN.md).
- Validate types and linting prior to submitting:
  ```bash
  cd apps/web
  npx tsc --noEmit
  npm run lint
  ```

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="pr-guidelines"></a>05. Pull Request Guidelines

### 1. Mandatory Visual Evidence
- **If your pull request modifies any UI, layout, styling, or dashboard workflow, you MUST include visual evidence in the PR description.**
- Acceptable formats:
  - Screenshots (PNG/JPG) showing Before and After states.
  - Video recordings (GIF, MP4, WebM) demonstrating interaction flows.

### 2. Automated Test Coverage (Enforced ≥80%)
- All logic changes require comprehensive unit or integration tests in `apps/api/tests/`.
- CI strictly enforces a **≥80% statement and branch coverage gate**:
  ```bash
  cd apps/api
  pytest --cov=. --cov-report=term-missing --cov-fail-under=80
  ```

### 3. Git Discipline: No Force Pushes & No Rebasing
- **Never Force Push (`--force`)**: Do not rewrite history on branches with open PRs.
- **No Manual Rebasing**: Merge `main` into your branch (`git merge origin/main`) if synchronization is needed.
- Maintainers use GitHub's **Squash and Merge** to guarantee clean linear history on `main`.

### 4. Conventional Commits
Use standard commit prefixes:
- `feat:` New functionality
- `fix:` Bug fix
- `docs:` Documentation updates
- `style:` Formatting or whitespace changes
- `refactor:` Code reorganization without behavioral change
- `test:` Adding or updating tests
- `chore:` Maintenance or build tasks

<br>

<p align="right"><a href="#top"><b>▲ Back to Top</b></a></p>

---

<br>

## <a id="pr-checklist"></a>06. Pull Request Checklist

Before submitting your pull request, verify that all items are checked:

- [ ] **Polite & Professional**: All PR communication is respectful and constructive.
- [ ] **Simple English Comments**: Comments and docstrings are concise and written in plain English.
- [ ] **Tests Included**: Automated tests verify all modified or added code paths.
- [ ] **Test Coverage Above 80%**: Verified locally with `pytest --cov=. --cov-fail-under=80`.
- [ ] **No Force Pushes**: Commit history has not been rewritten or force pushed.
- [ ] **Backend Linting**: Passed `black .` and `ruff check .` with zero errors.
- [ ] **Frontend Validation**: Passed `npx tsc --noEmit` and `npm run lint` with zero errors.
- [ ] **Visual Proof Attached**: UI changes include screenshots or screen recordings.
- [ ] **Conventional Commits**: Commits follow `feat:`, `fix:`, `docs:` formatting.

<br>

<div align="center">
  <a href="#top">
    <img src="https://img.shields.io/badge/%E2%86%91-Back%20to%20Top-050508?style=flat-square&logoColor=white" alt="Back to Top" />
  </a>
</div>
