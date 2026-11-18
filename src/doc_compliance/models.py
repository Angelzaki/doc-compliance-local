from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PASS = "pass"
PARTIAL = "partial"
FAIL = "fail"
STATUSES = (PASS, PARTIAL, FAIL)


@dataclass(frozen=True)
class Requirement:
    id: str
    title: str
    keywords: tuple[str, ...]
    must_have: tuple[str, ...]
    description: str = ""
    critical: bool = False
    weight: float = 1.0
    category: str = ""


@dataclass(frozen=True)
class Checklist:
    name: str
    version: str
    requirements: tuple[Requirement, ...]
    source: str = ""

    def get(self, req_id: str) -> Requirement | None:
        for req in self.requirements:
            if req.id == req_id:
                return req
        return None


@dataclass(frozen=True)
class Document:
    name: str
    text: str
    path: str = ""


@dataclass(frozen=True)
class Evidence:
    doc: str
    start: int
    end: int
    quote: str
    matched_keywords: tuple[str, ...]
    matched_must_have: tuple[str, ...]
    negated: bool = False
    score: float = 0.0

    @property
    def citation(self) -> str:
        return f"{self.doc}:{self.start}-{self.end}"


@dataclass
class RequirementResult:
    requirement: Requirement
    status: str
    score: float
    keyword_coverage: float
    must_have_coverage: float
    evidence: list[Evidence] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    missing_must_have: list[str] = field(default_factory=list)
    negated_must_have: list[str] = field(default_factory=list)

    @property
    def is_gap(self) -> bool:
        return self.status != PASS


@dataclass
class ComplianceRun:
    checklist_name: str
    checklist_version: str
    documents: list[str]
    results: list[RequirementResult]
    overall_pct: float
    verdict: str
    counts: dict[str, int]
    critical_gaps: list[str]
    label: str = ""
    created_at: str = ""

    def result_for(self, req_id: str) -> RequirementResult | None:
        for res in self.results:
            if res.requirement.id == req_id:
                return res
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "created_at": self.created_at,
            "checklist": {"name": self.checklist_name, "version": self.checklist_version},
            "documents": self.documents,
            "overall_pct": self.overall_pct,
            "verdict": self.verdict,
            "counts": self.counts,
            "critical_gaps": self.critical_gaps,
            "requirements": [_result_to_dict(r) for r in self.results],
        }


def _result_to_dict(res: RequirementResult) -> dict[str, Any]:
    req = res.requirement
    return {
        "id": req.id,
        "title": req.title,
        "category": req.category,
        "critical": req.critical,
        "weight": req.weight,
        "status": res.status,
        "score": round(res.score, 4),
        "keyword_coverage": round(res.keyword_coverage, 4),
        "must_have_coverage": round(res.must_have_coverage, 4),
        "missing_keywords": res.missing_keywords,
        "missing_must_have": res.missing_must_have,
        "negated_must_have": res.negated_must_have,
        "evidence": [
            {**asdict(ev), "citation": ev.citation, "score": round(ev.score, 4)}
            for ev in res.evidence
        ],
    }
