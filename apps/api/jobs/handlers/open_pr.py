"""
open_pr handler — bundles all verified patches for a repo+version into one PR.

Payload shape:
    { "repo_id": "<uuid>", "package_version_id": "<uuid>" }
"""
import logging
import uuid

logger = logging.getLogger(__name__)


async def run(payload: dict) -> None:
    from db.session import AsyncSessionLocal
    from db.models import (
        Repo, PackageVersion, Package, DetectedChange,
        CodeUsage, Patch, PullRequest,
    )
    from services.github_service import open_patch_pr, get_installation_client
    from sqlalchemy import select

    repo_id = uuid.UUID(payload["repo_id"])
    package_version_id = uuid.UUID(payload["package_version_id"])

    async with AsyncSessionLocal() as session:
        repo = await session.get(Repo, repo_id)
        pv = await session.get(PackageVersion, package_version_id)
        pkg = await session.get(Package, pv.package_id)
        installation = await session.get(
            __import__("db.models", fromlist=["Installation"]).Installation,
            repo.installation_id,
        )

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

        # Build the file-level content dict from patches
        # (Full apply logic would use `patch` CLI; simplified here for Phase 1)
        gh = get_installation_client(installation.github_installation_id)
        gh_repo = gh.get_repo(repo.full_name)

        patch_dicts: list[dict] = []
        for p in patches:
            cu = await session.get(CodeUsage, p.code_usage_id)
            try:
                content_file = gh_repo.get_contents(cu.file_path, ref=repo.default_branch)
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
                    "package_name": pkg.name,
                    "new_version": pv.version,
                    "diff": p.diff,
                }
            )

        # Build PR body
        body_lines = [
            f"## Telex Auto-Patch: `{pkg.name}` → `{pv.version}`\n",
            "Telex detected breaking API changes and generated the following patches.\n",
            "**Review each diff carefully before merging. Never auto-merge.**\n",
        ]
        for i, pd in enumerate(patch_dicts, 1):
            body_lines.append(f"\n### Patch {i}: `{pd['file_path']}`\n")
            body_lines.append(f"```diff\n{pd['diff']}\n```\n")

        summary = "\n".join(body_lines)
        branch_name = f"telex/{pkg.name}/{pv.version}"

        try:
            pr_url, pr_number = await open_patch_pr(
                repo_full_name=repo.full_name,
                installation_id=installation.github_installation_id,
                branch_name=branch_name,
                patches=patch_dicts,
                summary=summary,
            )
        except Exception as exc:
            logger.error("open_pr: failed to open PR: %s", exc)
            return

        # Record the PR
        pr = PullRequest(
            repo_id=repo_id,
            package_version_id=package_version_id,
            github_pr_number=pr_number,
            github_pr_url=pr_url,
            patch_ids=[p.id for p in patches],
        )
        session.add(pr)
        await session.commit()

    logger.info("open_pr: opened PR #%d on %s (%s)", pr_number, repo.full_name, pr_url)
