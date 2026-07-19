import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.knowledge_base import KnowledgeBaseService


def test_knowledge_base_indexes_and_retrieves():
    kb = KnowledgeBaseService()
    kb.add_document("Fed inflation note", "Inflation is cooling while labor demand slows.", "test_note")

    results = kb.retrieve("inflation labor", limit=3)

    assert results
    assert results[0].score > 0

