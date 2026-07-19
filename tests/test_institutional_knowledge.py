import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.models import CaseView, DataSignal, FinalResearchOutput, MacroThesis
from app.services.historical_outcome_linker import link_historical_outcome
from app.services.institutional_importer import approve_and_index_document, import_historical_document
from app.services.institutional_readiness import institutional_readiness_report
from app.services.investment_committee_report import generate_investment_committee_report
from app.services.knowledge_base import KnowledgeBaseService


def test_historical_document_import_parse_approve_and_retrieve(tmp_path: Path):
    report = tmp_path / "sample_hcp_report.md"
    report.write_text(
        """
# HCP Macro Report
Author: HCP Team
2024-01-15

Macro Thesis
Disinflation and slowing growth create a two-sided Fed reaction function.

Growth Outlook
Growth should slow but avoid a deep recession.

Inflation Outlook
Inflation should cool over the next 7-14 months.

Opportunities
- Quality equities
- Intermediate duration

Hedges
- Gold

Risks
- Inflation re-acceleration

What Would Change My Mind
- Payroll acceleration
""".strip()
    )
    imported = import_historical_document(
        report,
        metadata={"publication_date": "2024-01-15", "author": "HCP Team", "report_type": "macro_report"},
    )
    assert imported["ingestion_status"] == "pending_approval"
    assert imported["structured"]["growth_outlook"]
    approved = approve_and_index_document(imported["document_id"])
    assert approved["ingestion_status"] == "approved"
    retrieved = KnowledgeBaseService().retrieve_institutional_context("disinflation fed quality equities")
    assert retrieved["similar_hcp_reports"]
    assert retrieved["similar_hcp_reports"][0]["reason"]


def test_historical_outcome_link_and_institutional_readiness(tmp_path: Path):
    report = tmp_path / "outcome_report.txt"
    report.write_text(
        """
HCP Outcome Test
2023-03-01
Macro Thesis
The thesis is uncertain and requires hedges because recession risk is rising.
Opportunities
- Duration
Hedges
- Gold
Risks
- Credit stress
Probability
Base case 60%
""".strip()
    )
    imported = import_historical_document(report, metadata={"publication_date": "2023-03-01"}, approve=True)
    postmortem = link_historical_outcome(imported["document_id"])
    assert postmortem["payload"]["thesis_correct"] is True
    readiness = institutional_readiness_report()
    assert readiness["historical_hcp_reports_imported"] >= 1
    assert readiness["reports_linked_to_outcomes"] >= 1


def test_investment_committee_report_generation():
    signal = DataSignal(
        source="test",
        name="inflation",
        value="cooling",
        as_of="2024-01-01",
        direction="improving",
        interpretation="Inflation is cooling.",
    )
    thesis = MacroThesis(
        title="Soft landing with disinflation",
        base_case=CaseView(label="base", summary="Base case summary", probability=0.6, evidence=["Inflation cooling"]),
        bull_case=CaseView(label="bull", summary="Bull case", probability=0.2, evidence=["Growth improves"]),
        bear_tail_case=CaseView(label="bear_tail", summary="Bear case", probability=0.2, evidence=["Credit stress"]),
        key_signals=[signal],
        triggers=["Inflation re-accelerates"],
        change_log=["Initial report"],
    )
    output = FinalResearchOutput(
        thesis=thesis,
        probability_bands={"base_case": "60%", "bull_case": "20%", "bear_tail_case": "20%"},
        conviction_score=7,
        ranked_opportunities=[],
        asymmetric_hedges=[],
        ranked_hedge_ideas=[],
        evidence=["Inflation cooling"],
        triggers=["Inflation re-accelerates"],
        debate_notes=["Debate complete"],
        source_status={"test": "ok"},
    )
    report = generate_investment_committee_report("ic_test_run", output, {"similar_hcp_reports": []}, [])
    assert "Executive Summary" in report["markdown"]
    assert report["report"]["confidence_score"] == 7
