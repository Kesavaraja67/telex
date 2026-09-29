"""
analysis_weights.py — Single source of truth for architectural risk scoring (Phase 4).

Principle: Score is computed from verified facts. LLM only writes prose about those facts.
Weights and rules defined in docs/specs/skeuo-atlas-analysis.md Section 4B.
"""

from collections.abc import Mapping

WEIGHT_STRUCTURE = 0.30
WEIGHT_DEPENDENCY = 0.30
WEIGHT_CHANGE_SAFETY = 0.25
WEIGHT_VERIFICATION = 0.15

WEIGHTS_BY_CATEGORY: dict[str, float] = {
    "structure": WEIGHT_STRUCTURE,
    "dependency": WEIGHT_DEPENDENCY,
    "change_safety": WEIGHT_CHANGE_SAFETY,
    "verification": WEIGHT_VERIFICATION,
}


def clamp_score(val: float, min_val: int = 0, max_val: int = 100) -> int:
    return max(min_val, min(max_val, round(val)))


def compute_structure_score(
    cycles_count: int,
    hub_files_count: int,
    orphan_ratio: float,
    has_unresolved_imports: bool,
    node_count: int,
) -> int | None:
    """
    Sub-score factors:
    - Base: 90
    - -10 per cycle (max penalty 50)
    - -5 per hub file (fan-in > 30)
    - -3 per 10% orphan ratio (orphan_ratio * 10 * 3)
    - +10 if no unresolved internal imports
    """
    if node_count == 0:
        return None

    score = 90.0
    score -= min(50.0, cycles_count * 10.0)
    score -= hub_files_count * 5.0
    score -= (orphan_ratio / 0.10) * 3.0
    if not has_unresolved_imports:
        score += 10.0

    return clamp_score(score)


def compute_dependency_score(
    breaking_pkgs_count: int,
    outdated_pkgs_count: int,
    total_dependencies: int,
) -> int | None:
    """
    Sub-score factors:
    - Base: 100
    - -20 per package with breaking change
    - -5 per package behind major version
    """
    if total_dependencies == 0 and breaking_pkgs_count == 0:
        # No dependency information tracked
        return None

    score = 100.0
    score -= breaking_pkgs_count * 20.0
    score -= outdated_pkgs_count * 5.0
    return clamp_score(score)


def compute_change_safety_score(
    has_tests: bool,
    has_ci: bool,
    high_churn_hubs_count: int,
    signals_available: bool = True,
) -> int | None:
    """
    Sub-score factors:
    - Base: 100
    - -15 if no tests found
    - -10 if no CI workflow found
    - -5 per high-churn hub file
    """
    if not signals_available:
        return None

    score = 100.0
    if not has_tests:
        score -= 15.0
    if not has_ci:
        score -= 10.0
    score -= high_churn_hubs_count * 5.0

    return clamp_score(score)


def compute_verification_score(
    merge_rate: float | None,
    pass_rate: float | None,
    open_review_prs_count: int,
    total_patches_evaluated: int,
) -> int | None:
    """
    Sub-score factors:
    - Base: 70
    - +20 if merge_rate > 0.8
    - +15 if pass_rate > 0.9
    - -10 if > 3 open human-review PRs
    """
    if total_patches_evaluated == 0 and merge_rate is None and pass_rate is None:
        return None

    score = 70.0
    if merge_rate is not None and merge_rate > 0.8:
        score += 20.0
    if pass_rate is not None and pass_rate > 0.9:
        score += 15.0
    if open_review_prs_count > 3:
        score -= 10.0

    return clamp_score(score)


def compute_composite_score(sub_scores: Mapping[str, int | None]) -> int:
    """
    Computes overall score (0-100) as a weighted average over available (non-null) sub-scores.
    If all sub-scores are null, defaults to a neutral baseline of 75.
    """
    available_weighted_sum = 0.0
    total_weight = 0.0

    for category, weight in WEIGHTS_BY_CATEGORY.items():
        val = sub_scores.get(category)
        if val is not None:
            available_weighted_sum += val * weight
            total_weight += weight

    if total_weight <= 0:
        return 75

    normalized_score = available_weighted_sum / total_weight
    return clamp_score(normalized_score)
