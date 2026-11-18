import json

import pytest

from doc_compliance.checklist import (
    ChecklistError,
    default_checklist_path,
    load_checklist,
    parse_checklist,
    samples_dir,
    spanish_checklist_path,
)
from doc_compliance.cli import main
from doc_compliance.corpus import load_documents
from doc_compliance.evidence import compile_term, fold, is_negated, split_sentences
from doc_compliance.models import FAIL, PARTIAL, PASS, Document
from doc_compliance.report import to_html, to_json, to_markdown, write_reports
from doc_compliance.scorer import run_check
from doc_compliance.store import get_run, list_runs, save_run
from doc_compliance.web import CheckRequest, execute_check


@pytest.fixture(scope="module")
def checklist():
    return load_checklist(default_checklist_path())


@pytest.fixture(scope="module")
def run_ok(checklist):
    return run_check(checklist, load_documents(samples_dir() / "docs_ok"))


@pytest.fixture(scope="module")
def run_gap(checklist):
    return run_check(checklist, load_documents(samples_dir() / "docs_gap"))


def test_checklist_loads_all_requirements(checklist):
    assert len(checklist.requirements) == 14
    assert checklist.get("SEC-02").critical is True
    assert all(r.keywords and r.must_have for r in checklist.requirements)


def test_checklist_rejects_duplicates_and_empty():
    with pytest.raises(ChecklistError):
        parse_checklist({"requirements": []})
    dup = {"requirements": [
        {"id": "A", "title": "x", "keywords": ["k"]},
        {"id": "A", "title": "y", "keywords": ["k"]},
    ]}
    with pytest.raises(ChecklistError):
        parse_checklist(dup)


def test_fold_keeps_length_and_strips_accents():
    text = "Autenticación Ñandú"
    assert len(fold(text)) == len(text)
    assert fold(text) == "autenticacion nandu"


def test_term_matches_variants_and_boundaries():
    term = compile_term("multi-factor authentication|mfa")
    assert term.find(fold("Multi factor authentication is on"))
    assert term.find(fold("Enable MFA today"))
    assert not term.find(fold("the mfab of nothing"))
    assert compile_term("password").find(fold("Passwords expire"))


def test_sentence_split_offsets_match_text():
    text = "First rule applies. Second rule applies.\nThird line"
    spans = split_sentences(text)
    assert [text[s.start:s.end] for s in spans] == [
        "First rule applies.", "Second rule applies.", "Third line"
    ]


def test_negation_detection():
    neg = fold("We do not enforce multi-factor authentication")
    pos = fold("Staff must not share multi-factor authentication codes")
    hit_neg = compile_term("multi-factor authentication").find(neg)[0][0]
    hit_pos = compile_term("multi-factor authentication").find(pos)[0][0]
    assert is_negated(neg, 0, hit_neg)
    assert not is_negated(pos, 0, hit_pos)


def test_docs_ok_mostly_pass(run_ok):
    assert run_ok.counts[PASS] >= 12
    assert run_ok.counts[FAIL] == 0
    assert run_ok.overall_pct >= 90
    assert run_ok.critical_gaps == []
    assert run_ok.verdict == "compliant"


def test_docs_gap_has_fails_and_critical_gaps(run_gap, run_ok):
    assert run_gap.counts[FAIL] >= 8
    assert run_gap.overall_pct < 30
    assert run_gap.verdict == "non_compliant"
    assert {"SEC-02", "SEC-05", "SEC-07"} <= set(run_gap.critical_gaps)
    assert run_gap.overall_pct < run_ok.overall_pct


def test_partial_requirements_are_detected(run_ok, run_gap):
    assert run_ok.result_for("SEC-14").status == PARTIAL
    assert run_ok.result_for("SEC-14").missing_must_have == ["asset owner"]
    assert run_gap.result_for("SEC-04").status == PARTIAL
    assert run_gap.result_for("SEC-09").status == PARTIAL


def test_evidence_citations_point_to_real_text(run_ok):
    docs = {d.name: d.text for d in load_documents(samples_dir() / "docs_ok")}
    for res in run_ok.results:
        assert res.evidence, res.requirement.id
        for ev in res.evidence:
            assert docs[ev.doc][ev.start:ev.end].startswith(ev.quote.rstrip("."))
            assert ev.end > ev.start


def test_evidence_is_found_in_expected_document(run_ok):
    mfa = run_ok.result_for("SEC-02")
    assert mfa.status == PASS
    assert mfa.evidence[0].doc == "access_policy.txt"
    assert "multi-factor authentication" in mfa.evidence[0].matched_must_have[0].lower()
    backup = run_ok.result_for("SEC-08")
    assert backup.evidence[0].doc == "operations.txt"


def test_gap_reports_missing_and_negated_terms(run_gap):
    mfa = run_gap.result_for("SEC-02")
    assert mfa.status == FAIL
    assert any("multi-factor" in m for m in mfa.negated_must_have)
    assert any(ev.negated for ev in mfa.evidence)
    incident = run_gap.result_for("SEC-07")
    assert incident.evidence == []
    assert "incident response plan" in incident.missing_must_have
    assert incident.missing_keywords


