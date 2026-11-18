from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from doc_compliance.models import Checklist, Requirement


class ChecklistError(ValueError):
    pass


def samples_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "samples"


def default_checklist_path() -> Path:
    return samples_dir() / "checklist" / "security_baseline.json"


def parse_checklist(data: dict[str, Any], source: str = "") -> Checklist:
    raw_reqs = data.get("requirements")
    if not isinstance(raw_reqs, list) or not raw_reqs:
        raise ChecklistError("el checklist necesita una lista 'requirements' no vacia")
    seen: set[str] = set()
    reqs: list[Requirement] = []
    for idx, raw in enumerate(raw_reqs, start=1):
        if not isinstance(raw, dict):
            raise ChecklistError(f"requirement #{idx} no es un objeto")
        req_id = str(raw.get("id", "")).strip()
        title = str(raw.get("title", "")).strip()
        if not req_id or not title:
            raise ChecklistError(f"requirement #{idx} requiere 'id' y 'title'")
        if req_id in seen:
            raise ChecklistError(f"id duplicado: {req_id}")
        seen.add(req_id)
        keywords = _str_tuple(raw.get("keywords"))
        must_have = _str_tuple(raw.get("must_have"))
        if not keywords and not must_have:
            raise ChecklistError(f"{req_id}: define 'keywords' o 'must_have'")
        weight = float(raw.get("weight", 1.0))
        if weight <= 0:
            raise ChecklistError(f"{req_id}: weight debe ser > 0")
        reqs.append(
            Requirement(
                id=req_id,
                title=title,
                keywords=keywords,
                must_have=must_have,
                description=str(raw.get("description", "")).strip(),
                critical=bool(raw.get("critical", False)),
                weight=weight,
                category=str(raw.get("category", "")).strip(),
            )
        )
    return Checklist(
        name=str(data.get("name", "checklist")),
        version=str(data.get("version", "1")),
        requirements=tuple(reqs),
        source=source,
    )


def load_checklist(path: str | Path) -> Checklist:
    p = Path(path)
    if not p.is_file():
        raise ChecklistError(f"no existe el checklist: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ChecklistError(f"JSON invalido en {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise ChecklistError("la raiz del checklist debe ser un objeto")
    return parse_checklist(data, source=str(p))


def _str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    return tuple(str(v).strip() for v in value if str(v).strip())
