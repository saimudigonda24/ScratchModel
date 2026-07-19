from app.services.database import (
    get_institutional_document,
    list_historical_postmortems,
    save_historical_postmortem,
)
from app.services.institutional_memory import generate_lessons_learned


def link_historical_outcome(document_id: str) -> dict:
    doc = get_institutional_document(document_id)
    if not doc:
        raise ValueError(f"Unknown institutional document: {document_id}")
    structured = doc.get("structured", {})
    opportunities = structured.get("opportunities") or []
    hedges = structured.get("hedges") or []
    risks = structured.get("risks") or []
    probability_text = str(structured.get("probability_estimates") or "")
    thesis_text = str(structured.get("macro_thesis") or "")
    thesis_correct = _heuristic_thesis_correct(thesis_text, risks)
    payload = {
        "document_id": document_id,
        "publication_date": doc["publication_date"],
        "title": doc["title"],
        "what_actually_happened": "Outcome linked with available structured fields; replace with realized market attribution as data coverage expands.",
        "thesis_correct": thesis_correct,
        "opportunities_outperformed": bool(opportunities) and thesis_correct,
        "hedges_worked": bool(hedges) and bool(risks),
        "probability_calibration": _probability_calibration_label(probability_text, thesis_correct),
        "mistakes": [] if thesis_correct else ["Thesis requires stronger disconfirming evidence and outcome attribution."],
        "successful_patterns": ["Clear opportunities and risks stated together."] if opportunities and risks else [],
        "recurring_errors": ["Missing explicit probability estimates."] if not probability_text else [],
        "lessons_learned": [
            "Historical report was converted into searchable institutional memory.",
            "Future runs should compare current thesis against this document before changing regime views.",
        ],
    }
    saved = save_historical_postmortem(document_id, payload)
    generate_lessons_learned(min_count=2)
    return saved


def list_linked_historical_outcomes(limit: int = 100) -> list[dict]:
    return list_historical_postmortems(limit)


def _heuristic_thesis_correct(thesis: str, risks: list | str) -> bool:
    text = f"{thesis} {risks}".lower()
    if any(term in text for term in ["uncertain", "two-sided", "range", "risk", "hedge"]):
        return True
    return len(thesis) > 120


def _probability_calibration_label(probability_text: str, thesis_correct: bool) -> str:
    if not probability_text:
        return "not_available"
    if thesis_correct:
        return "directionally_calibrated"
    return "needs_review"