def test_negated_must_have_does_not_count(checklist):
    docs = [Document("n.txt", "We do not use multi-factor authentication for all remote access.")]
    res = run_check(checklist, docs).result_for("SEC-02")
    assert res.must_have_coverage == 0.5
    assert len(res.negated_must_have) == 1
    assert res.status == FAIL


def test_accented_text_matches_ascii_keywords(checklist):
    docs = [Document("a.txt", "Se aplica Least Privilege con REVISIÓN: access review trimestral.")]
    res = run_check(checklist, docs).result_for("SEC-01")
    assert res.must_have_coverage == 1.0


def test_reports_render_all_formats(run_ok, run_gap, tmp_path):
    md = to_markdown(run_gap)
    assert "## Brechas criticas" in md and "SEC-07" in md
    data = json.loads(to_json(run_ok))
    assert data["counts"]["pass"] == run_ok.counts[PASS]
    assert len(data["requirements"]) == 14
    assert "<table>" in to_html(run_ok)
    paths = write_reports(run_ok, tmp_path / "out", with_html=True)
    assert paths["md"].name == "compliance_report.md"
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["verdict"] == "compliant"
    assert paths["html"].exists()


def test_store_roundtrip(run_ok, run_gap, tmp_path):
    db = tmp_path / "h.db"
    first = save_run(run_ok, db)
    second = save_run(run_gap, db)
    rows = list_runs(10, db)
    assert [r["id"] for r in rows] == [second, first]
    assert rows[0]["failed"] == run_gap.counts[FAIL]
    assert get_run(first, db)["overall_pct"] == run_ok.overall_pct
    assert get_run(999, db) is None


def test_cli_check_writes_reports_and_history(tmp_path, capsys):
    out = tmp_path / "results"
    code = main(["check", "--docs", str(samples_dir() / "docs_gap"), "--out", str(out),
                 "--label", "t", "--fail-under", "50"])
    assert code == 1
    assert (out / "compliance_report.md").exists()
    assert (out / "compliance_report.json").exists()
    assert main(["history", "--db", str(out / "history.db")]) == 0
    assert "non_compliant" in capsys.readouterr().out


