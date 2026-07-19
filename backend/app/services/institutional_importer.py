import hashlib
import re
from datetime import datetime
from email import message_from_string
from pathlib import Path
from typing import Any

from app.services.database import (
    approve_institutional_document,
    mark_document_memory_indexed,
    save_institutional_document,
)
from app.services.knowledge_base import KnowledgeBaseService

ROOT = Path(__file__).resolve().parents[3]
DOCUMENT_STORE = ROOT / "data" / "institutional_documents"


STRUCTURED_FIELDS = [
    "macro_thesis",
    "growth_outlook",
    "inflation_outlook",
    "central_bank_expectations",
    "country_views",
    "opportunities",
    "hedges",
    "risks",
    "conviction",
    "probability_estimates",
    "invalidation_triggers",
    "indicators_being_monitored",
    "conclusion",
]


def import_historical_document(path: Path, metadata: dict[str, Any] | None = None, approve: bool = False) -> dict:
    metadata = metadata or {}
    text, parser_status = extract_document_text(path)
    title = metadata.get("title") or _title_from_text(text) or path.stem
    publication_date = metadata.get("publication_date") or _date_from_text(text) or datetime.utcnow().date().isoformat()
    author = metadata.get("author") or _author_from_text(text)
    report_type = metadata.get("report_type") or _report_type_from_text(text)
    document_id = _document_id(path, publication_date, title)
    stored_path = _store_original(path, document_id)
    structured = parse_hcp_report_fields(text)
    structured.update(
        {
            "title": title,
            "author": author,
            "publication_date": publication_date,
            "report_type": report_type,
            "original_source": metadata.get("original_source", str(path)),
        }
    )
    record = save_institutional_document(
        {
            "document_id": document_id,
            "title": title,
            "author": author,
            "publication_date": publication_date,
            "report_type": report_type,
            "original_source": metadata.get("original_source", str(path)),
            "source_path": str(stored_path),
            "original_text": text,
            "structured": structured,
            "parser_status": parser_status,
            "ingestion_status": "approved" if approve else "pending_approval",
            "memory_indexed": False,
            "outcome_linked": False,
        }
    )
    if approve:
        approve_and_index_document(document_id)
        record = approve_institutional_document(document_id)
    return record


def approve_and_index_document(document_id: str) -> dict:
    doc = approve_institutional_document(document_id)
    if doc:
        KnowledgeBaseService().add_document(
            title=doc["title"],
            text=doc["original_text"],
            source_type="historical_hcp_report",
            path=doc["source_path"],
            metadata={
                "document_id": document_id,
                "publication_date": doc["publication_date"],
                "author": doc.get("author"),
                "report_type": doc.get("report_type"),
            },
        )
        mark_document_memory_indexed(document_id, True)
    return doc


def extract_document_text(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt", ".eml"}:
        raw = path.read_text(errors="ignore")
        if suffix == ".eml":
            msg = message_from_string(raw)
            return msg.get_payload() if isinstance(msg.get_payload(), str) else raw, "parsed_email"
        return raw, "parsed_text"
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages), "parsed_pdf"
        except Exception as exc:
            return f"[PDF parser unavailable: {exc}] {path.name}", "parser_unavailable_pdf"
    if suffix == ".docx":
        try:
            import zipfile
            import xml.etree.ElementTree as ET

            with zipfile.ZipFile(path) as docx:
                xml = docx.read("word/document.xml")
            root = ET.fromstring(xml)
            words = [node.text for node in root.iter() if node.text]
            return " ".join(words), "parsed_docx"
        except Exception as exc:
            return f"[DOCX parser unavailable: {exc}] {path.name}", "parser_unavailable_docx"
    return path.read_text(errors="ignore"), "parsed_unknown_text"


def parse_hcp_report_fields(text: str) -> dict[str, Any]:
    structured = {field: "" for field in STRUCTURED_FIELDS}
    aliases = {
        "macro_thesis": ["macro thesis", "thesis"],
        "growth_outlook": ["growth outlook", "growth view", "u.s. growth"],
        "inflation_outlook": ["inflation outlook", "inflation view", "u.s. inflation"],
        "central_bank_expectations": ["central bank", "fed", "reaction function"],
        "country_views": ["country views", "country overlays", "global"],
        "opportunities": ["opportunities", "assets i think could benefit", "beneficiaries"],
        "hedges": ["hedges", "hedge"],
        "risks": ["risks", "risks to the thesis"],
        "conviction": ["conviction"],
        "probability_estimates": ["probability", "probabilities"],
        "invalidation_triggers": ["invalidation", "what would change my mind"],
        "indicators_being_monitored": ["indicators", "watch", "monitor"],
        "conclusion": ["conclusion", "summary"],
    }
    sections = _split_sections(text)
    for field, names in aliases.items():
        for heading, body in sections.items():
            if any(name in heading for name in names):
                structured[field] = body.strip()
                break
    if not structured["macro_thesis"]:
        structured["macro_thesis"] = text.strip()[:800]
    structured["opportunities"] = _as_list(structured["opportunities"])
    structured["hedges"] = _as_list(structured["hedges"])
    structured["risks"] = _as_list(structured["risks"])
    structured["invalidation_triggers"] = _as_list(structured["invalidation_triggers"])
    structured["indicators_being_monitored"] = _as_list(structured["indicators_being_monitored"])
    return structured


def _split_sections(text: str) -> dict[str, str]:
    heading_pattern = re.compile(r"(?im)^(#{1,4}\s*)?([A-Z][A-Za-z0-9 .,/&-]{2,80}):?\s*$")
    matches = []
    for match in heading_pattern.finditer(text):
        heading = match.group(2).strip()
        if heading.endswith("."):
            continue
        if len(heading.split()) > 8:
            continue
        matches.append(match)
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(2).strip().lower()] = text[start:end].strip()
    return sections


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    rows = [row.strip(" -\t") for row in str(value).splitlines() if row.strip(" -\t")]
    return rows or [str(value).strip()]


def _store_original(path: Path, document_id: str) -> Path:
    DOCUMENT_STORE.mkdir(parents=True, exist_ok=True)
    destination = DOCUMENT_STORE / f"{document_id}{path.suffix.lower() or '.txt'}"
    destination.write_bytes(path.read_bytes())
    return destination


def _document_id(path: Path, publication_date: str, title: str) -> str:
    digest = hashlib.sha256(f"{path.resolve()}:{publication_date}:{title}".encode()).hexdigest()[:16]
    return f"hcp_doc_{digest}"


def _title_from_text(text: str) -> str | None:
    for line in text.splitlines()[:10]:
        clean = line.strip("# ").strip()
        if len(clean) > 8:
            return clean[:120]
    return None


def _date_from_text(text: str) -> str | None:
    match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return None


def _author_from_text(text: str) -> str | None:
    match = re.search(r"(?im)^author:\s*(.+)$", text)
    return match.group(1).strip() if match else None


def _report_type_from_text(text: str) -> str:
    lower = text.lower()
    if "investment committee" in lower:
        return "investment_committee"
    if "macro" in lower:
        return "macro_report"
    return "hcp_report"
