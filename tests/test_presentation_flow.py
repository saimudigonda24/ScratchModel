from app.services.database import list_investment_committee_reports
from app.services.scenario_presentation import (
    DEMO_SCENARIO,
    data_mode_label,
    generate_presentation_outlook,
    outlook_to_markdown,
    parse_free_text_scenario,
    safe_generate_presentation_outlook,
    scenario_input_options,
    scenario_summary,
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
    assert data_mode_label({"source_status": {"FRED": "Live Data Mode - FRED connected"}}) == "Live Data Mode - FRED connected"
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


def test_free_text_scenario_parsing_extracts_assumptions():
    parsed = parse_free_text_scenario("Inflation surprises higher, growth remains strong, and the Fed delays tightening.")

    assert parsed["growth_outlook"] == "strong acceleration"
    assert parsed["inflation_surprise"] == "large upside surprise"
    assert parsed["fed_position"] == "behind the curve"
    assert parsed["central_bank_stance"] == "gradually tightening"


def test_presets_expose_expected_defaults():
    presets = scenario_input_options()["presets"]

    assert presets["Fed Overtightening / Recession"]["recession_probability"] >= 0.7
    assert presets["Credit Stress Event"]["credit_stress"] == 9
    assert presets["Dollar Squeeze"]["dollar_outlook"] == "sharply stronger"


def test_scenario_summary_formatting():
    summary = scenario_summary(
        {
            **DEMO_SCENARIO,
            "growth_outlook": "slowing growth",
            "market_volatility": "high",
            "credit_stress": 8,
            "dollar_outlook": "sharply stronger",
            "countries_or_regions": ["U.S.", "Eurozone"],
        }
    )

    assert summary["growth"] == "slowing growth"
    assert summary["volatility"] == "high"
    assert summary["credit stress"] == 8
    assert summary["countries"] == "U.S., Eurozone"


def test_slider_dropdown_values_reach_backend_and_persist(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())
    scenario = {
        **DEMO_SCENARIO,
        "scenario_name": "Persistence Test Scenario",
        "recession_probability": 0.82,
        "market_volatility": "crisis",
        "credit_stress": 9,
        "dollar_outlook": "sharply stronger",
        "commodity_shock": "broad commodity shock",
        "countries_or_regions": ["U.S.", "India"],
    }

    outlook = generate_presentation_outlook(scenario, sequence_name="Persistence Controls Test")

    definition = outlook["scenario_definition"]
    assert definition["market_volatility"] == "crisis"
    assert definition["credit_stress"] == 9
    assert definition["dollar_outlook"] == "sharply stronger"
    assert definition["commodity_shock"] == "broad commodity shock"
    assert definition["countries_or_regions"] == ["U.S.", "India"]


def test_recommendations_change_with_recession_volatility_and_fed_stance(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())
    benign = generate_presentation_outlook(
        {
            **DEMO_SCENARIO,
            "scenario_name": "Benign Scenario",
            "recession_probability": 0.15,
            "market_volatility": "low",
            "central_bank_stance": "gradually easing",
            "fed_position": "roughly on time",
            "financial_conditions": "loose",
            "credit_stress": 1,
            "commodity_shock": "none",
        },
        sequence_name="Sensitivity Test Benign",
    )
    stress = generate_presentation_outlook(
        {
            **DEMO_SCENARIO,
            "scenario_name": "Stress Scenario",
            "recession_probability": 0.8,
            "market_volatility": "crisis",
            "central_bank_stance": "aggressively tightening",
            "fed_position": "ahead of the curve",
            "financial_conditions": "severely tight",
            "credit_stress": 9,
            "dollar_outlook": "sharply stronger",
        },
        sequence_name="Sensitivity Test Stress",
    )

    benign_names = {row["name"] for row in benign["top_opportunities"]}
    stress_names = {row["name"] for row in stress["top_opportunities"]}
    stress_hedges = {row["hedge_name"] for row in stress["recommended_hedges"]}

    assert "Short high-yield credit / own quality credit" in stress_names
    assert "Long equity volatility" in stress_hedges
    assert benign_names != stress_names
    assert stress["bear_tail_case"]["probability"] > benign["bear_tail_case"]["probability"]
