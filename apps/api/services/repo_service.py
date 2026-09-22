"""
Repository Service — dynamically fetches LIVE real-time repository data,
recent git commits, and Gemini 2.5 Flash architectural insights from GitHub API
for both personal repositories and industry benchmark repositories.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from config import get_settings
from services.patch_providers.gemini import GeminiProvider

logger = logging.getLogger(__name__)

# In-memory cache with 60s TTL to prevent GitHub rate limits
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_CACHE: dict[str, Any] = {
    "repos": None,
    "repos_time": 0,
    "commits_by_repo": {},
}


def _parse_github_datetime(iso_str: str | None) -> str:
    """Formats GitHub ISO datetime into human-friendly relative time."""
    if not iso_str:
        return "recently"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        return dt.strftime("%b %d, %Y")
    except Exception:
        return iso_str[:10]


def fetch_live_github_commits(repo_full_name: str, limit: int = 5, token: str | None = None) -> list[dict]:
    """Fetch live recent commits for a repository from GitHub API."""
    cache_key = f"{repo_full_name}-{limit}"
    cached = _CACHE["commits_by_repo"].get(cache_key)
    if cached and (time.time() - cached["time"]) < 90:
        return cached["data"]

    url = f"https://api.github.com/repos/{repo_full_name}/commits?per_page={limit}"
    headers = {
        "User-Agent": "Telex-Autonomous-Agent",
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=6) as response:
            commits_raw = json.loads(response.read().decode())
            commits = []
            for c in commits_raw:
                commit_obj = c.get("commit", {})
                author_obj = commit_obj.get("author", {})
                committer_obj = c.get("author", {}) or {}
                sha = c.get("sha", "")
                date_str = author_obj.get("date")
                rel_time = _parse_github_datetime(date_str)
                commits.append(
                    {
                        "hash": sha,
                        "short_hash": sha[:7] if sha else "HEAD",
                        "author": committer_obj.get("login")
                        or author_obj.get("name")
                        or "Developer",
                        "email": author_obj.get("email") or "dev@github.com",
                        "relative_time": rel_time,
                        "date": rel_time,
                        "message": commit_obj.get("message", "Update codebase").split("\n")[0],
                    }
                )
            _CACHE["commits_by_repo"][cache_key] = {"data": commits, "time": time.time()}
            return commits
    except Exception:
        return []


def get_local_git_commits(repo_path: str, limit: int = 5) -> list[dict]:
    """Fallback local git parser."""
    if not os.path.exists(repo_path) or not os.path.exists(os.path.join(repo_path, ".git")):
        return []
    try:
        cmd = ["git", "log", f"-n{limit}", "--pretty=format:%H|%an|%ae|%ad|%s", "--date=relative"]
        res = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        commits = []
        for line in res.stdout.strip().split("\n"):
            if not line:
                continue
            p = line.split("|")
            if len(p) >= 5:
                commits.append(
                    {
                        "hash": p[0],
                        "short_hash": p[0][:7],
                        "author": p[1],
                        "email": p[2],
                        "relative_time": p[3],
                        "date": p[3],
                        "message": "|".join(p[4:]),
                    }
                )
        return commits
    except Exception:
        return []


BENCHMARK_REPOS: list[dict[str, Any]] = [
    {
        "id": "next-js",
        "full_name": "vercel/next.js",
        "name": "next.js",
        "owner": "vercel",
        "description": "The React Framework for the Web — App Router, Server Actions, Dynamic I/O, and Turbopack.",
        "default_branch": "canary",
        "is_active": True,
        "created_at": datetime(2016, 10, 25, 0, 0, 0, tzinfo=timezone.utc),
        "github_url": "https://github.com/vercel/next.js",
        "languages": ["Rust", "TypeScript", "JavaScript"],
        "patch_count": 1420,
        "status": "healthy",
        "category": "benchmark",
        "dependencies": ["react", "react-dom", "turbopack", "swc"],
    },
    {
        "id": "openai-python",
        "full_name": "openai/openai-python",
        "name": "openai-python",
        "owner": "openai",
        "description": "The official Python library for the OpenAI API with streaming completions, audio, and structured outputs.",
        "default_branch": "main",
        "is_active": True,
        "created_at": datetime(2020, 6, 11, 0, 0, 0, tzinfo=timezone.utc),
        "github_url": "https://github.com/openai/openai-python",
        "languages": ["Python", "Pydantic", "Httpx"],
        "patch_count": 684,
        "status": "healthy",
        "category": "benchmark",
        "dependencies": ["httpx", "pydantic", "typing-extensions"],
    },
    {
        "id": "stripe-node",
        "full_name": "stripe/stripe-node",
        "name": "stripe-node",
        "owner": "stripe",
        "description": "Official Stripe Node.js SDK for payments, subscriptions, and platform integrations.",
        "default_branch": "master",
        "is_active": True,
        "created_at": datetime(2013, 9, 12, 0, 0, 0, tzinfo=timezone.utc),
        "github_url": "https://github.com/stripe/stripe-node",
        "languages": ["TypeScript", "JavaScript"],
        "patch_count": 312,
        "status": "healthy",
        "category": "benchmark",
        "dependencies": ["node-fetch", "qs"],
    },
    {
        "id": "fastapi",
        "full_name": "fastapi/fastapi",
        "name": "fastapi",
        "owner": "fastapi",
        "description": "FastAPI framework, high performance, easy to learn, fast to code, ready for production.",
        "default_branch": "master",
        "is_active": True,
        "created_at": datetime(2018, 12, 5, 0, 0, 0, tzinfo=timezone.utc),
        "github_url": "https://github.com/fastapi/fastapi",
        "languages": ["Python", "Starlette", "Pydantic"],
        "patch_count": 915,
        "status": "healthy",
        "category": "benchmark",
        "dependencies": ["starlette", "pydantic", "uvicorn"],
    },
]


def fetch_repo_metadata_from_github(
    repo_full_name: str, default_branch: str = "main", token: str | None = None
) -> dict[str, Any]:
    """Dynamically fetches real repository description, languages, and dependencies from GitHub API."""
    metadata: dict[str, Any] = {
        "description": "Connected repository monitored by Telex autonomous telemetry engine.",
        "languages": ["TypeScript"],
        "dependencies": ["typescript"],
    }
    api_headers = {
        "User-Agent": "Telex-Autonomous-Agent",
        "Accept": "application/vnd.github+json",
    }
    raw_headers = {"User-Agent": "Telex-Autonomous-Agent"}
    if token:
        api_headers["Authorization"] = f"Bearer {token}"
        raw_headers["Authorization"] = f"token {token}"

    # 1. Fetch repo description & primary language from GitHub API
    try:
        url = f"https://api.github.com/repos/{repo_full_name}"
        req = urllib.request.Request(url, headers=api_headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            if data.get("description"):
                metadata["description"] = data["description"]
            if data.get("language"):
                metadata["languages"] = [data["language"]]
    except Exception:
        pass

    # 2. Fetch full languages breakdown
    try:
        lang_url = f"https://api.github.com/repos/{repo_full_name}/languages"
        req = urllib.request.Request(lang_url, headers=api_headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            lang_data = json.loads(resp.read().decode())
            if lang_data:
                metadata["languages"] = list(lang_data.keys())[:3]
    except Exception:
        pass

    # 3. Dynamically extract real dependencies from package.json or requirements.txt using default_branch
    branch_to_use = default_branch or "main"
    try:
        # Check raw package.json on default branch
        pkg_url = f"https://raw.githubusercontent.com/{repo_full_name}/{branch_to_use}/package.json"
        req = urllib.request.Request(pkg_url, headers=raw_headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            pkg = json.loads(resp.read().decode())
            deps = list(pkg.get("dependencies", {}).keys())
            if deps:
                metadata["dependencies"] = deps[:6]
    except Exception:
        try:
            # Fallback for Python repos: requirements.txt on default branch
            req_url = f"https://raw.githubusercontent.com/{repo_full_name}/{branch_to_use}/requirements.txt"
            req = urllib.request.Request(req_url, headers=raw_headers)
            with urllib.request.urlopen(req, timeout=4) as resp:
                lines = [
                    line.strip().split("==")[0].split(">=")[0]
                    for line in resp.read().decode().splitlines()
                    if line.strip() and not line.startswith("#")
                ]
                if lines:
                    metadata["dependencies"] = lines[:6]
        except Exception:
            pass

    return metadata


_LAST_SYNC_TIME: float = 0.0


async def sync_github_app_repositories_async(user_id: str | None = None) -> None:
    """
    Directly queries GitHub App installations and syncs accessible repositories
    into the database so newly connected repositories are immediately available
    even if webhook delivery to localhost is unavailable.
    """
    global _LAST_SYNC_TIME
    settings = get_settings()
    if not settings.github_app_id or not settings.github_app_private_key:
        return

    import httpx
    from github import GithubIntegration
    from sqlalchemy import select

    from db.models import Installation, Repo, User
    from db.session import AsyncSessionLocal

    try:
        private_key = settings.github_app_private_key.replace("\\n", "\n").strip("\"'")
        integration = GithubIntegration(int(settings.github_app_id), private_key)
        installations = await asyncio.to_thread(lambda: list(integration.get_installations()))

        async with AsyncSessionLocal() as session:
            current_user = None
            if user_id:
                try:
                    user_res = await session.execute(
                        select(User).where(User.id == uuid.UUID(str(user_id)))
                    )
                    current_user = user_res.scalar_one_or_none()
                except Exception:
                    pass

            for inst in installations:
                account_login = inst.raw_data.get("account", {}).get("login", "unknown")
                token = await asyncio.to_thread(
                    lambda i_id=inst.id: integration.get_access_token(i_id).token
                )

                res = await session.execute(
                    select(Installation).where(Installation.github_installation_id == inst.id)
                )
                db_inst = res.scalar_one_or_none()
                if not db_inst:
                    db_inst = Installation(
                        github_installation_id=inst.id,
                        account_login=account_login,
                        account_type=inst.raw_data.get("account", {}).get("type", "User"),
                    )
                    session.add(db_inst)
                    await session.flush()

                if current_user:
                    if (
                        account_login.lower() == current_user.github_login.lower()
                        or not db_inst.installed_by
                    ):
                        db_inst.installed_by = current_user.id
                elif user_id and not db_inst.installed_by:
                    try:
                        db_inst.installed_by = uuid.UUID(str(user_id))
                    except Exception:
                        pass

                async with httpx.AsyncClient(timeout=15.0) as client:
                    gh_repos = []
                    page = 1
                    while True:
                        resp = await client.get(
                            "https://api.github.com/installation/repositories",
                            params={"per_page": 100, "page": page},
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Accept": "application/vnd.github+json",
                                "User-Agent": "Telex-Autonomous-Agent",
                            },
                        )
                        if resp.status_code != 200:
                            break
                        data = resp.json()
                        page_repos = data.get("repositories", [])
                        gh_repos.extend(page_repos)
                        total_count = data.get("total_count", len(gh_repos))
                        if not page_repos or len(gh_repos) >= total_count:
                            break
                        page += 1

                    if gh_repos:
                        active_gh_ids = set()
                        for gr in gh_repos:
                            active_gh_ids.add(gr["id"])
                            r_res = await session.execute(
                                select(Repo).where(Repo.github_repo_id == gr["id"])
                            )
                            db_repo = r_res.scalar_one_or_none()
                            if db_repo:
                                db_repo.installation_id = db_inst.id
                                db_repo.is_active = True
                                db_repo.full_name = gr["full_name"]
                                db_repo.default_branch = gr.get("default_branch", "main")
                            else:
                                db_repo = Repo(
                                    installation_id=db_inst.id,
                                    github_repo_id=gr["id"],
                                    full_name=gr["full_name"],
                                    default_branch=gr.get("default_branch", "main"),
                                    is_active=True,
                                )
                                session.add(db_repo)

                        # Deactivate repos no longer returned for this installation
                        all_inst_repos = (
                            (
                                await session.execute(
                                    select(Repo).where(Repo.installation_id == db_inst.id)
                                )
                            )
                            .scalars()
                            .all()
                        )
                        for r in all_inst_repos:
                            if r.github_repo_id not in active_gh_ids:
                                r.is_active = False

                        await session.commit()
                        logger.info(
                            "Successfully synced %d repos for installation %s",
                            len(gh_repos),
                            inst.id,
                        )

        _LAST_SYNC_TIME = time.time()
    except Exception as exc:
        logger.warning("sync_github_app_repositories_async error: %s", exc)


async def get_core_repositories_async(
    force_sync: bool = False,
    include_benchmarks: bool = False,
    user_id: str | None = None,
) -> list[dict]:
    """Dynamically loads connected repositories from the database and hydrates live GitHub commit telemetry in parallel."""
    global _LAST_SYNC_TIME
    if force_sync or (time.time() - _LAST_SYNC_TIME) > 30:
        await sync_github_app_repositories_async(user_id=user_id)

    from sqlalchemy import func, or_, select

    from db.models import Installation, PullRequest, Repo, User
    from db.session import AsyncSessionLocal

    personal_repos: list[dict] = []
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Repo).where(Repo.is_active == True)
            if user_id:
                try:
                    user_uuid = uuid.UUID(str(user_id))
                    user_res = await session.execute(
                        select(User).where(User.id == user_uuid)
                    )
                    cur_user = user_res.scalar_one_or_none()
                    user_login = cur_user.github_login.lower() if cur_user else None

                    conditions = [Installation.installed_by == user_uuid]
                    if user_login:
                        conditions.append(func.lower(Installation.account_login) == user_login)

                    user_inst_res = await session.execute(
                        select(Installation.id).where(or_(*conditions))
                    )
                    user_inst_ids = [row[0] for row in user_inst_res.all()]
                    if user_inst_ids:
                        stmt = stmt.where(Repo.installation_id.in_(user_inst_ids))
                except Exception:
                    pass

            result = await session.execute(stmt)
            db_repos = result.scalars().all()

            if not db_repos:
                personal_repos = []
            else:
                # Cache installation access tokens to avoid rate limits
                inst_token_map: dict[Any, str] = {}
                inst_ids = {r.installation_id for r in db_repos if r.installation_id}
                if inst_ids:
                    inst_records = (
                        await session.execute(
                            select(Installation).where(Installation.id.in_(inst_ids))
                        )
                    ).scalars().all()
                    for inst_record in inst_records:
                        try:
                            from services.github_service import get_installation_token

                            token = await asyncio.to_thread(
                                get_installation_token, inst_record.github_installation_id
                            )
                            if token:
                                inst_token_map[inst_record.id] = token
                        except Exception:
                            pass

                async def hydrate_repo(r: Repo) -> dict:
                    token = inst_token_map.get(r.installation_id)
                    commits_task = asyncio.to_thread(
                        fetch_live_github_commits, r.full_name, 5, token
                    )
                    meta_task = asyncio.to_thread(
                        fetch_repo_metadata_from_github,
                        r.full_name,
                        r.default_branch or "main",
                        token,
                    )
                    pr_task = session.execute(
                        select(func.count(PullRequest.id)).where(PullRequest.repo_id == r.id)
                    )

                    commits, meta, pr_res = await asyncio.gather(
                        commits_task, meta_task, pr_task, return_exceptions=True
                    )
                    commits = commits if isinstance(commits, list) else []
                    meta = meta if isinstance(meta, dict) else {}
                    pr_count: int = pr_res.scalar_one() if hasattr(pr_res, "scalar_one") else 0

                    parts = r.full_name.split("/")
                    owner = parts[0] if len(parts) > 1 else "User"
                    name = parts[1] if len(parts) > 1 else r.full_name

                    return {
                        "id": str(r.id),
                        "full_name": r.full_name,
                        "name": name,
                        "owner": owner,
                        "description": meta.get("description")
                        or f"Autonomous codebase tracked by Telex Engine ({', '.join(meta.get('languages', ['TypeScript']))}).",
                        "default_branch": r.default_branch or "main",
                        "is_active": r.is_active,
                        "requires_tests": r.requires_tests,
                        "requires_typecheck": r.requires_typecheck,
                        "created_at": r.created_at,
                        "github_url": f"https://github.com/{r.full_name}",
                        "languages": meta.get("languages") or ["TypeScript"],
                        "patch_count": pr_count,
                        "status": "healthy",
                        "category": "personal",
                        "commits": commits,
                        "last_commit": commits[0] if commits else None,
                        "dependencies": meta.get("dependencies") or ["typescript"],
                    }

                hydrated = await asyncio.gather(*(hydrate_repo(r) for r in db_repos))
                personal_repos = [h for h in hydrated if isinstance(h, dict)]
    except Exception as exc:
        logger.exception("get_core_repositories_async failed to load repositories: %s", exc)
        personal_repos = []

    # Only return benchmarks if explicitly requested
    if not include_benchmarks:
        return personal_repos

    # Hydrate benchmarks with latest commits
    hydrated_benchmarks = []
    for b in BENCHMARK_REPOS:
        commits = await asyncio.to_thread(fetch_live_github_commits, str(b["full_name"]), 3)
        b_copy: dict[str, Any] = dict(b)
        b_copy["commits"] = commits
        b_copy["last_commit"] = commits[0] if commits else None
        hydrated_benchmarks.append(b_copy)

    return personal_repos + hydrated_benchmarks


async def explain_repo_with_gemini(repo_id: str) -> dict:
    """Invokes Gemini 2.5 Flash to generate live deep architectural and commit intelligence for a repo."""
    repos = await get_core_repositories_async(include_benchmarks=True)
    target_repo = next(
        (
            r
            for r in repos
            if r["id"] == repo_id
            or r["full_name"].lower() == repo_id.lower()
            or r["name"].lower() == repo_id.lower()
        ),
        None,
    )
    if not target_repo:
        raise KeyError(f"Repository '{repo_id}' not found")

    settings = get_settings()
    gemini = GeminiProvider(api_key=settings.gemini_api_key)
    return await gemini.explain_repo_architecture(
        repo_name=target_repo["full_name"],
        commits=target_repo.get("commits", []),
        dependencies=target_repo.get("dependencies", []),
    )
