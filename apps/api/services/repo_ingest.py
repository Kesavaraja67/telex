"""
Repo ingestion for Atlas — fetches a full repo snapshot via GitHub's tarball
endpoint (one HTTP call) instead of the Contents API per-file (N calls).

Rate-limit and memory discipline: a 2,000-file repo fetched file-by-file via
the Contents API could burn 2,000+ requests and round trips. The tarball
endpoint returns the whole tree in one authenticated request, scoped to the
installation token exactly like every other github_service.py call.
"""

import io
import logging
import shutil
import tarfile
import tempfile
from pathlib import Path

import httpx

from services.github_service import get_installation_token

logger = logging.getLogger(__name__)

MAX_TARBALL_BYTES = 150 * 1024 * 1024  # 150 MB hard cap — reject absurdly large repos
MAX_FILE_BYTES_FOR_PARSE = 2 * 1024 * 1024  # skip parsing (not skip listing) files > 2MB


async def fetch_repo_snapshot(
    repo_full_name: str,
    installation_id: int,
    ref: str,
) -> Path:
    """
    Downloads GitHub's codeload tarball for `ref` using the installation
    token, extracts it into a fresh temp directory, and returns that
    directory's path. Caller is responsible for cleanup (shutil.rmtree).

    Raises RuntimeError on any failure — caller (the job handler) lets the
    existing job retry/backoff mechanism handle transient errors.
    """
    token = get_installation_token(installation_id)
    url = f"https://api.github.com/repos/{repo_full_name}/tarball/{ref}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        async with client.stream("GET", url, headers=headers) as resp:
            if resp.status_code != 200:
                raise RuntimeError(
                    f"tarball fetch failed for {repo_full_name}@{ref}: {resp.status_code}"
                )
            buffer = io.BytesIO()
            total_bytes = 0
            async for chunk in resp.aiter_bytes():
                total_bytes += len(chunk)
                if total_bytes > MAX_TARBALL_BYTES:
                    raise RuntimeError(
                        f"repo tarball for {repo_full_name}@{ref} exceeds {MAX_TARBALL_BYTES} bytes — refusing to ingest"
                    )
                buffer.write(chunk)
            content = buffer.getvalue()

    tmpdir = Path(tempfile.mkdtemp(prefix="telex_atlas_"))
    try:
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tf:
            # GitHub tarballs wrap everything in one top-level "<owner>-<repo>-<sha>/" dir.
            # The tarball is third-party content: the "data" filter rejects absolute paths,
            # ".." traversal, links that escape the destination, and special files.
            try:
                tf.extractall(path=tmpdir, filter="data")
            except TypeError:
                safe_members = []
                resolved_tmp = tmpdir.resolve()
                for member in tf.getmembers():
                    member_path = (tmpdir / member.name).resolve()
                    if not member_path.is_relative_to(resolved_tmp) or not (
                        member.isfile() or member.isdir()
                    ):
                        logger.warning("Skipping unsafe tar member: %s", member.name)
                        continue
                    safe_members.append(member)
                tf.extractall(path=tmpdir, members=safe_members)

        # Descend into the single top-level directory GitHub always wraps content in
        children = list(tmpdir.iterdir())
        if len(children) == 1 and children[0].is_dir():
            return children[0]
        return tmpdir
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
