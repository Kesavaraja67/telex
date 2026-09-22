"""
Repos API — list live repositories, commit history, and Gemini 2.5 Flash architecture insights.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import Text, cast, or_, select

from db.models import CodeUsage, DetectedChange, Patch, PullRequest, Repo, ValidationRun
from db.session import AsyncSessionLocal
from routers.auth import require_auth
from schemas import (
    AIExplainOut,
    PatchOut,
    RepoDetailOut,
    RepoOut,
    RepoPatchesOut,
    RepoToggleIn,
    RepoUpdateIn,
)
from services.change_extractor import classify_risk
from services.repo_service import (
    explain_repo_with_gemini,
    get_core_repositories_async,
    sync_github_app_repositories_async,
)

router = APIRouter(prefix="/api/repos", tags=["repos"])


@router.post("/sync", response_model=list[RepoOut])
@router.get("/sync", response_model=list[RepoOut])
async def sync_repos(
    request: Request,
    include_benchmarks: bool = False,
    auth_data: dict = Depends(require_auth),
):
    """Immediately syncs repositories from GitHub App installations and returns the active repos."""
    user_id = auth_data.get("user_id") if isinstance(auth_data, dict) else None
    await sync_github_app_repositories_async(user_id=user_id)
    repos = await get_core_repositories_async(
        force_sync=True, include_benchmarks=include_benchmarks, user_id=user_id
    )
    return repos


@router.get("", response_model=list[RepoOut])
async def list_repos(
    request: Request,
    sync: bool = False,
    include_benchmarks: bool = False,
):
    """Return all active monitored repositories with live git commit metadata."""
    user_id = None
    try:
        auth_data = await require_auth(request)
        if isinstance(auth_data, dict):
            user_id = auth_data.get("user_id")
    except Exception:
        pass

    repos = await get_core_repositories_async(
        force_sync=sync, include_benchmarks=include_benchmarks, user_id=user_id
    )
    return repos


@router.get("/{repo_id}", response_model=RepoDetailOut)
async def get_repo_details(repo_id: str):
    """Return full repository detail with full recent commit history."""
    repos = await get_core_repositories_async(include_benchmarks=True)
    repo = next(
        (
            r
            for r in repos
            if r["id"] == repo_id or r["full_name"] == repo_id or r["name"] == repo_id
        ),
        None,
    )
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    return repo


@router.post("/{repo_id}/ai-explain", response_model=AIExplainOut)
async def ai_explain_repo(repo_id: str):
    """Invoke Gemini 2.5 Flash to generate live architectural and commit analysis."""
    try:
        explanation = await explain_repo_with_gemini(repo_id)
        return explanation
    except KeyError:
        raise HTTPException(status_code=404, detail="Repo not found")


@router.post("/{repo_id}/toggle", response_model=dict, dependencies=[Depends(require_auth)])
async def toggle_repo(repo_id: str, body: RepoToggleIn):
    """Toggle monitoring state for a repository."""
    repos = await get_core_repositories_async()
    repo = next(
        (
            r
            for r in repos
            if r["id"] == repo_id or r["full_name"] == repo_id or r["name"] == repo_id
        ),
        None,
    )
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    repo["is_active"] = body.is_active

    # Persist in DB if repository record exists
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Repo).where(Repo.full_name == repo["full_name"]).limit(1)
        )
        db_repo = result.scalar_one_or_none()
        if db_repo:
            db_repo.is_active = body.is_active
            await session.commit()

    return {"id": repo_id, "is_active": body.is_active}


@router.patch("/{repo_id}", response_model=dict, dependencies=[Depends(require_auth)])
async def update_repo_settings(repo_id: str, body: RepoUpdateIn):
    """Update repo verification policy (requires_tests, requires_typecheck) or monitoring status."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Repo)
            .where(
                or_(
                    cast(Repo.id, Text) == repo_id,
                    Repo.full_name == repo_id,
                )
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        repo = result.scalar_one_or_none()
        if not repo:
            raise HTTPException(status_code=404, detail="Repo not found")

        if body.requires_tests is not None:
            repo.requires_tests = body.requires_tests
        if body.requires_typecheck is not None:
            repo.requires_typecheck = body.requires_typecheck
        if body.is_active is not None:
            repo.is_active = body.is_active
        if body.allow_install_scripts is not None:
            repo.allow_install_scripts = body.allow_install_scripts

        await session.commit()
        return {
            "id": str(repo.id),
            "full_name": repo.full_name,
            "requires_tests": repo.requires_tests,
            "requires_typecheck": repo.requires_typecheck,
            "is_active": repo.is_active,
            "allow_install_scripts": repo.allow_install_scripts,
        }


@router.get("/{repo_id}/patches", response_model=RepoPatchesOut)
async def list_patches(repo_id: str):
    """Return recent patches for repository from real DB records (P1-8)."""
    repos = await get_core_repositories_async()
    repo = next(
        (
            r
            for r in repos
            if r["id"] == repo_id or r["full_name"] == repo_id or r["name"] == repo_id
        ),
        None,
    )
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo not found")
    repo_name = repo["full_name"]

    patches_out: list[PatchOut] = []
    async with AsyncSessionLocal() as session:
        # Find DB repo row by full_name or id
        repo_res = await session.execute(
            select(Repo)
            .where(
                or_(
                    Repo.full_name == repo_name,
                    cast(Repo.id, Text) == repo_id,
                )
            )
            .limit(1)
        )
        db_repo = repo_res.scalar_one_or_none()

        if db_repo:
            stmt = (
                select(Patch, CodeUsage)
                .join(CodeUsage, Patch.code_usage_id == CodeUsage.id)
                .where(CodeUsage.repo_id == db_repo.id)
                .order_by(Patch.created_at.desc())
                .limit(20)
            )
            res = await session.execute(stmt)
            pairs = res.all()

            if pairs:
                patch_ids = [p.id for p, _ in pairs]
                dc_ids = [cu.detected_change_id for _, cu in pairs if cu.detected_change_id]

                # 1. Batch PRs
                pr_res = await session.execute(
                    select(PullRequest).where(PullRequest.repo_id == db_repo.id)
                )
                pr_rows = pr_res.scalars().all()
                pr_map = {}
                for pr in pr_rows:
                    for pid in pr.patch_ids or []:
                        pr_map[pid] = pr

                # 2. Batch ValidationRuns
                vr_res = await session.execute(
                    select(ValidationRun)
                    .where(ValidationRun.patch_id.in_(patch_ids))
                    .order_by(ValidationRun.created_at.desc())
                )
                vr_map = {}
                for vr in vr_res.scalars().all():
                    if vr.patch_id not in vr_map:
                        vr_map[vr.patch_id] = vr

                # 3. Batch DetectedChanges
                dc_map = {}
                if dc_ids:
                    dc_res = await session.execute(
                        select(DetectedChange).where(DetectedChange.id.in_(dc_ids))
                    )
                    for dc in dc_res.scalars().all():
                        dc_map[dc.id] = dc

                for patch_row, cu_row in pairs:
                    pr_row = pr_map.get(patch_row.id)
                    vr_row = vr_map.get(patch_row.id)
                    dc_row = dc_map.get(cu_row.detected_change_id)

                    patches_out.append(
                        PatchOut(
                            id=str(patch_row.id),
                            package=cu_row.file_path,
                            old_version="current",
                            new_version="patched",
                            status="verified" if patch_row.verified else "generated",
                            pr_url=(
                                pr_row.github_pr_url
                                if pr_row
                                else f"https://github.com/{repo_name}"
                            ),
                            usages_patched=1,
                            opened_at=(
                                patch_row.created_at
                                if patch_row.created_at
                                else datetime.now(timezone.utc)
                            ),
                            diff=patch_row.diff,
                            verification_mode=(
                                vr_row.verification_mode if vr_row else "structural_only"
                            ),
                            tests_passed=vr_row.tests_pass if vr_row else None,
                            typecheck_passed=vr_row.typechecks if vr_row else None,
                            change_type=dc_row.change_type if dc_row else None,
                            change_description=dc_row.description if dc_row else None,
                            confidence=dc_row.confidence if dc_row else None,
                            is_semantic_risk=(
                                classify_risk(dc_row.change_type, dc_row.confidence)
                                if dc_row
                                else None
                            ),
                        )
                    )

    return RepoPatchesOut(
        repo=repo_name,
        patches=patches_out,
    )
