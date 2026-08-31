"""
Repository Service — dynamically fetches LIVE real-time repository data,
recent git commits, and Gemini 2.5 Flash architectural insights from GitHub API
for both personal repositories and industry benchmark repositories.
"""
import os
import json
import asyncio
import logging
import urllib.request
import subprocess
from datetime import datetime, timezone
import time
from typing import Optional, List, Any
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

def _parse_github_datetime(iso_str: Optional[str]) -> str:
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

def fetch_live_github_commits(repo_full_name: str, limit: int = 5) -> list[dict]:
    """Fetch live recent commits for a repository from GitHub API."""
    cache_key = f"{repo_full_name}-{limit}"
    cached = _CACHE["commits_by_repo"].get(cache_key)
    if cached and (time.time() - cached["time"]) < 90:
        return cached["data"]

    url = f"https://api.github.com/repos/{repo_full_name}/commits?per_page={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Telex-Autonomous-Agent"})
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
                commits.append({
                    "hash": sha,
                    "short_hash": sha[:7] if sha else "HEAD",
                    "author": committer_obj.get("login") or author_obj.get("name") or "Developer",
                    "email": author_obj.get("email") or "dev@github.com",
                    "relative_time": rel_time,
                    "date": rel_time,
                    "message": commit_obj.get("message", "Update codebase").split("\n")[0],
                })
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
        res = subprocess.run(cmd, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        commits = []
        for line in res.stdout.strip().split("\n"):
            if not line: continue
            p = line.split("|")
            if len(p) >= 5:
                commits.append({
                    "hash": p[0],
                    "short_hash": p[0][:7],
                    "author": p[1],
                    "email": p[2],
                    "relative_time": p[3],
                    "date": p[3],
                    "message": "|".join(p[4:]),
                })
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
        "id": "razorpay-node",
        "full_name": "razorpay/razorpay-node",
        "name": "razorpay-node",
        "owner": "razorpay",
        "description": "Official Node.js SDK for Razorpay payment gateway API integration, orders, refunds, and webhook HMAC verification.",
        "default_branch": "master",
        "is_active": True,
        "created_at": datetime(2016, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
        "github_url": "https://github.com/razorpay/razorpay-node",
        "languages": ["TypeScript", "JavaScript"],
        "patch_count": 312,
        "status": "healthy",
        "category": "benchmark",
        "dependencies": ["request-promise-native", "crypto"],
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


def fetch_repo_metadata_from_github(repo_full_name: str, default_branch: str = "main") -> dict[str, Any]:
    """Dynamically fetches real repository description, languages, and dependencies from GitHub API."""
    metadata: dict[str, Any] = {
        "description": "Connected repository monitored by Telex autonomous telemetry engine.",
        "languages": ["TypeScript"],
        "dependencies": ["typescript"],
    }

    # 1. Fetch repo description & primary language from GitHub API
    try:
        url = f"https://api.github.com/repos/{repo_full_name}"
        req = urllib.request.Request(url, headers={"User-Agent": "Telex-Autonomous-Agent"})
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
        req = urllib.request.Request(lang_url, headers={"User-Agent": "Telex-Autonomous-Agent"})
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
        req = urllib.request.Request(pkg_url, headers={"User-Agent": "Telex-Autonomous-Agent"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            pkg = json.loads(resp.read().decode())
            deps = list(pkg.get("dependencies", {}).keys())
            if deps:
                metadata["dependencies"] = deps[:6]
    except Exception:
        try:
            # Fallback for Python repos: requirements.txt on default branch
            req_url = f"https://raw.githubusercontent.com/{repo_full_name}/{branch_to_use}/requirements.txt"
            req = urllib.request.Request(req_url, headers={"User-Agent": "Telex-Autonomous-Agent"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                lines = [l.strip().split("==")[0].split(">=")[0] for l in resp.read().decode().splitlines() if l.strip() and not l.startswith("#")]
                if lines:
                    metadata["dependencies"] = lines[:6]
        except Exception:
            pass

    return metadata


async def get_core_repositories_async() -> list[dict]:
    """Dynamically loads connected repositories from the database and hydrates live GitHub commit telemetry."""
    from db.session import AsyncSessionLocal
    from db.models import Repo, PullRequest
    from sqlalchemy import select, func

    personal_repos: list[dict] = []
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Repo).where(Repo.is_active == True))
            db_repos = result.scalars().all()

            if not db_repos:
                # No repos connected — dashboard shows empty personal section with connect prompt
                personal_repos = []
            else:
                for r in db_repos:
                    commits = await asyncio.to_thread(fetch_live_github_commits, r.full_name, 5)
                    meta = await asyncio.to_thread(
                        fetch_repo_metadata_from_github,
                        r.full_name,
                        r.default_branch or "main",
                    )
                    parts = r.full_name.split("/")
                    owner = parts[0] if len(parts) > 1 else "User"
                    name = parts[1] if len(parts) > 1 else r.full_name

                    pr_res = await session.execute(
                        select(func.count(PullRequest.id)).where(PullRequest.repo_id == r.id)
                    )
                    pr_count: int = pr_res.scalar_one() or 0

                    personal_repos.append({
                        "id": str(r.id),
                        "full_name": r.full_name,
                        "name": name,
                        "owner": owner,
                        "description": meta.get("description") or f"Autonomous codebase tracked by Telex Engine ({', '.join(meta['languages'])}).",
                        "default_branch": r.default_branch or "main",
                        "is_active": r.is_active,
                        "created_at": r.created_at,
                        "github_url": f"https://github.com/{r.full_name}",
                        "languages": meta.get("languages") or ["TypeScript"],
                        "patch_count": pr_count,
                        "status": "healthy",
                        "category": "personal",
                        "commits": commits,
                        "last_commit": commits[0] if commits else None,
                        "dependencies": meta.get("dependencies") or ["typescript"],
                    })
    except Exception as exc:
        logger.exception("get_core_repositories_async failed to load repositories: %s", exc)
        personal_repos = []

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
    repos = await get_core_repositories_async()
    target_repo = next((r for r in repos if r["id"] == repo_id or r["full_name"].lower() == repo_id.lower() or r["name"].lower() == repo_id.lower()), None)
    if not target_repo:
        raise KeyError(f"Repository '{repo_id}' not found")

    settings = get_settings()
    gemini = GeminiProvider(api_key=settings.gemini_api_key)
    return await gemini.explain_repo_architecture(
        repo_name=target_repo["full_name"],
        commits=target_repo.get("commits", []),
        dependencies=target_repo.get("dependencies", []),
    )
