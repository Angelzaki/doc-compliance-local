from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from doc_compliance import __version__
from doc_compliance.checklist import (
    ChecklistError,
    default_checklist_path,
    load_checklist,
    samples_dir,
)
from doc_compliance.corpus import CorpusError, load_documents
from doc_compliance.models import ComplianceRun
from doc_compliance.report import VERDICT_LABEL, write_reports
from doc_compliance.scorer import run_check
from doc_compliance.store import get_run, list_runs, save_run

DEFAULT_PORT = 8022


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doc-compliance",
        description="Verificador local de cumplimiento documental (matching lexico, sin LLM).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check", help="evalua documentos contra un checklist")
    check.add_argument("--checklist", default=str(default_checklist_path()))
    check.add_argument("--docs", default=str(samples_dir() / "docs_ok"))
    check.add_argument("--out", default="results")
    check.add_argument("--html", action="store_true", help="genera tambien compliance_report.html")
    check.add_argument("--label", default="")
    check.add_argument("--db", default=None, help="ruta SQLite (por defecto results/history.db)")
    check.add_argument("--no-store", action="store_true")
    check.add_argument("--max-evidence", type=int, default=3)
    check.add_argument("--fail-under", type=float, default=None, help="exit 1 si el puntaje es menor")

    compare = sub.add_parser("compare", help="compara docs_ok vs docs_gap")
    compare.add_argument("--checklist", default=str(default_checklist_path()))
    compare.add_argument("--ok", default=str(samples_dir() / "docs_ok"))
    compare.add_argument("--gap", default=str(samples_dir() / "docs_gap"))
    compare.add_argument("--out", default="results")
    compare.add_argument("--db", default=None)
    compare.add_argument("--no-store", action="store_true")

    serve = sub.add_parser("serve", help="UI web local")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)

    hist = sub.add_parser("history", help="historial de corridas")
    hist.add_argument("--limit", type=int, default=20)
    hist.add_argument("--show", type=int, default=None, help="imprime el JSON de una corrida")
    hist.add_argument("--db", default=None)
    return parser


def format_summary(run: ComplianceRun) -> str:
    lines = [
        f"{run.checklist_name} v{run.checklist_version} | docs: {', '.join(run.documents)}",
        f"Puntaje global: {run.overall_pct:.1f}% - {VERDICT_LABEL.get(run.verdict, run.verdict)}",
        f"pass={run.counts['pass']} partial={run.counts['partial']} fail={run.counts['fail']}",
        "",
        f"{'ID':<8}{'Estado':<9}{'Pts':>5}  {'Crit':<5}Requisito",
    ]
    for r in run.results:
        req = r.requirement
        lines.append(
            f"{req.id:<8}{r.status.upper():<9}{r.score * 100:>4.0f}%  "
            f"{'si' if req.critical else '-':<5}{req.title}"
        )
    lines.append("")
    if run.critical_gaps:
        lines.append("Brechas criticas: " + ", ".join(run.critical_gaps))
    else:
        lines.append("Brechas criticas: ninguna")
    return "\n".join(lines)


def cmd_check(args: argparse.Namespace) -> int:
    checklist = load_checklist(args.checklist)
    docs = load_documents(args.docs)
    run = run_check(checklist, docs, max_evidence=args.max_evidence, label=args.label)
    paths = write_reports(run, args.out, with_html=args.html)
    print(format_summary(run))
    print()
    for kind, path in paths.items():
        print(f"{kind}: {path}")
    if not args.no_store:
        run_id = save_run(run, args.db or Path(args.out) / "history.db")
        print(f"historial: corrida #{run_id}")
    if args.fail_under is not None and run.overall_pct < args.fail_under:
        return 1
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    checklist = load_checklist(args.checklist)
    ok = run_check(checklist, load_documents(args.ok), label="compare:ok")
    gap = run_check(checklist, load_documents(args.gap), label="compare:gap")
    print(f"{'ID':<8}{'OK':<9}{'GAP':<9}Requisito")
    for r_ok, r_gap in zip(ok.results, gap.results):
        print(f"{r_ok.requirement.id:<8}{r_ok.status.upper():<9}{r_gap.status.upper():<9}"
              f"{r_ok.requirement.title}")
    print()
    print(f"docs_ok : {ok.overall_pct:5.1f}%  pass={ok.counts['pass']} partial={ok.counts['partial']} "
          f"fail={ok.counts['fail']} criticas={len(ok.critical_gaps)}")
    print(f"docs_gap: {gap.overall_pct:5.1f}%  pass={gap.counts['pass']} partial={gap.counts['partial']} "
          f"fail={gap.counts['fail']} criticas={len(gap.critical_gaps)}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "compare.json").write_text(
        json.dumps({"ok": ok.to_dict(), "gap": gap.to_dict()}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if not args.no_store:
        db = args.db or out / "history.db"
        save_run(ok, db)
        save_run(gap, db)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from doc_compliance.web import app

    print(f"UI en http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    db = args.db or Path("results") / "history.db"
    if args.show is not None:
        payload = get_run(args.show, db)
        if payload is None:
            print(f"no existe la corrida #{args.show}", file=sys.stderr)
            return 2
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    rows = list_runs(args.limit, db)
    if not rows:
        print("sin corridas registradas")
        return 0
    print(f"{'#':<5}{'Fecha (UTC)':<22}{'Pts':>6}  {'P/Pa/F':<9}{'Crit':<5}{'Veredicto':<15}Etiqueta")
    for r in rows:
        trio = f"{r['passed']}/{r['partial']}/{r['failed']}"
        print(f"{r['id']:<5}{r['created_at'][:19]:<22}{r['overall_pct']:>5.1f}%  {trio:<9}"
              f"{r['critical_gaps']:<5}{r['verdict']:<15}{r['label']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "check": cmd_check,
        "compare": cmd_compare,
        "serve": cmd_serve,
        "history": cmd_history,
    }
    if args.command is None:
        parser.print_help()
        return 0
    try:
        return handlers[args.command](args)
    except (ChecklistError, CorpusError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
