from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from doc_compliance.models import ComplianceRun

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  checklist TEXT NOT NULL,
  documents TEXT NOT NULL,
  overall_pct REAL NOT NULL,
  verdict TEXT NOT NULL,
  passed INTEGER NOT NULL,
  partial INTEGER NOT NULL,
  failed INTEGER NOT NULL,
  critical_gaps INTEGER NOT NULL,
  payload TEXT NOT NULL
);
"""


def default_db_path() -> Path:
    env = os.environ.get("DOC_COMPLIANCE_DB")
    if env:
        return Path(env)
    return Path("results") / "history.db"


@contextmanager
def _connect(db_path: Path | str | None) -> Iterator[sqlite3.Connection]:
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        with conn:
            yield conn
    finally:
        conn.close()


def save_run(run: ComplianceRun, db_path: Path | str | None = None) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO runs (created_at, label, checklist, documents, overall_pct, verdict,
               passed, partial, failed, critical_gaps, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.created_at,
                run.label,
                f"{run.checklist_name} v{run.checklist_version}",
                json.dumps(run.documents),
                run.overall_pct,
                run.verdict,
                run.counts.get("pass", 0),
                run.counts.get("partial", 0),
                run.counts.get("fail", 0),
                len(run.critical_gaps),
                json.dumps(run.to_dict()),
            ),
        )
        return int(cur.lastrowid)


def list_runs(limit: int = 20, db_path: Path | str | None = None) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT id, created_at, label, checklist, documents, overall_pct, verdict,
               passed, partial, failed, critical_gaps FROM runs ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["documents"] = json.loads(item["documents"])
        out.append(item)
    return out


def get_run(run_id: int, db_path: Path | str | None = None) -> dict[str, Any] | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
    return json.loads(row["payload"]) if row else None
