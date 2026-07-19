import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KB_ROOT = ROOT / "data" / "knowledge_base"
KB_INDEX = KB_ROOT / "index.jsonl"


@dataclass
class RetrievedDocument:
    document_id: str
    title: str
    source_type: str
    score: float
    text: str
    path: str
    reason: str = ""
    metadata: dict | None = None


class KnowledgeBaseService:
    """Lightweight retrieval layer for HCP reports, debates, speeches, papers, and notes."""

    def add_document(self, title: str, text: str, source_type: str, path: str | None = None, metadata: dict | None = None) -> str:
        KB_ROOT.mkdir(parents=True, exist_ok=True)
        document_id = f"doc_{datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')}"
        doc_path = Path(path) if path else KB_ROOT / f"{document_id}.txt"
        if not path:
            doc_path.write_text(text)
        record = {
            "document_id": document_id,
            "title": title,
            "source_type": source_type,
            "path": str(doc_path),
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
        }
        with KB_INDEX.open("a") as handle:
            handle.write(json.dumps(record) + "\n")
        return document_id

    def index_existing_document(self, path: Path, source_type: str) -> str:
        return self.add_document(title=path.name, text=path.read_text(), source_type=source_type, path=str(path))

    def retrieve(self, query: str, limit: int = 5) -> list[RetrievedDocument]:
        if not KB_INDEX.exists():
            return []
        terms = {term.lower() for term in query.split() if len(term) > 2}
        results: list[RetrievedDocument] = []
        for line in KB_INDEX.read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            path = Path(record["path"])
            if not path.exists():
                continue
            text = path.read_text(errors="ignore")
            haystack = f"{record['title']} {text}".lower()
            hits = sum(1 for term in terms if term in haystack)
            if hits:
                matched_terms = sorted(term for term in terms if term in haystack)
                results.append(
                    RetrievedDocument(
                        document_id=record["document_id"],
                        title=record["title"],
                        source_type=record["source_type"],
                        score=hits / max(len(terms), 1),
                        text=text[:4000],
                        path=str(path),
                        reason=f"Matched terms: {', '.join(matched_terms[:8])}",
                        metadata=record.get("metadata", {}),
                    )
                )
        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]

    def retrieve_institutional_context(self, query: str, limit: int = 8) -> dict:
        docs = self.retrieve(query, limit=limit)
        buckets = {
            "similar_hcp_reports": [],
            "similar_macro_regimes": [],
            "similar_inflation_environments": [],
            "similar_central_bank_environments": [],
            "similar_growth_environments": [],
            "similar_investment_opportunities": [],
            "similar_failed_theses": [],
            "similar_successful_theses": [],
        }
        for doc in docs:
            payload = doc.__dict__
            text = f"{doc.title} {doc.text}".lower()
            buckets["similar_hcp_reports"].append(payload)
            if "regime" in text or "soft landing" in text or "risk-off" in text:
                buckets["similar_macro_regimes"].append(payload)
            if "inflation" in text or "disinflation" in text:
                buckets["similar_inflation_environments"].append(payload)
            if "fed" in text or "central bank" in text or "rates" in text:
                buckets["similar_central_bank_environments"].append(payload)
            if "growth" in text or "recession" in text:
                buckets["similar_growth_environments"].append(payload)
            if "opportunit" in text or "equity" in text or "duration" in text or "gold" in text:
                buckets["similar_investment_opportunities"].append(payload)
            if "failed" in text or "miss" in text or "mistake" in text:
                buckets["similar_failed_theses"].append(payload)
            if "successful" in text or "worked" in text or "hit" in text:
                buckets["similar_successful_theses"].append(payload)
        return buckets
