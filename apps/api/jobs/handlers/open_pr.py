"""
open_pr handler — bundles all verified patches for a repo+version into one PR.

Payload shape:
    { "repo_id": "<uuid>", "package_version_id": "<uuid>" }
    or: { "repo_id": "<uuid>", "code_usage_id": "<uuid>" }
"""

import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


def format_verification_disclosure(vr) -> str:
    """Derive accurate human-readable verification disclosure from actual validation run gates."""
    if not vr:
        return "[Warning] No verification run recorded for this patch."

    mode_display = getattr(vr, "verification_mode", None) or "structural_only"
    tests_pass = getattr(vr, "tests_pass", None)
    typechecks = getattr(vr, "typechecks", None)

    if mode_display == "full":
        if tests_pass is True and typechecks is True:
            return "[Verified] Repo's own test suite and type-checker both passed on this patch."
        elif tests_pass is True:
            return "[Verified] Repo's own test suite passed on this patch (type-check not run / not configured)."
        else:
            return "[Verified] Isolated sandbox verification passed on this patch."
    else:
        return "[Warning] No test suite detected in this repo — this patch was validated by parse and type-check only, not by running tests."


def build_classification_table(
    change_type: str,
    confidence: float,
    is_semantic_risk: bool,
    allow_install_scripts: bool = False,
    needs_review: bool = False,
) -> str:
    """Build the markdown Change Classification table for PR bodies."""
    risk_flag = (
        "[Warning] Possible semantic/behavior change — passing tests do not guarantee old behavior is preserved"
        if is_semantic_risk
        else "[Safe] Mechanical change"
    )
    install_scripts_str = "allowed (opt-in)" if allow_install_scripts else "blocked (default)"
    table = (
        "## Change classification\n"
        "| Field | Value |\n"
        "|---|---|\n"
        f"| Change type | {change_type} |\n"
        f"| Classifier confidence | {confidence:.0%} |\n"
        f"| Risk flag | {risk_flag} |\n"
        f"| Install scripts | {install_scripts_str} |\n"
    )
    if needs_review:
        table += "\n> [Review Required] Human review required before merge — see risk flag above.\n"
    return table


def build_pr_title(base_title: str, is_semantic_risk: bool) -> str:
    """Prefix PR title with [semantic-risk] if the change is flagged as a semantic risk."""
    if is_semantic_risk and not base_title.startswith("[semantic-risk]"):
        return f"[semantic-risk] {base_title}"
    return base_title


def build_pr_metadata(
    change_type: str,
    confidence: float,
    base_title: str = "chore(deps): auto-patch for my-lib@2.0",
    allow_install_scripts: bool = False,
    needs_review: bool = False,
    is_semantic_risk: bool | None = None,
) -> tuple[str, str]:
    """
    Combined production helper returning (title, classification_table).
    Used by open_pr.py and unit tests.
    """
    from services.change_extractor import classify_risk

    if is_semantic_risk is None:
        is_semantic_risk = classify_risk(change_type, confidence)
    title = build_pr_title(base_title, is_semantic_risk)
    table = build_classification_table(
        change_type=change_type,
        confidence=confidence,
        is_semantic_risk=is_semantic_risk,
        allow_install_scripts=allow_install_scripts,
        needs_review=needs_review,
    )
    return title, table


