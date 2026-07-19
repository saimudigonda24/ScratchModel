from datetime import datetime
from pathlib import Path
from typing import Any

from app.models import FinalResearchOutput
from app.services.database import list_investment_committee_reports, save_investment_committee_report

ROOT = Path(__file__).resolve().parents[3]
IC_REPORT_DIR = ROOT / "reports" / "investment_committee"


def generate_investment_committee_report(
    run_id: str,
    result: FinalResearchOutput,
    retrieved_context: dict[str, Any] | None = None,
    lessons: list[dict] | None = None,
) -> dict:
    retrieved_context = retrieved_context or {}
    lessons = lessons or []
    thesis = result.thesis
    report = {
        "run_id": run_id,
        "generated_at": datetime.utcnow().isoformat(),
        "executive_summary": thesis.base_case.summary,
        "current_macro_thesis": thesis.title,
        "growth_outlook": _extract_signal(thesis, "growth"),
        "inflation_outlook": _extract_signal(thesis, "inflation"),
        "central_bank_expectations": _extract_signal(thesis, "fed") or _extract_signal(thesis, "rate"),
        "country_views": "See retrieved historical reports and current macro data signals.",
        "cross_asset_allocation": [item.name for item in result.ranked_opportunities[:5]],
        "ranked_opportunities": [item.model_dump(mode="json") for item in result.ranked_opportunities],
        "ranked_hedges": [item.model_dump(mode="json") for item in result.ranked_hedge_ideas],
        "risk_analysis": thesis.bear_tail_case.summary,
        "probability_distribution": result.probability_bands,
        "historical_hcp_reports_retrieved": retrieved_context.get("similar_hcp_reports", []),
        "lessons_learned_applied": lessons,
        "debate_summary": result.model_debate.judge_summary if result.model_debate else "",
        "changes_since_previous_report": thesis.change_log,
        "indicators_to_watch": [signal.model_dump(mode="json") for signal in thesis.key_signals],
        "confidence_score": result.conviction_score,
        "invalidation_conditions": result.triggers,
        "disclaimer": result.disclaimer,
    }
    markdown = _to_markdown(report)
    IC_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = IC_REPORT_DIR / f"{run_id}.md"
    path.write_text(markdown)
    save_investment_committee_report(run_id, f"Investment Committee Report {run_id}", report, markdown)
    return {"path": str(path), "report": report, "markdown": markdown}


def list_committee_reports(limit: int = 50) -> list[dict[str, Any]]:
    return list_investment_committee_reports(limit)


def _extract_signal(thesis, term: str) -> str:
    for signal in thesis.key_signals:
        if term in signal.name.lower() or term in signal.interpretation.lower():
            return signal.interpretation
    return thesis.base_case.summary


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# HCP Investment Committee Report",
        "",
        f"Run ID: {report['run_id']}",
        f"Generated: {report['generated_at']}",
        "",
    ]
    sections = [
        ("Executive Summary", report["executive_summary"]),
        ("Current Macro Thesis", report["current_macro_thesis"]),
        ("Growth Outlook", report["growth_outlook"]),
        ("Inflation Outlook", report["inflation_outlook"]),
        ("Central Bank Expectations", report["central_bank_expectations"]),
        ("Country Views", report["country_views"]),
        ("Cross-Asset Allocation", report["cross_asset_allocation"]),
        ("Ranked Opportunities", report["ranked_opportunities"]),
        ("Ranked Hedges", report["ranked_hedges"]),
        ("Risk Analysis", report["risk_analysis"]),
        ("Probability Distribution", report["probability_distribution"]),
        ("Historical HCP Reports Retrieved", report["historical_hcp_reports_retrieved"]),
        ("Lessons Learned Applied", report["lessons_learned_applied"]),
        ("Debate Summary", report["debate_summary"]),
        ("Changes Since Previous Report", report["changes_since_previous_report"]),
        ("Indicators To Watch", report["indicators_to_watch"]),
        ("Confidence Score", report["confidence_score"]),
        ("Invalidation Conditions", report["invalidation_conditions"]),
    ]
    for title, value in sections:
        lines.extend([f"## {title}", _render_value(value), ""])
    lines.extend(["## Disclaimer", report["disclaimer"], ""])
    return "\n".join(lines)


def _render_value(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return "None recorded."
        return "\n".join(f"- {item}" for item in value)
    if isinstance(value, dict):
        return "\n".join(f"- {key}: {item}" for key, item in value.items())
    return str(value)
