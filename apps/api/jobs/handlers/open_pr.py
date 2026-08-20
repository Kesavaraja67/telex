"""
open_pr handler — bundles all verified patches for a repo+version into one PR.

Payload shape:
    { "repo_id": "<uuid>", "package_version_id": "<uuid>" }
"""
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


async def run(payload: dict) -> None:
    from db.session import AsyncSessionLocal
    from db.models import (
        Repo, PackageVersion, Package, DetectedChange,
        CodeUsage, Patch, PullRequest, Installation,
    )
    from services.github_service import open_patch_pr, get_installation_client
    from sqlalchemy import select

    repo_id = uuid.UUID(payload["repo_id"])
    package_version_id = uuid.UUID(payload["package_version_id"])

    async with AsyncSessionLocal() as session:
        repo = await session.get(Repo, repo_id)
        pv = await session.get(PackageVersion, package_version_id)

        if repo is None or pv is None:
            logger.error("open_pr: repo %s or version %s not found", repo_id, package_version_id)
            return

        pkg = await session.get(Package, pv.package_id)
        installation = await session.get(Installation, repo.installation_id)

        if pkg is None or installation is None:
            logger.error("open_pr: package or installation missing for repo %s", repo_id)
            return

        # Read scalar values before the session closes to avoid DetachedInstanceError
        repo_full_name = repo.full_name
        repo_default_branch = repo.default_branch
        installation_github_id = installation.github_installation_id
        pkg_name = pkg.name
        pv_version = pv.version

        # Collect all verified patches for this repo + version
        patches_result = await session.execute(
            select(Patch)
            .join(CodeUsage, Patch.code_usage_id == CodeUsage.id)
            .join(DetectedChange, CodeUsage.detected_change_id == DetectedChange.id)
            .where(
                CodeUsage.repo_id == repo_id,
                DetectedChange.package_version_id == package_version_id,
                Patch.verified == True,
            )
        )
        patches = list(patches_result.scalars())

        if not patches:
            logger.info("open_pr: no verified patches for repo %s version %s", repo_id, package_version_id)
            return

        # Pre-load CodeUsage rows (avoids lazy-load outside session)
        usage_map: dict = {}
        for p in patches:
            cu = await session.get(CodeUsage, p.code_usage_id)
            if cu:
                usage_map[p.id] = cu

    # ── PyGithub calls run in a thread — they are blocking I/O ───────────────
    gh = await asyncio.to_thread(get_installation_client, installation_github_id)
    gh_repo = await asyncio.to_thread(gh.get_repo, repo_full_name)

    patch_dicts: list[dict] = []
    for p in patches:
        cu = usage_map.get(p.id)
        if not cu:
            continue
        try:
            content_file = await asyncio.to_thread(
                gh_repo.get_contents, cu.file_path, ref=repo_default_branch
            )
            original = content_file.decoded_content.decode("utf-8")  # type: ignore
        except Exception as exc:
            logger.warning("open_pr: could not fetch %s: %s", cu.file_path, exc)
            continue

        # For Phase 1, we store the raw diff in the PR body instead of auto-applying.
        # Full patch application (subprocess `patch`) comes in Phase 2.
        patch_dicts.append(
            {
                "file_path": cu.file_path,
                "new_content": original,  # placeholder — real apply in Phase 2
                "package_name": pkg_name,
                "new_version": pv_version,
                "diff": p.diff,
            }
        )

    # Guard: don't open a no-op PR with zero patches collected
    if not patch_dicts:
        logger.warning(
            "open_pr: no patch content collected for repo %s version %s — skipping PR",
            repo_id, package_version_id,
        )
        return

    # Build PR body
    body_lines = [
        f"## Telex Auto-Patch: `{pkg_name}` → `{pv_version}`\n",
        "Telex detected breaking API changes and generated the following patches.\n",
        "**Review each diff carefully before merging. Never auto-merge.**\n",
    ]
    for i, pd in enumerate(patch_dicts, 1):
        body_lines.append(f"\n### Patch {i}: `{pd['file_path']}`\n")
        body_lines.append(f"```diff\n{pd['diff']}\n```\n")

    summary = "\n".join(body_lines)
    branch_name = f"telex/{pkg_name}/{pv_version}"

    try:
        pr_url, pr_number = await open_patch_pr(
            repo_full_name=repo_full_name,
            installation_id=installation_github_id,
            branch_name=branch_name,
            patches=patch_dicts,
            summary=summary,
        )
    except Exception as exc:
        logger.error("open_pr: failed to open PR: %s", exc)
        return

    # Record the PR
    async with AsyncSessionLocal() as session:
        pr = PullRequest(
            repo_id=repo_id,
            package_version_id=package_version_id,
            github_pr_number=pr_number,
            github_pr_url=pr_url,
            patch_ids=[p.id for p in patches],
        )
        session.add(pr)
        await session.commit()

    logger.info("open_pr: opened PR #%d on %s (%s)", pr_number, repo_full_name, pr_url)

