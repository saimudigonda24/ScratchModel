from app.services.database import list_investment_committee_reports
from app.services.scenario_presentation import (
    DEMO_SCENARIO,
    data_mode_label,
    generate_presentation_outlook,
    outlook_to_markdown,
    safe_generate_presentation_outlook,
)


class FakeSnapshot:
    def model_dump(self, mode="json"):
        return {
            "signals": [
                {
                    "source": "FRED",
                    "name": "Inflation signal",
                    "value": "firm",
                    "as_of": "2026-08-06",
                    "direction": "deteriorating",
                    "interpretation": "Inflation remains firm.",
                }
            ],
            "source_status": {"FRED": "ok: 1 signals", "Yahoo Finance": "ok: 1 signals"},
        }


def test_scenario_submission_generates_presentation_outlook(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())

    outlook = generate_presentation_outlook(DEMO_SCENARIO, sequence_name="Presentation Test", demo=True)

    assert outlook["status"] == "ok"
    assert outlook["demo"] is True
    assert "Executive" not in outlook["executive_outlook"]
    assert outlook["base_case"]["probability"] == DEMO_SCENARIO["probability"]
    assert len(outlook["cross_asset_outlook"]) == 11
    assert outlook["top_opportunities"]
    assert outlook["recommended_hedges"]
    assert outlook["data_to_watch_next"]


def test_final_outlook_formatting_and_markdown_export(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())
    outlook = generate_presentation_outlook(DEMO_SCENARIO, sequence_name="Markdown Presentation Test", demo=True)
    markdown = outlook_to_markdown(outlook)

    required_sections = [
        "Executive Summary",
        "Scenario Definition",
        "Macro Outlook",
        "Central Bank Outlook",
        "Historical Analogs",
        "Cross-Asset Allocation",
        "Ranked Opportunities",
        "Ranked Hedges",
        "Invalidation Conditions",
        "Indicators to Watch",
        "Conclusion",
    ]
    for section in required_sections:
        assert f"## {section}" in markdown
    assert "Research hypotheses" in markdown


def test_investment_committee_report_retrieval(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())
    outlook = generate_presentation_outlook(DEMO_SCENARIO, sequence_name="IC Retrieval Test", demo=True)

    reports = list_investment_committee_reports()

    matching = [row for row in reports if row["run_id"] == outlook["run_id"]]
    assert matching
    assert "Executive Summary" in matching[0]["markdown"]


def test_live_and_fallback_data_mode_labels():
    assert data_mode_label({"source_status": {"FRED": "ok: 1 signals"}}) == "Live Data Mode"
    assert data_mode_label({"source_status": {"FRED": "unavailable: 1/1 signals"}}).startswith("Demo Mode")
    assert data_mode_label({}).startswith("Demo Mode")


def test_duplicate_free_opportunity_display(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())
    outlook = generate_presentation_outlook(DEMO_SCENARIO, sequence_name="Dedupe Presentation Test", demo=True)

    keys = [(row["name"], row["direction"], row["expected_horizon"]) for row in outlook["top_opportunities"]]

    assert len(keys) == len(set(keys))


def test_scenario_api_failure_is_graceful(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("presentation failure")

    monkeypatch.setattr("app.services.scenario_presentation.generate_presentation_outlook", boom)

    response = safe_generate_presentation_outlook(DEMO_SCENARIO)

    assert response["status"] == "not_ready"
    assert response["reason"] == "scenario_outlook_generation_failed"
    assert response["warnings"]