async def run(payload: dict) -> None:
    from sqlalchemy import select

    from db.models import (
        CodeUsage,
        DetectedChange,
        Installation,
        Package,
        PackageVersion,
        Patch,
        PullRequest,
        Repo,
    )
    from db.session import AsyncSessionLocal
    from services.change_extractor import classify_risk
    from services.github_service import create_check_run, get_installation_client, open_patch_pr

    repo_id = uuid.UUID(payload["repo_id"])
    pv_id_raw = payload.get("package_version_id")
    package_version_id = uuid.UUID(pv_id_raw) if pv_id_raw else None
    cu_id_raw = payload.get("code_usage_id")
    code_usage_id = uuid.UUID(cu_id_raw) if cu_id_raw else None

    if package_version_id is None and code_usage_id is None:
        logger.error("open_pr: both package_version_id and code_usage_id are missing")
        return

    async with AsyncSessionLocal() as session:
        repo = await session.get(Repo, repo_id)
        if repo is None:
            logger.error("open_pr: repo %s not found", repo_id)
            return

        # PackageVersion may be absent for Engine B escalations
        if package_version_id is not None:
            pv = await session.get(PackageVersion, package_version_id)
            if pv is None:
                logger.error("open_pr: version %s not found", package_version_id)
                return
            pkg = await session.get(Package, pv.package_id)
            pkg_name = pkg.name if pkg else "unknown"
            pv_version = pv.version
        else:
            pkg_name = "dependency"
            pv_version = "patch"

        installation = await session.get(Installation, repo.installation_id)
        if installation is None:
            logger.error("open_pr: installation missing for repo %s", repo_id)
            return

        # Read scalar values before session closes
        repo_full_name = repo.full_name
        repo_default_branch = repo.default_branch
        installation_github_id = installation.github_installation_id

        # Collect verified patches
        if package_version_id is not None:
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
        else:
            patches_result = await session.execute(
                select(Patch)
                .join(CodeUsage, Patch.code_usage_id == CodeUsage.id)
                .where(
                    CodeUsage.repo_id == repo_id,
                    CodeUsage.id == code_usage_id,
                    Patch.verified == True,
                )
            )
        patches = list(patches_result.scalars())

        if not patches:
            logger.info(
                "open_pr: no verified patches for repo %s (version=%s, usage=%s)",
                repo_id,
                package_version_id,
                code_usage_id,
            )
            return

        # Pre-load CodeUsage and ValidationRun rows
        usage_map: dict = {}
        vr_map: dict = {}
        from db.models import ValidationRun

        for p in patches:
            cu = await session.get(CodeUsage, p.code_usage_id)
            if cu:
                usage_map[p.id] = cu
            vr_res = await session.execute(
                select(ValidationRun)
                .where(ValidationRun.patch_id == p.id)
                .order_by(ValidationRun.created_at.desc())
                .limit(1)
            )
            vr = vr_res.scalar_one_or_none()
            if vr:
                vr_map[p.id] = vr

        # Pre-load detected changes for all code usages associated with these patches
        dc_map: dict[uuid.UUID, DetectedChange] = {}
        for cu in usage_map.values():
            if cu.detected_change_id and cu.detected_change_id not in dc_map:
                dc = await session.get(DetectedChange, cu.detected_change_id)
                if dc:
                    dc_map[cu.detected_change_id] = dc

    # ── PyGithub calls run in a thread — they are blocking I/O ───────────────
    gh = await asyncio.to_thread(get_installation_client, installation_github_id)
    gh_repo = await asyncio.to_thread(gh.get_repo, repo_full_name)

    from services.github_service import apply_diff_to_content, get_installation_client

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

        # Compute patched content by applying the validated diff
        apply_ok, new_content, apply_log = apply_diff_to_content(cu.file_path, original, p.diff)
        if not apply_ok:
            logger.warning("open_pr: could not apply diff to %s: %s", cu.file_path, apply_log)
            new_content = original

        cu_dc = dc_map.get(cu.detected_change_id) if cu.detected_change_id else None
        patch_dicts.append(
            {
                "file_path": cu.file_path,
                "new_content": new_content,
                "package_name": pkg_name,
                "new_version": pv_version,
                "diff": p.diff,
                "validation": vr_map.get(p.id),
                "detected_change": cu_dc,
            }
        )

    # Guard: don't open a no-op PR with zero patches collected
    if not patch_dicts:
        logger.warning(
            "open_pr: no patch content collected for repo %s — skipping PR",
            repo_id,
        )
        return

    # ── Derive aggregated classification signal across included patches ───────
    included_dcs = [pd.get("detected_change") for pd in patch_dicts]

    # If any included patch has no detected_change (unclassified) or triggers classify_risk, flag semantic risk
    is_semantic_risk = any(
        dc is None or classify_risk(dc.change_type, dc.confidence) for dc in included_dcs
    )

    known_dcs = [dc for dc in included_dcs if dc is not None]
    if known_dcs:
        distinct_types = sorted({dc.change_type for dc in known_dcs})
        dc_change_type = ", ".join(distinct_types)
        # Conservative aggregate: lowest confidence among included changes
        dc_confidence = min(dc.confidence for dc in known_dcs)
    else:
        dc_change_type = "unclassified"
        dc_confidence = 0.0

    # ── Aggregate test and typecheck evidence across all included patches ─────
    included_vrs = [pd.get("validation") for pd in patch_dicts]
    if any(vr is None for vr in included_vrs):
        _tests_passed = None
        _typecheck_passed = None
    else:
        valid_vrs = [vr for vr in included_vrs if vr is not None]
        if any(getattr(vr, "tests_pass", None) is False for vr in valid_vrs):
            _tests_passed = False
        elif any(getattr(vr, "tests_pass", None) is None for vr in valid_vrs):
            _tests_passed = None
        else:
            _tests_passed = True

        if any(getattr(vr, "typechecks", None) is False for vr in valid_vrs):
            _typecheck_passed = False
        elif any(getattr(vr, "typechecks", None) is None for vr in valid_vrs):
            _typecheck_passed = None
        else:
            _typecheck_passed = True

    from services.github_service import requires_human_review as _requires_human_review

    _needs_review = _requires_human_review(
        tests_passed=_tests_passed,
        typecheck_passed=_typecheck_passed,
        is_semantic_risk=is_semantic_risk,
        has_test_coverage_on_changed_symbol=False,
    )

    base_title = f"chore(deps): auto-patch for {pkg_name}@{pv_version}"
    repo_allow_scripts = getattr(repo, "allow_install_scripts", False) if repo else False

    pr_title, classification_table = build_pr_metadata(
        change_type=dc_change_type,
        confidence=dc_confidence,
        base_title=base_title,
        allow_install_scripts=repo_allow_scripts,
        needs_review=_needs_review,
        is_semantic_risk=is_semantic_risk,
    )

    body_lines = [
        f"## Telex Auto-Patch: `{pkg_name}` → `{pv_version}`\n",
        "Telex detected breaking API changes / runtime defects and generated the following patches.\n",
        "**Review each diff carefully before merging. Never auto-merge.**\n",
        classification_table,
    ]
    for i, pd in enumerate(patch_dicts, 1):
        vr = pd.get("validation")
        vr_evidence = []
        if vr:
            mode_display = getattr(vr, "verification_mode", None) or "structural_only"
            disclosure_text = format_verification_disclosure(vr)
            vr_evidence.append(f"- **Verification Status**: {disclosure_text}")
            vr_evidence.append(f"- **Verification Mode**: `{mode_display}`")
            vr_evidence.append(
                f"- **Applied Cleanly**: {'Passed' if vr.applies_cleanly else 'Failed'}"
            )
            if vr.typechecks is not None:
                vr_evidence.append(f"- **Typecheck**: {'Passed' if vr.typechecks else 'Failed'}")
            else:
                vr_evidence.append("- **Typecheck**: N/A (no config found)")
            if vr.tests_pass is not None:
                vr_evidence.append(
                    f"- **Automated Tests**: {'Passed' if vr.tests_pass else 'Failed'}"
                )
            else:
                vr_evidence.append("- **Automated Tests**: N/A (no test suite found)")

        body_lines.append(f"\n### Patch {i}: `{pd['file_path']}`\n")
        if vr_evidence:
            body_lines.append("**Verification Gate Evidence:**\n" + "\n".join(vr_evidence) + "\n")
        else:
            body_lines.append("**Verification Gate Evidence:** No verification run recorded.\n")
        body_lines.append(f"```diff\n{pd['diff']}\n```\n")

    summary = "\n".join(body_lines)

    # Include a short unique ID so concurrent defects don't collide on the same branch.
    unique_id_source = cu_id_raw or str(uuid.uuid4())
    short_id = unique_id_source.split("-")[0]  # e.g. "a3f2c1b8"
    branch_name = f"telex/{pkg_name}/{pv_version}/{short_id}"

    try:
        pr_url, pr_number = await open_patch_pr(
            repo_full_name=repo_full_name,
            installation_id=installation_github_id,
            branch_name=branch_name,
            patches=patch_dicts,
            summary=summary,
            title=pr_title,
            is_semantic_risk=is_semantic_risk,
            tests_passed=_tests_passed,
            typecheck_passed=_typecheck_passed,
            allow_install_scripts=repo_allow_scripts,
        )
    except Exception as exc:
        logger.error("open_pr: failed to open PR: %s", exc)
        return

    # ── Phase 8.4: create Telex Validation Check Run ──────────────────────────
    # Determine the head commit SHA from the PR branch so the check run appears
    # in the PR's "Checks" tab alongside the repo's own CI.
    try:
        import asyncio as _asyncio

        def _get_head_sha():
            gh = get_installation_client(installation_github_id)
            repo_obj = gh.get_repo(repo_full_name)
            branch_ref = repo_obj.get_branch(branch_name)
            return branch_ref.commit.sha

        head_sha = await _asyncio.to_thread(_get_head_sha)

        # Aggregate validations for all included patches (Comment 7 fix)
        has_failure = False
        has_missing = False
        summary_rows = []

        for idx, pd in enumerate(patch_dicts, 1):
            vr = pd.get("validation")
            fpath = pd.get("file_path", f"patch #{idx}")
            if vr is None:
                has_missing = True
                summary_rows.append(f"- `{fpath}`: no validation run recorded (neutral)")
                continue

            gate_passed = (
                bool(vr.applies_cleanly)
                and bool(vr.parses)
                and bool(vr.scope_ok)
                and (vr.tests_pass is not False)
                and (vr.typechecks is not False)
            )
            if not gate_passed:
                has_failure = True
                summary_rows.append(
                    f"- `{fpath}`: failed gate (applies={vr.applies_cleanly}, parses={vr.parses}, "
                    f"scope={vr.scope_ok}, tests={vr.tests_pass}, types={vr.typechecks})"
                )
            else:
                mode_lbl = getattr(vr, "verification_mode", None) or "structural_only"
                summary_rows.append(f"- `{fpath}`: passed all gates (mode: `{mode_lbl}`)")

        if has_failure:
            check_conclusion = "failure"
            check_title = "Telex: patch verification failed"
        elif has_missing:
            check_conclusion = "neutral"
            check_title = "Telex: verification incomplete (missing validation run)"
        else:
            check_conclusion = "success"
            check_title = f"Telex: all {len(patch_dicts)} patch(es) verified (all gates passed)"

        check_summary = "\n".join(summary_rows)

        await create_check_run(
            repo_full_name=repo_full_name,
            installation_id=installation_github_id,
            head_sha=head_sha,
            name="Telex Validation",
            conclusion=check_conclusion,
            title=check_title,
            summary=check_summary,
        )
    except Exception as check_exc:
        # Non-fatal — log and continue; the PR has already been opened
        logger.warning("open_pr: could not create Check Run for PR #%d: %s", pr_number, check_exc)

    # Record the PR in the database
    async with AsyncSessionLocal() as session:
        pr = PullRequest(
            repo_id=repo_id,
            package_version_id=package_version_id,
            github_pr_number=pr_number,
            github_pr_url=pr_url,
            patch_ids=[p.id for p in patches],
        )
        session.add(pr)

        # Record pr_opened event (rides the same insert transaction)
        from services.incident_events import record_event
        await record_event(
            session,
            event_type="pr_opened",
            repo_id=repo_id,
            payload={
                "github_pr_url": pr_url,
                "github_pr_number": pr_number,
            },
        )

        await session.commit()

    # Publish after commit — non-fatal
    try:
        from services.event_bus import event_bus
        await event_bus.publish({
            "event_type": "pr_opened",
            "repo_id": str(repo_id),
            "github_pr_url": pr_url,
            "github_pr_number": pr_number,
        })
    except Exception as exc:
        logger.warning("event_bus publish pr_opened failed (non-fatal): %s", exc)

    logger.info("open_pr: opened PR #%d on %s (%s)", pr_number, repo_full_name, pr_url)
