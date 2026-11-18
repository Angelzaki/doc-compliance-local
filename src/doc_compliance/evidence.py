from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from doc_compliance.models import Document, Evidence, Requirement

MAX_QUOTE = 400
NEGATION_CUES = frozenset(
    {"no", "not", "never", "without", "lack", "lacks", "lacking", "cannot", "none",
     "neither", "nor", "dont", "doesnt", "isnt", "arent", "wont", "didnt", "nunca", "sin"}
)
MODALS = frozenset({"must", "shall", "should", "may", "will"})
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])|\n+")
_CLAUSE_CUT = re.compile(r"[,;:()]")
_TOKEN = re.compile(r"[\w]+")
_SUFFIX = r"(?:s|es|ed|d|ing)?"


def fold(text: str) -> str:
    out: list[str] = []
    for ch in text:
        base = unicodedata.normalize("NFKD", ch)[:1] or ch
        out.append(base.lower()[:1] or ch)
    return "".join(out)


@dataclass(frozen=True)
class Term:
    spec: str
    patterns: tuple[re.Pattern[str], ...]

    def find(self, folded: str) -> list[tuple[int, int]]:
        hits: list[tuple[int, int]] = []
        for pat in self.patterns:
            hits.extend((m.start(), m.end()) for m in pat.finditer(folded))
        return sorted(hits)


def compile_term(spec: str) -> Term:
    patterns: list[re.Pattern[str]] = []
    for alt in spec.split("|"):
        words = [w for w in re.split(r"[\s\-]+", fold(alt.strip())) if w]
        if not words:
            continue
        body = r"[\s\-]+".join(re.escape(w) for w in words)
        patterns.append(re.compile(rf"(?<!\w){body}{_SUFFIX}(?!\w)"))
    if not patterns:
        raise ValueError(f"termino vacio: {spec!r}")
    return Term(spec=spec, patterns=tuple(patterns))


@dataclass(frozen=True)
class Sentence:
    start: int
    end: int


@dataclass
class PreparedDoc:
    doc: Document
    folded: str
    sentences: list[Sentence]


def split_sentences(text: str) -> list[Sentence]:
    spans: list[Sentence] = []
    pos = 0
    for m in _SENTENCE_BREAK.finditer(text):
        _push(text, pos, m.start(), spans)
        pos = m.end()
    _push(text, pos, len(text), spans)
    return spans


def _push(text: str, start: int, end: int, spans: list[Sentence]) -> None:
    segment = text[start:end]
    stripped = segment.strip()
    if not stripped:
        return
    lead = len(segment) - len(segment.lstrip())
    spans.append(Sentence(start + lead, start + lead + len(stripped)))


def prepare(docs: list[Document]) -> list[PreparedDoc]:
    return [PreparedDoc(d, fold(d.text), split_sentences(d.text)) for d in docs]


def is_negated(folded: str, sent_start: int, hit_start: int) -> bool:
    prefix = folded[sent_start:hit_start].replace("'", "")
    cut = list(_CLAUSE_CUT.finditer(prefix))
    if cut:
        prefix = prefix[cut[-1].end():]
    tokens = _TOKEN.findall(prefix)[-4:]
    for i, tok in enumerate(tokens):
        if tok not in NEGATION_CUES:
            continue
        if i > 0 and tokens[i - 1] in MODALS:
            continue
        if len(tokens) - i <= 3:
            return True
    return False


@dataclass
class EvidenceReport:
    evidence: list[Evidence] = field(default_factory=list)
    keywords_found: list[str] = field(default_factory=list)
    keywords_missing: list[str] = field(default_factory=list)
    must_found: list[str] = field(default_factory=list)
    must_missing: list[str] = field(default_factory=list)
    must_negated: list[str] = field(default_factory=list)


def collect_evidence(
    req: Requirement, prepared: list[PreparedDoc], max_evidence: int = 3
) -> EvidenceReport:
    kw_terms = [compile_term(k) for k in req.keywords]
    must_terms = [compile_term(m) for m in req.must_have]
    kw_found: set[str] = set()
    must_found: set[str] = set()
    must_neg: set[str] = set()
    positives: list[Evidence] = []
    negatives: list[Evidence] = []

    for pdoc in prepared:
        for sent in pdoc.sentences:
            seg = pdoc.folded[sent.start:sent.end]
            ok_kw, ok_must, bad = [], [], []
            for term in kw_terms:
                _classify(term, seg, pdoc.folded, sent.start, ok_kw, bad, kw_found)
            for term in must_terms:
                _classify(term, seg, pdoc.folded, sent.start, ok_must, bad, must_found, must_neg)
            if not (ok_kw or ok_must or bad):
                continue
            quote = pdoc.doc.text[sent.start:sent.end]
            if len(quote) > MAX_QUOTE:
                quote = quote[:MAX_QUOTE].rstrip() + "..."
            if ok_kw or ok_must:
                score = 2.0 * len(ok_must) + len(ok_kw)
                positives.append(
                    Evidence(pdoc.doc.name, sent.start, sent.end, quote,
                             tuple(ok_kw), tuple(ok_must), bool(bad), score)
                )
            else:
                negatives.append(
                    Evidence(pdoc.doc.name, sent.start, sent.end, quote, (), (), True, 0.5)
                )

    positives.sort(key=lambda e: (-e.score, e.doc, e.start))
    negatives.sort(key=lambda e: (e.doc, e.start))
    slots = max_evidence - 1 if negatives and max_evidence > 1 else max_evidence
    chosen = positives[:slots]
    chosen += negatives[: max_evidence - len(chosen)]

    must_neg_only = [m for m in req.must_have if m in must_neg and m not in must_found]
    return EvidenceReport(
        evidence=chosen,
        keywords_found=[k for k in req.keywords if k in kw_found],
        keywords_missing=[k for k in req.keywords if k not in kw_found],
        must_found=[m for m in req.must_have if m in must_found],
        must_missing=[m for m in req.must_have if m not in must_found and m not in must_neg_only],
        must_negated=must_neg_only,
    )


def _classify(
    term: Term,
    seg: str,
    folded_doc: str,
    sent_start: int,
    matched: list[str],
    negated_hits: list[str],
    found: set[str],
    neg_found: set[str] | None = None,
) -> None:
    hits = term.find(seg)
    if not hits:
        return
    live = [h for h in hits if not is_negated(folded_doc, sent_start, sent_start + h[0])]
    if live:
        matched.append(term.spec)
        found.add(term.spec)
    else:
        negated_hits.append(term.spec)
        if neg_found is not None:
            neg_found.add(term.spec)
