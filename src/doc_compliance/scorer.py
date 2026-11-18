from __future__ import annotations

from datetime import datetime, timezone

from doc_compliance.evidence import EvidenceReport, PreparedDoc, collect_evidence, prepare
from doc_compliance.models import (
    FAIL,
    PARTIAL,
    PASS,
    Checklist,
    ComplianceRun,
    Document,
    Requirement,
    RequirementResult,
)

MUST_WEIGHT = 0.65
KEYWORD_WEIGHT = 0.35
PASS_KEYWORD_MIN = 0.5
PASS_KEYWORD_ONLY_MIN = 0.75
FAIL_BELOW = 0.35
COMPLIANT_PCT = 80.0
NON_COMPLIANT_PCT = 60.0


def _coverage(found: int, total: int) -> float:
    return found / total if total else 1.0


def score_requirement(req: Requirement, rep: EvidenceReport) -> RequirementResult:
    kw_cov = _coverage(len(rep.keywords_found), len(req.keywords))
    must_cov = _coverage(len(rep.must_found), len(req.must_have))
    if req.must_have and req.keywords:
        score = MUST_WEIGHT * must_cov + KEYWORD_WEIGHT * kw_cov
        passed = must_cov == 1.0 and kw_cov >= PASS_KEYWORD_MIN
    elif req.must_have:
        score = must_cov
        passed = must_cov == 1.0
    else:
        score = kw_cov
        passed = kw_cov >= PASS_KEYWORD_ONLY_MIN

    if passed:
        status = PASS
    elif score < FAIL_BELOW:
        status = FAIL
    else:
        status = PARTIAL

    return RequirementResult(
        requirement=req,
        status=status,
        score=score,
        keyword_coverage=kw_cov,
        must_have_coverage=must_cov,
        evidence=rep.evidence,
        missing_keywords=rep.keywords_missing,
        missing_must_have=rep.must_missing,
        negated_must_have=rep.must_negated,
    )


def overall_percentage(results: list[RequirementResult]) -> float:
    total = sum(r.requirement.weight for r in results)
    if total == 0:
        return 0.0
    return 100.0 * sum(r.requirement.weight * r.score for r in results) / total


def critical_gaps(results: list[RequirementResult]) -> list[str]:
    return [r.requirement.id for r in results if r.requirement.critical and r.status != PASS]


def verdict_for(pct: float, results: list[RequirementResult]) -> str:
    critical_fail = any(r.requirement.critical and r.status == FAIL for r in results)
    if critical_fail or pct < NON_COMPLIANT_PCT:
        return "non_compliant"
    if pct >= COMPLIANT_PCT and not critical_gaps(results):
        return "compliant"
    return "needs_work"


def run_check(
    checklist: Checklist,
    docs: list[Document],
    max_evidence: int = 3,
    label: str = "",
) -> ComplianceRun:
    prepared: list[PreparedDoc] = prepare(docs)
    results = [
        score_requirement(req, collect_evidence(req, prepared, max_evidence))
        for req in checklist.requirements
    ]
    pct = round(overall_percentage(results), 2)
    counts = {s: sum(1 for r in results if r.status == s) for s in (PASS, PARTIAL, FAIL)}
    return ComplianceRun(
        checklist_name=checklist.name,
        checklist_version=checklist.version,
        documents=[d.name for d in docs],
        results=results,
        overall_pct=pct,
        verdict=verdict_for(pct, results),
        counts=counts,
        critical_gaps=critical_gaps(results),
        label=label,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
