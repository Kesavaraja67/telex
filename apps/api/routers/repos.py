"""
Repos API — list live repositories, commit history, and Gemini 2.5 Flash architecture insights.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select

from db.models import (
    CodeUsage,
    DetectedChange,
    Patch,
    PullRequest,
    Repo,
    RepoAnalysisRun,
    ValidationRun,
)
from db.session import AsyncSessionLocal
from routers.auth import get_authorized_repo, require_auth
from schemas import (
    AIExplainOut,
    PatchOut,
    RepoAnalysisHistoryOut,
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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/repos", tags=["repos"])

# In-memory rate limiter cooldown for AI explanation: (user_id, repo_id) -> timestamp
_AI_EXPLAIN_COOLDOWN: dict[tuple[str, str], float] = {}


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
    auth_data = await require_auth(request)
    user_id = auth_data.get("user_id") if isinstance(auth_data, dict) else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    repos = await get_core_repositories_async(
        force_sync=sync, include_benchmarks=include_benchmarks, user_id=user_id
    )
    return repos


@router.get("/{repo_id}", response_model=RepoDetailOut)
async def get_repo_details(
    repo_id: str,
    auth_data: dict = Depends(require_auth),
):
    """Return full repository detail with full recent commit history."""
    async with AsyncSessionLocal() as session:
        db_repo, _ = await get_authorized_repo(session, repo_id, auth_data)

    user_id = auth_data.get("user_id") if isinstance(auth_data, dict) else None
    try:
        repos = await asyncio.wait_for(
            get_core_repositories_async(include_benchmarks=True, user_id=user_id),
            timeout=4.0,
        )
    except Exception as exc:
        logger.warning(
            "get_core_repositories_async timed out or failed in get_repo_details: %s", exc
        )
        repos = []
    repo = next(
        (
            r
            for r in repos
            if r["id"] == str(db_repo.id)
            or r["full_name"] == db_repo.full_name
            or r.get("name") == db_repo.full_name.split("/")[-1]
        ),
        None,
    )
    if repo is None:
        repo = {
            "id": str(db_repo.id),
            "full_name": db_repo.full_name,
            "name": (
                db_repo.full_name.split("/")[-1] if "/" in db_repo.full_name else db_repo.full_name
            ),
            "owner": (db_repo.full_name.split("/")[0] if "/" in db_repo.full_name else "owner"),
            "description": None,
            "default_branch": db_repo.default_branch,
            "is_active": db_repo.is_active,
            "requires_tests": db_repo.requires_tests,
            "requires_typecheck": db_repo.requires_typecheck,
            "allow_install_scripts": db_repo.allow_install_scripts,
            "created_at": db_repo.created_at or datetime.now(timezone.utc),
            "github_url": f"https://github.com/{db_repo.full_name}",
            "languages": [],
            "patch_count": 0,
            "status": "healthy",
            "commits": [],
            "dependencies": [],
        }
    return repo


@router.post("/{repo_id}/ai-explain", response_model=AIExplainOut)
async def ai_explain_repo(
    repo_id: str,
    auth_data: dict = Depends(require_auth),
):
    """Invoke Gemini 2.5 Flash to generate live architectural and commit analysis."""
    async with AsyncSessionLocal() as session:
        db_repo, _ = await get_authorized_repo(session, repo_id, auth_data)
        repo_target = db_repo.full_name

    user_id = str(auth_data.get("user_id", "anon"))
    now = time.time()

    # Evict expired entries older than the 10-second cooldown window
    cutoff = now - 10.0
    for k in list(_AI_EXPLAIN_COOLDOWN.keys()):
        if _AI_EXPLAIN_COOLDOWN[k] < cutoff:
            _AI_EXPLAIN_COOLDOWN.pop(k, None)

    last_req = _AI_EXPLAIN_COOLDOWN.get((user_id, str(db_repo.id)), 0)
    if now - last_req < 10.0:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a few seconds before requesting another AI explanation.",
        )
    _AI_EXPLAIN_COOLDOWN[(user_id, str(db_repo.id))] = now

    try:
        from services.repo_analysis import run_repo_analysis

        return await run_repo_analysis(db_repo.id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Repo not found")
    except Exception as exc:
        logger.warning("run_repo_analysis failed: %s; trying fallback", exc)
        try:
            explanation = await explain_repo_with_gemini(repo_target)
            return explanation
        except KeyError:
            raise HTTPException(status_code=404, detail="Repo not found")
        except Exception:
            raise HTTPException(status_code=502, detail="Failed to generate AI explanation")


@router.get("/{repo_id}/analysis", response_model=RepoAnalysisHistoryOut)
async def get_repo_analysis(
    repo_id: str,
    auth_data: dict = Depends(require_auth),
):
    """Retrieve latest and previous evidence-based analysis runs for a repository."""
    async with AsyncSessionLocal() as session:
        db_repo, _ = await get_authorized_repo(session, repo_id, auth_data)

        runs_res = await session.execute(
            select(RepoAnalysisRun)
            .where(RepoAnalysisRun.repo_id == db_repo.id)
            .order_by(RepoAnalysisRun.created_at.desc())
            .limit(2)
        )
        runs = runs_res.scalars().all()

        if not runs:
            return {"latest": None, "previous": None, "delta_score": 0}

        latest = runs[0]
        prev = runs[1] if len(runs) > 1 else None
        delta = (latest.score - prev.score) if prev else 0

        latest_created_str = (
            latest.created_at.isoformat()
            if getattr(latest, "created_at", None)
            else datetime.now(timezone.utc).isoformat()
        )
        prev_created_str = (
            prev.created_at.isoformat()
            if prev and getattr(prev, "created_at", None)
            else (datetime.now(timezone.utc).isoformat() if prev else None)
        )

        latest_dict = {
            "id": str(latest.id),
            "repo_id": str(latest.repo_id),
            "head_sha": latest.head_sha,
            "score": latest.score,
            "sub_scores": latest.sub_scores,
            "findings": latest.findings,
            "signals": latest.signals,
            "executive_summary": latest.executive_summary,
            "do_this_first": latest.do_this_first,
            "created_at": latest_created_str,
        }
        prev_dict = (
            {
                "id": str(prev.id),
                "head_sha": prev.head_sha,
                "score": prev.score,
                "created_at": prev_created_str,
            }
            if prev
            else None
        )

        return {
            "latest": latest_dict,
            "previous": prev_dict,
            "delta_score": delta,
        }


@router.post("/{repo_id}/toggle", response_model=dict)
async def toggle_repo(
    repo_id: str,
    body: RepoToggleIn,
    auth_data: dict = Depends(require_auth),
):
    """Toggle monitoring state for an authorized repository."""
    async with AsyncSessionLocal() as session:
        db_repo, _ = await get_authorized_repo(session, repo_id, auth_data)
        db_repo.is_active = body.is_active
        await session.commit()
        return {"id": str(db_repo.id), "is_active": body.is_active}


@router.patch("/{repo_id}", response_model=dict)
async def update_repo_settings(
    repo_id: str,
    body: RepoUpdateIn,
    auth_data: dict = Depends(require_auth),
):
    """Update repo verification policy (requires_tests, requires_typecheck) or monitoring status."""
    async with AsyncSessionLocal() as session:
        db_repo, _ = await get_authorized_repo(session, repo_id, auth_data)

        if body.requires_tests is not None:
            db_repo.requires_tests = body.requires_tests
        if body.requires_typecheck is not None:
            db_repo.requires_typecheck = body.requires_typecheck
        if body.is_active is not None:
            db_repo.is_active = body.is_active
        if body.allow_install_scripts is not None:
            db_repo.allow_install_scripts = body.allow_install_scripts

        await session.commit()
        return {
            "id": str(db_repo.id),
            "full_name": db_repo.full_name,
            "requires_tests": db_repo.requires_tests,
            "requires_typecheck": db_repo.requires_typecheck,
            "is_active": db_repo.is_active,
            "allow_install_scripts": db_repo.allow_install_scripts,
        }


@router.get("/digest/human-review")
async def get_human_review_digest(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    auth_data: dict = Depends(require_auth),
):
    """
    Weekly summary / digest of open PRs requiring human review across all accessible repos (ISSUE-4).
    """
    async with AsyncSessionLocal() as session:
        from routers.stats import _accessible_repo_ids

        repo_ids = await _accessible_repo_ids(session, auth_data)
        if not repo_ids:
            return {"open_review_prs": [], "total": 0, "page": page, "page_size": page_size}

        total_stmt = select(func.count(PullRequest.id)).where(
            PullRequest.repo_id.in_(repo_ids),
            PullRequest.status == "open",
        )
        total_res = await session.execute(total_stmt)
        raw_total = total_res.scalar() if hasattr(total_res, "scalar") else None
        total = raw_total if isinstance(raw_total, int) else None

        pr_stmt = (
            select(PullRequest, Repo)
            .join(Repo, PullRequest.repo_id == Repo.id)
            .where(
                PullRequest.repo_id.in_(repo_ids),
                PullRequest.status == "open",
            )
            .order_by(PullRequest.opened_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        pr_res = await session.execute(pr_stmt)
        rows = pr_res.all()

        digest_items = []
        for pr, repo in rows:
            digest_items.append(
                {
                    "pr_id": str(pr.id),
                    "repo_name": repo.full_name,
                    "github_pr_number": pr.github_pr_number,
                    "github_pr_url": pr.github_pr_url,
                    "opened_at": pr.opened_at.isoformat() if pr.opened_at else None,
                    "status": pr.status,
                }
            )

        return {
            "open_review_prs": digest_items,
            "total": total if total is not None else len(digest_items),
            "page": page,
            "page_size": page_size,
        }


@router.get("/{repo_id}/patches", response_model=RepoPatchesOut)
async def list_patches(
    repo_id: str,
    risk: str | None = None,
    sort_by: str | None = None,
    auth_data: dict = Depends(require_auth),
):
    """Return recent patches for repository from real DB records (P1-8)."""
    import re

    async with AsyncSessionLocal() as session:
        db_repo, _ = await get_authorized_repo(session, repo_id, auth_data)
        repo_name = db_repo.full_name

        patches_out: list[PatchOut] = []
        semantic_cond = or_(
            DetectedChange.change_type == "behavior_change",
            and_(
                DetectedChange.change_type.in_(["signature_change", "deprecated"]),
                DetectedChange.confidence < 0.75,
            ),
        )
        mechanical_cond = or_(
            DetectedChange.change_type.in_(["removed", "renamed"]),
            and_(
                DetectedChange.change_type.in_(["signature_change", "deprecated"]),
                DetectedChange.confidence >= 0.75,
            ),
        )

        stmt = (
            select(Patch, CodeUsage)
            .join(CodeUsage, Patch.code_usage_id == CodeUsage.id)
            .where(CodeUsage.repo_id == db_repo.id)
        )
        if risk or sort_by:
            stmt = stmt.outerjoin(DetectedChange, CodeUsage.detected_change_id == DetectedChange.id)
            if risk == "semantic_only":
                stmt = stmt.where(semantic_cond)
            elif risk == "mechanical_only":
                stmt = stmt.where(mechanical_cond)

            if sort_by == "risk_first":
                stmt = stmt.order_by(semantic_cond.desc(), Patch.created_at.desc())
            elif sort_by == "confidence_asc":
                stmt = stmt.order_by(DetectedChange.confidence.asc(), Patch.created_at.desc())
            elif sort_by == "confidence_desc":
                stmt = stmt.order_by(DetectedChange.confidence.desc(), Patch.created_at.desc())
            else:
                stmt = stmt.order_by(Patch.created_at.desc())
        else:
            stmt = stmt.order_by(Patch.created_at.desc())

        stmt = stmt.limit(20)
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

                is_risk = classify_risk(dc_row.change_type, dc_row.confidence) if dc_row else None

                if risk == "semantic_only" and not is_risk:
                    continue
                if risk == "mechanical_only" and is_risk is not False:
                    continue

                base_sha = None
                commit_sha = None
                if vr_row and vr_row.log:
                    m_base = re.search(r"\[base_sha:([a-f0-9]+)\]", vr_row.log)
                    if m_base:
                        base_sha = m_base.group(1)
                    m_commit = re.search(r"\[commit_sha:([a-f0-9]+)\]", vr_row.log)
                    if m_commit:
                        commit_sha = m_commit.group(1)

                patches_out.append(
                    PatchOut(
                        id=str(patch_row.id),
                        package=cu_row.file_path,
                        old_version="current",
                        new_version="patched",
                        status="verified" if patch_row.verified else "generated",
                        pr_url=(
                            pr_row.github_pr_url if pr_row else f"https://github.com/{repo_name}"
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
                        is_semantic_risk=is_risk,
                        base_sha=base_sha,
                        commit_sha=commit_sha,
                    )
                )

        if sort_by == "risk_first":
            patches_out.sort(
                key=lambda p: (0 if p.is_semantic_risk else 1, -p.opened_at.timestamp())
            )
        elif sort_by == "confidence_asc":
            patches_out.sort(key=lambda p: (p.confidence if p.confidence is not None else 1.0))
        elif sort_by == "confidence_desc":
            patches_out.sort(key=lambda p: (-(p.confidence if p.confidence is not None else 0.0)))

        return RepoPatchesOut(
            repo=repo_name,
            patches=patches_out[:20],
        )