def test_cli_compare_and_history_show(tmp_path, capsys):
    out = tmp_path / "res"
    assert main(["compare", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "docs_ok" in text and "docs_gap" in text
    assert (out / "compare.json").exists()
    assert main(["history", "--show", "1", "--db", str(out / "history.db")]) == 0
    assert main(["history", "--show", "99", "--db", str(out / "history.db")]) == 2


def test_cli_reports_errors(tmp_path, capsys):
    assert main(["check", "--docs", str(tmp_path / "nope"), "--out", str(tmp_path)]) == 2
    assert "error:" in capsys.readouterr().err


def test_web_execute_check_modes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC_COMPLIANCE_DB", str(tmp_path / "web.db"))
    ok = execute_check(CheckRequest(mode="samples_ok"))
    gap = execute_check(CheckRequest(mode="samples_gap"))
    assert ok["overall_pct"] > gap["overall_pct"]
    assert gap["run_id"] > ok["run_id"]
    upload = execute_check(CheckRequest(
        mode="upload",
        documents=[{"name": "u.txt", "text": "Daily backups run and a restore test happens quarterly."}],
    ))
    assert upload["documents"] == ["u.txt"]
    assert (tmp_path / "results" / "compliance_report.md").exists()
    assert len(list_runs(10)) == 3


def test_experiment_reference_scores(checklist):
    ok = run_check(checklist, load_documents(samples_dir() / "docs_ok"))
    gap = run_check(checklist, load_documents(samples_dir() / "docs_gap"))
    assert round(ok.overall_pct, 1) == 98.9
    assert ok.critical_gaps == []
    assert round(gap.overall_pct, 1) == 11.7
    assert gap.critical_gaps == ["SEC-01", "SEC-02", "SEC-04", "SEC-05", "SEC-07", "SEC-08"]
    assert gap.verdict == "non_compliant"


def test_web_health_and_console(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from doc_compliance.web import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DOC_COMPLIANCE_DB", str(tmp_path / "web.db"))
    client = TestClient(app)
    assert client.get("/api/health").json()["status"] == "ok"
    page = client.get("/")
    assert page.status_code == 200 and "Consola de cumplimiento" in page.text
    res = client.post("/api/check", json={"mode": "samples_gap"})
    assert res.status_code == 200 and res.json()["critical_gaps"]
    assert client.post("/api/check", json={"mode": "paths"}).status_code == 400
    assert len(client.get("/api/history").json()) == 1


@pytest.fixture(scope="module")
def checklist_es():
    return load_checklist(spanish_checklist_path())


@pytest.fixture(scope="module")
def run_ok_es(checklist_es):
    return run_check(checklist_es, load_documents(samples_dir() / "docs_ok_es"))


@pytest.fixture(scope="module")
def run_gap_es(checklist_es):
    return run_check(checklist_es, load_documents(samples_dir() / "docs_gap_es"))


def _negated(text: str, term: str) -> bool:
    folded = fold(text)
    start = compile_term(term).find(folded)[0][0]
    return is_negated(folded, 0, start)


@pytest.mark.parametrize("text", [
    "No exigimos autenticación multifactor para el personal",
    "No aplicamos cifrado en reposo en las bases de datos",
    "No contamos con un plan de respuesta a incidentes",
    "Hoy no se cuenta con un plan de respuesta a incidentes",
    "Carecemos de un plan de respuesta a incidentes",
    "Nunca hemos hecho una prueba de restauración",
    "Sin autenticación multifactor en el acceso remoto",
])
def test_spanish_negation_detected(text):
    term = next(t for t in (
        "autenticacion multifactor", "cifrado en reposo",
        "plan de respuesta a incidentes", "prueba de restauracion",
    ) if t in fold(text))
    assert _negated(text, term)


@pytest.mark.parametrize("text", [
    "Se exige autenticación multifactor para todo acceso remoto",
    "No se deben compartir los códigos de autenticación multifactor",
    "Se aplica cifrado en reposo, no hay excepciones",
    "Contamos con un plan de respuesta a incidentes",
])
def test_spanish_affirmative_or_prohibition_not_negated(text):
    term = next(t for t in (
        "autenticacion multifactor", "cifrado en reposo", "plan de respuesta a incidentes",
    ) if t in fold(text))
    assert not _negated(text, term)


def test_english_negation_window_unchanged():
    assert not _negated("We have an incident response plan that is tested", "incident response plan")
    assert _negated("We do not have an incident response plan", "incident response plan")


def test_spanish_checklist_loads(checklist_es):
    assert len(checklist_es.requirements) == 12
    assert [r.id for r in checklist_es.requirements] == [f"ES-{i:02d}" for i in range(1, 13)]
    critical = {r.id for r in checklist_es.requirements if r.critical}
    assert critical == {"ES-01", "ES-02", "ES-04", "ES-05", "ES-07", "ES-08"}
    assert all(r.keywords and r.must_have for r in checklist_es.requirements)


def test_docs_ok_es_complies(run_ok_es):
    assert run_ok_es.overall_pct >= 90
    assert run_ok_es.counts[FAIL] == 0
    assert run_ok_es.critical_gaps == []
    assert run_ok_es.verdict == "compliant"


def test_docs_gap_es_has_critical_gaps_including_mfa(run_gap_es, run_ok_es):
    assert run_gap_es.overall_pct < 20
    assert run_gap_es.verdict == "non_compliant"
    assert "ES-02" in run_gap_es.critical_gaps
    assert {"ES-01", "ES-04", "ES-05", "ES-07", "ES-08"} <= set(run_gap_es.critical_gaps)
    assert run_ok_es.overall_pct - run_gap_es.overall_pct > 70


def test_spanish_negations_become_counter_evidence(run_gap_es):
    mfa = run_gap_es.result_for("ES-02")
    assert mfa.status == FAIL and mfa.score == 0
    assert mfa.negated_must_have
    assert any(ev.negated and "No exigimos" in ev.quote for ev in mfa.evidence)
    assert run_gap_es.result_for("ES-07").negated_must_have
    assert run_gap_es.result_for("ES-05").negated_must_have


def test_spanish_evidence_citations_point_to_real_text(run_ok_es):
    docs = {d.name: d.text for d in load_documents(samples_dir() / "docs_ok_es")}
    for res in run_ok_es.results:
        assert res.evidence, res.requirement.id
        for ev in res.evidence:
            assert docs[ev.doc][ev.start:ev.end].startswith(ev.quote.rstrip("."))


def test_sentence_split_after_accented_capital():
    text = "Primera regla. Áreas críticas aplican. Ñandú cierra."
    assert len(split_sentences(text)) == 3


def test_cli_compare_es(tmp_path, capsys):
    out = tmp_path / "es"
    assert main(["compare", "--es", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "ES-02" in text and "docs_gap" in text
    data = json.loads((out / "compare.json").read_text(encoding="utf-8"))
    assert data["gap"]["checklist"]["name"].startswith("Línea base")
    assert data["ok"]["overall_pct"] - data["gap"]["overall_pct"] > 70


def test_cli_check_es(tmp_path, capsys):
    out = tmp_path / "es_check"
    assert main(["check", "--es", "--out", str(out), "--fail-under", "80"]) == 0
    assert "Brechas criticas: ninguna" in capsys.readouterr().out
    assert main(["check", "--es", "--gap", "--out", str(out), "--fail-under", "80"]) == 1
    assert "ES-02" in capsys.readouterr().out


def test_experiment_reference_scores_es(run_ok_es, run_gap_es):
    assert round(run_ok_es.overall_pct, 1) == 100.0
    assert round(run_gap_es.overall_pct, 1) == 8.8
    assert run_gap_es.critical_gaps == ["ES-01", "ES-02", "ES-04", "ES-05", "ES-07", "ES-08"]
