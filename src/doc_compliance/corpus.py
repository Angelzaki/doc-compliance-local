from __future__ import annotations

from pathlib import Path

from doc_compliance.models import Document

SUPPORTED_SUFFIXES = (".txt", ".md")


class CorpusError(ValueError):
    pass


def load_documents(path: str | Path) -> list[Document]:
    p = Path(path)
    if not p.exists():
        raise CorpusError(f"no existe la ruta de documentos: {p}")
    if p.is_file():
        return [_read(p, p.parent)]
    files = sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in SUPPORTED_SUFFIXES)
    if not files:
        raise CorpusError(f"sin documentos {SUPPORTED_SUFFIXES} en {p}")
    return [_read(f, p) for f in files]


def documents_from_texts(items: list[tuple[str, str]]) -> list[Document]:
    docs = [Document(name=name, text=text) for name, text in items if text.strip()]
    if not docs:
        raise CorpusError("no hay documentos con contenido")
    return docs


def _read(file: Path, root: Path) -> Document:
    text = file.read_text(encoding="utf-8", errors="replace")
    try:
        name = file.relative_to(root).as_posix()
    except ValueError:
        name = file.name
    return Document(name=name, text=text, path=str(file))
