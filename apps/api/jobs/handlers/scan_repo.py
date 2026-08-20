"""
scan_repo handler — tree-sitter AST scan of a repo for call sites matching
each detected_change in a package version.

Payload shape:
    { "repo_id": "<uuid>", "package_version_id": "<uuid>" }
"""
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)

# Max file size to scan (bytes) — skip huge generated/vendored files
MAX_FILE_BYTES = 500_000

# Extensions to scan
SCAN_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}


async def run(payload: dict) -> None:
    from db.session import AsyncSessionLocal
    from db.models import Repo, DetectedChange, CodeUsage, PackageVersion, Installation
    from services.code_scanner import find_usages
    from services.github_service import get_installation_client
    from jobs.queue import enqueue_job
    from sqlalchemy import select

    repo_id = uuid.UUID(payload["repo_id"])
    package_version_id = uuid.UUID(payload["package_version_id"])

    async with AsyncSessionLocal() as session:
        repo = await session.get(Repo, repo_id)
        if repo is None or not repo.is_active:
            logger.warning("scan_repo: repo %s not found or inactive", repo_id)
            return

        pv = await session.get(PackageVersion, package_version_id)
        if pv is None:
            logger.error("scan_repo: PackageVersion %s not found", package_version_id)
            return

        changes_result = await session.execute(
            select(DetectedChange).where(
                DetectedChange.package_version_id == package_version_id
            )
        )
        changes = list(changes_result.scalars())
        if not changes:
            logger.info("scan_repo: no changes to scan for")
            return

        # Get GitHub client for this installation
        installation = await session.get(Installation, repo.installation_id)
        if installation is None:
            logger.error("scan_repo: installation %s not found", repo.installation_id)
            return

        # Read scalars before session closes to avoid DetachedInstanceError
        repo_full_name = repo.full_name
        repo_default_branch = repo.default_branch
        installation_github_id = installation.github_installation_id
        pv_version = pv.version

    # ── PyGithub blocking calls — run in a thread ────────────────────────────
    gh = await asyncio.to_thread(get_installation_client, installation_github_id)
    gh_repo = await asyncio.to_thread(gh.get_repo, repo_full_name)

    async with AsyncSessionLocal() as session:
        # Re-load entities needed for the scan loop
        repo = await session.get(Repo, repo_id)
        pv = await session.get(PackageVersion, package_version_id)
        changes_result = await session.execute(
            select(DetectedChange).where(
                DetectedChange.package_version_id == package_version_id
            )
        )
        changes = list(changes_result.scalars())

        # Walk the default branch tree and scan each eligible file
        total_usages = 0
        try:
            tree = await asyncio.to_thread(gh_repo.get_git_tree, repo_default_branch, recursive=True)
        except Exception as exc:
            logger.error("scan_repo: failed to fetch git tree for %s: %s", repo_full_name, exc)
            return

        new_usages: list[CodeUsage] = []

        for item in tree.tree:
            if item.type != "blob":
                continue
            ext = "." + item.path.rsplit(".", 1)[-1] if "." in item.path else ""
            if ext not in SCAN_EXTENSIONS:
                continue
            if item.size and item.size > MAX_FILE_BYTES:
                continue

            try:
                content = await asyncio.to_thread(
                    gh_repo.get_contents, item.path, ref=repo_default_branch
                )
                source = content.decoded_content  # type: ignore[union-attr]
            except Exception as exc:
                logger.warning("scan_repo: could not fetch %s: %s", item.path, exc)
                continue

            for change in changes:
                symbol = change.symbol_old.split("(")[0].strip()  # strip signature
                usages = find_usages(item.path, source, symbol)

                for usage in usages:
                    # Idempotent: skip if this exact usage already exists
                    existing = await session.execute(
                        select(CodeUsage).where(
                            CodeUsage.repo_id == repo_id,
                            CodeUsage.detected_change_id == change.id,
                            CodeUsage.file_path == usage["file_path"],
                            CodeUsage.line_start == usage["line_start"],
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    cu = CodeUsage(
                        repo_id=repo_id,
                        detected_change_id=change.id,
                        file_path=usage["file_path"],
                        line_start=usage["line_start"],
                        line_end=usage["line_end"],
                        snippet=usage["snippet"],
                    )
                    session.add(cu)
                    new_usages.append(cu)
                    total_usages += 1

        # Flush so new_usages get their generated IDs assigned
        await session.flush()
        await session.commit()

        # Enqueue generate_patch only for newly created usages (avoids duplicates on rescan)
        for cu in new_usages:
            await enqueue_job(
                session,
                "generate_patch",
                {"code_usage_id": str(cu.id)},
            )

    logger.info(
        "scan_repo: found %d usages across %s for version %s",
        total_usages,
        repo_full_name,
        pv_version,
    )
