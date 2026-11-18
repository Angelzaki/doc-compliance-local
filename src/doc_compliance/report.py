from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from doc_compliance.models import ComplianceRun

STATUS_LABEL = {"pass": "PASS", "partial": "PARTIAL", "fail": "FAIL"}
VERDICT_LABEL = {
    "compliant": "Cumple",
    "needs_work": "Requiere trabajo",
    "non_compliant": "No cumple",
}
STATUS_COLOR = {"pass": "#198754", "partial": "#e0a800", "fail": "#dc3545"}


def to_json(run: ComplianceRun) -> str:
    return json.dumps(run.to_dict(), indent=2, ensure_ascii=False)


def to_markdown(run: ComplianceRun) -> str:
    data = run.to_dict()
    c = data["counts"]
    lines = [
        f"# Reporte de cumplimiento: {data['checklist']['name']} v{data['checklist']['version']}",
        "",
        f"- Generado: {data['created_at']}",
        f"- Documentos: {', '.join(data['documents'])}",
        f"- **Puntaje global: {data['overall_pct']:.1f}%** ({VERDICT_LABEL.get(data['verdict'], data['verdict'])})",
        f"- Pass: {c['pass']} | Partial: {c['partial']} | Fail: {c['fail']}",
        "",
        "## Brechas criticas",
        "",
    ]
    by_id = {r["id"]: r for r in data["requirements"]}
    if data["critical_gaps"]:
        for rid in data["critical_gaps"]:
            r = by_id[rid]
            lines.append(f"- **{rid}** {r['title']}: {STATUS_LABEL[r['status']]}")
    else:
        lines.append("Ninguna.")
    lines += ["", "## Matriz", "", "| ID | Requisito | Critico | Estado | Puntaje | Evidencia |",
              "|---|---|---|---|---|---|"]
    for r in data["requirements"]:
        cites = ", ".join(e["citation"] for e in r["evidence"] if not e["negated"]) or "-"
        lines.append(
            f"| {r['id']} | {_md(r['title'])} | {'si' if r['critical'] else 'no'} "
            f"| {STATUS_LABEL[r['status']]} | {r['score'] * 100:.0f}% | {cites} |"
        )
    lines += ["", "## Detalle", ""]
    for r in data["requirements"]:
        lines.append(f"### {r['id']} {r['title']} [{STATUS_LABEL[r['status']]}]")
        lines.append("")
        if r["evidence"]:
            for e in r["evidence"]:
                tag = " (negado)" if e["negated"] else ""
                lines.append(f"- `{e['citation']}`{tag}: \"{_md(e['quote'])}\"")
        else:
            lines.append("- Sin evidencia encontrada.")
        if r["missing_must_have"]:
            lines.append(f"- Frases obligatorias ausentes: {', '.join(r['missing_must_have'])}")
        if r["negated_must_have"]:
            lines.append(f"- Frases obligatorias solo negadas: {', '.join(r['negated_must_have'])}")
        if r["missing_keywords"]:
            lines.append(f"- Keywords ausentes: {', '.join(r['missing_keywords'])}")
        lines.append("")
    return "\n".join(lines)


def to_html(run: ComplianceRun) -> str:
    return render_html(run.to_dict())


def render_html(data: dict[str, Any]) -> str:
    esc = html.escape
    rows = []
    for r in data["requirements"]:
        color = STATUS_COLOR[r["status"]]
        ev = "".join(
            f"<div class='ev{' neg' if e['negated'] else ''}'><code>{esc(e['citation'])}</code> "
            f"{esc(e['quote'])}</div>"
            for e in r["evidence"]
        ) or "<em>sin evidencia</em>"
        missing = ", ".join(r["missing_must_have"] + r["missing_keywords"])
        rows.append(
            f"<tr><td>{esc(r['id'])}</td><td>{esc(r['title'])}"
            f"{' <b>*</b>' if r['critical'] else ''}</td>"
            f"<td style='color:{color};font-weight:600'>{STATUS_LABEL[r['status']]}</td>"
            f"<td>{r['score'] * 100:.0f}%</td><td>{ev}</td><td>{esc(missing)}</td></tr>"
        )
    c = data["counts"]
    verdict = VERDICT_LABEL.get(data["verdict"], data["verdict"])
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        f"<title>Compliance {esc(data['checklist']['name'])}</title>"
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;color:#212529}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #dee2e6;padding:.4rem;"
        "vertical-align:top;font-size:.9rem}th{background:#f8f9fa}.ev{margin-bottom:.3rem}"
        ".neg{color:#dc3545}code{background:#f1f3f5;padding:0 .25rem}</style></head><body>"
        f"<h1>{esc(data['checklist']['name'])} v{esc(str(data['checklist']['version']))}</h1>"
        f"<p><b>{data['overall_pct']:.1f}%</b> - {esc(verdict)} | pass {c['pass']} / "
        f"partial {c['partial']} / fail {c['fail']}</p>"
        f"<p>Documentos: {esc(', '.join(data['documents']))}</p>"
        f"<p>Brechas criticas: {esc(', '.join(data['critical_gaps']) or 'ninguna')}</p>"
        "<table><tr><th>ID</th><th>Requisito</th><th>Estado</th><th>Puntaje</th>"
        "<th>Evidencia</th><th>Faltante</th></tr>" + "".join(rows) + "</table></body></html>"
    )


def write_reports(
    run: ComplianceRun, out_dir: str | Path = "results", with_html: bool = False
) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "md": out / "compliance_report.md",
        "json": out / "compliance_report.json",
    }
    paths["md"].write_text(to_markdown(run), encoding="utf-8")
    paths["json"].write_text(to_json(run), encoding="utf-8")
    if with_html:
        paths["html"] = out / "compliance_report.html"
        paths["html"].write_text(to_html(run), encoding="utf-8")
    return paths


def _md(text: str) -> str:
    return " ".join(text.replace("|", "\\|").split())
