from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from doc_compliance.checklist import (
    ChecklistError,
    default_checklist_path,
    load_checklist,
    parse_checklist,
    samples_dir,
)
from doc_compliance.corpus import CorpusError, documents_from_texts, load_documents
from doc_compliance.report import render_html, write_reports
from doc_compliance.scorer import run_check
from doc_compliance.store import get_run, list_runs, save_run

TEMPLATE = Path(__file__).parent / "templates" / "index.html"

app = FastAPI(title="doc-compliance-local", version="0.1.0")


class UploadedDoc(BaseModel):
    name: str
    text: str


class CheckRequest(BaseModel):
    mode: str = Field(default="samples_ok", pattern="^(samples_ok|samples_gap|paths|upload)$")
    checklist_path: str | None = None
    docs_path: str | None = None
    checklist_json: dict[str, Any] | None = None
    documents: list[UploadedDoc] = Field(default_factory=list)
    label: str = ""
    max_evidence: int = Field(default=3, ge=1, le=10)


def execute_check(req: CheckRequest) -> dict[str, Any]:
    if req.checklist_json is not None:
        checklist = parse_checklist(req.checklist_json, source="upload")
    else:
        checklist = load_checklist(req.checklist_path or default_checklist_path())

    if req.mode == "samples_ok":
        docs = load_documents(samples_dir() / "docs_ok")
    elif req.mode == "samples_gap":
        docs = load_documents(samples_dir() / "docs_gap")
    elif req.mode == "paths":
        if not req.docs_path:
            raise CorpusError("indica docs_path")
        docs = load_documents(req.docs_path)
    else:
        docs = documents_from_texts([(d.name, d.text) for d in req.documents])

    label = req.label or f"web:{req.mode}"
    run = run_check(checklist, docs, max_evidence=req.max_evidence, label=label)
    write_reports(run, "results", with_html=True)
    run_id = save_run(run)
    payload = run.to_dict()
    payload["run_id"] = run_id
    return payload


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


@app.get("/api/samples")
def api_samples() -> dict[str, str]:
    base = samples_dir()
    return {
        "checklist": str(default_checklist_path()),
        "docs_ok": str(base / "docs_ok"),
        "docs_gap": str(base / "docs_gap"),
    }


@app.post("/api/check")
def api_check(req: CheckRequest) -> dict[str, Any]:
    try:
        return execute_check(req)
    except (ChecklistError, CorpusError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/history")
def api_history(limit: int = 20) -> list[dict[str, Any]]:
    return list_runs(limit)


@app.get("/api/history/{run_id}")
def api_history_item(run_id: int) -> dict[str, Any]:
    payload = get_run(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="corrida no encontrada")
    return payload


@app.get("/api/history/{run_id}/html", response_class=HTMLResponse)
def api_history_html(run_id: int) -> str:
    payload = get_run(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="corrida no encontrada")
    return render_html(payload)
