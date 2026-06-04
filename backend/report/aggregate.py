"""Pure aggregation helpers for the Reports page (4a).

Kept free of Streamlit so they are unit-testable on plain suite dicts.
"""

from __future__ import annotations


def pass_rate(suite: dict) -> float:
    """Fraction of calls that passed: ``n_passed / n_total``.

    Returns ``0.0`` when there are no calls (no ZeroDivisionError).
    """
    total = suite.get("n_total") or 0
    if not total:
        return 0.0
    return (suite.get("n_passed") or 0) / total


def per_criterion_averages(suite: dict) -> dict[str, float]:
    """Mean ``score`` per criterion ``name`` across all scored calls.

    Calls with no ``text_verdict`` are skipped (not counted as 0). A criterion
    that appears in only some calls is averaged over the calls where it is
    present.
    """
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for call in suite.get("calls", []):
        verdict = call.get("text_verdict")
        if not verdict:
            continue
        for criterion in verdict.get("criteria", []):
            name = criterion.get("name")
            score = criterion.get("score")
            if name is None or score is None:
                continue
            sums[name] = sums.get(name, 0.0) + score
            counts[name] = counts.get(name, 0) + 1
    return {name: sums[name] / counts[name] for name in sums}
