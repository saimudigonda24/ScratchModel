from app.services.database import list_investment_committee_reports
from app.services.scenario_presentation import (
    DEMO_SCENARIO,
    confirm_structured_scenario,
    data_mode_label,
    generate_presentation_outlook,
    outlook_to_markdown,
    parse_free_text_scenario,
    safe_generate_presentation_outlook,
    scenario_input_options,
    scenario_summary,
    validate_confirmed_scenario,
)
from app.services.ollama_provider import OllamaParseResult


MANAGER_SCENARIO = (
    "Over the next 12 months, inflation begins to rise again because energy prices increase and wage growth remains strong. "
    "The U.S. economy continues to grow, but at a slower pace than before. The Federal Reserve believes inflation will be temporary "
    "and delays raising interest rates. Financial markets remain calm at first, but investors become increasingly concerned that the Fed "
    "is falling behind the curve. Treasury yields gradually rise, the U.S. dollar strengthens, and commodity prices continue to increase. "
    "Equity markets remain positive early in the year but become more volatile as expectations for higher interest rates grow. "
    "Credit spreads stay relatively contained, and unemployment remains low. Assume there is a 30% probability that the economy eventually "
    "falls into recession if the Fed has to tighten policy aggressively later."
)

SCENARIO_A = (
    "Inflation rises again because energy prices and wages increase, growth remains positive but slows, "
    "the Fed delays tightening, unemployment remains low, the dollar strengthens, and volatility rises later."
)

SCENARIO_B = (
    "Inflation cools, growth weakens, unemployment rises, credit conditions tighten, the Fed cuts earlier and faster, "
    "Treasury yields fall, the dollar weakens, defensive equities outperform, high yield underperforms, and gold benefits. "
    "Mild recession: 45%, soft landing: 35%, deep downturn: 20%."
)

SOFT_LANDING_EASING_SCENARIO = (
    "Over the next 10 months, the U.S. economy avoids recession, but growth remains uneven. "
    "Consumer spending holds up, while manufacturing and housing stay weak. Inflation continues to decline gradually, "
    "allowing the Federal Reserve to begin cutting rates slowly, but not aggressively. The labor market cools without collapsing, "
    "credit spreads remain contained, and financial conditions ease modestly. The U.S. dollar weakens somewhat as rate differentials narrow, "
    "while gold and long-duration bonds benefit from lower real yields. Large-cap quality equities continue to outperform, "
    "but small caps and highly leveraged companies remain vulnerable. Assume a 55% probability of a soft landing, "
    "a 25% probability of renewed inflation that delays rate cuts, and a 20% probability of a mild recession."
)

FISCAL_SUPPLY_SHOCK_SCENARIO = {
    "scenario_name": "Fiscal Stimulus Meets Supply Shock",
    "scenario_description": "Fiscal stimulus meets tariffs and supply constraints in a higher-inflation environment.",
    "growth_outlook": "moderate growth",
    "inflation_direction": "moderately higher",
    "inflation_surprise": "large upside surprise",
    "central_bank_stance": "gradually tightening",
    "expected_policy_path": "The Fed tightens gradually at first but risks falling behind the curve.",
    "fed_position": "behind the curve",
    "labor_market": "strong",
    "financial_conditions": "tight",
    "market_volatility": "high",
    "credit_stress": 4,
    "dollar_outlook": "moderately stronger",
    "commodity_shock": "broad commodity shock",
    "equity_valuation": "expensive",
    "time_horizon": "6-12 months",
    "recession_probability": 0.20,
    "probability": 0.50,
    "countries_or_regions": ["U.S.", "Eurozone", "China", "emerging markets"],
    "custom_assumptions": (
        "fiscal stimulus supports infrastructure and defense; tariffs and supply constraints keep inflation elevated; "
        "energy and industrial metals rise; China adds targeted stimulus; Europe weakens due to higher energy costs; "
        "defense, industrials, infrastructure, energy outperform; utilities, REITs, and long-duration technology underperform; "
        "gold is weak initially due to higher real yields, then stabilizes as geopolitical risk rises"
    ),
    "risks": ["Fed overtightening risk if delayed tightening later becomes aggressive."],
    "invalidation_triggers": ["Inflation rolls over and energy and industrial metals reverse lower."],
}


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
    assert len(outlook["cross_asset_outlook"]) == 21
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
        "Cross-Asset Outlook",
        "Ranked Opportunities",
        "Ranked Hedges",
        "Underweights / Positions to Avoid",
        "Risk Register",
        "Decisions for the Investment Committee",
        "Invalidation Conditions",
        "Indicators to Watch",
    ]
    for section in required_sections:
        assert f"## {section}" in markdown
    assert "Research hypotheses" in markdown


def test_investment_committee_report_retrieval(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())
    outlook = generate_presentation_outlook(DEMO_SCENARIO, sequence_name="IC Retrieval Test", demo=True)

    reports = list_investment_committee_reports(limit=500)

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
    parsed = parse_free_text_scenario("Inflation surprises higher, growth remains strong, and the Fed delays tightening.", force_rule_fallback=True)

    assert parsed["growth_outlook"] == "strong acceleration"
    assert parsed["inflation_surprise"] == "large upside surprise"
    assert parsed["fed_position"] == "behind the curve"
    assert parsed["central_bank_stance"] == "gradually tightening"


def test_manager_scenario_parses_as_inflation_surprise_behind_curve():
    parsed = parse_free_text_scenario(MANAGER_SCENARIO, force_rule_fallback=True)

    assert parsed["scenario_name"] == "Inflation Surprise / Fed Behind the Curve"
    assert parsed["growth_outlook"] in {"moderate growth", "slowing growth"}
    assert parsed["inflation_direction"] == "moderately higher"
    assert parsed["inflation_surprise"] == "small upside surprise"
    assert parsed["central_bank_stance"] == "gradually tightening"
    assert parsed["fed_position"] == "behind the curve"
    assert parsed["labor_market"] == "strong"
    assert parsed["financial_conditions"] == "neutral"
    assert parsed["market_volatility"] == "high"
    assert parsed["credit_stress"] == 3
    assert parsed["dollar_outlook"] == "moderately stronger"
    assert parsed["commodity_shock"] == "energy shock"
    assert parsed["equity_valuation"] == "fair"
    assert parsed["time_horizon"] == "6-12 months"
    assert parsed["recession_probability"] == 0.30
    assert parsed["probability"] is None
    assert parsed["field_confidence"]["recession_probability"] == 1.0
    assert not parsed["parser_warnings"]


def test_explicit_percentage_preserved_without_invented_scenario_probability():
    parsed = parse_free_text_scenario("Assume a 30% probability that the economy falls into recession.", force_rule_fallback=True)

    assert parsed["recession_probability"] == 0.30
    assert parsed["probability"] is None
    assert scenario_summary(parsed)["scenario probability"] == "not specified"


def test_phased_volatility_language_is_high_not_crisis():
    parsed = parse_free_text_scenario("Markets remain calm at first, then become more volatile as rates rise.", force_rule_fallback=True)

    assert parsed["market_volatility"] == "high"
    assert parsed["phases"][0]["market_volatility"] == "normal"
    assert parsed["phases"][1]["market_volatility"] == "high"


def test_slowing_but_positive_growth_is_not_recession():
    parsed = parse_free_text_scenario("The U.S. economy continues to grow, but at a slower pace than before.", force_rule_fallback=True)

    assert parsed["growth_outlook"] == "slowing growth"


def test_contained_credit_spreads_are_not_severe_stress():
    parsed = parse_free_text_scenario("Credit spreads stay relatively contained.", force_rule_fallback=True)

    assert parsed["financial_conditions"] == "neutral"
    assert parsed["credit_stress"] == 3


def test_energy_driven_inflation_sets_energy_shock():
    parsed = parse_free_text_scenario("Inflation begins to rise again because energy prices increase.", force_rule_fallback=True)

    assert parsed["inflation_direction"] == "moderately higher"
    assert parsed["commodity_shock"] == "energy shock"


def test_behind_curve_is_not_overtightening():
    parsed = parse_free_text_scenario("The Fed believes inflation is temporary and delays raising interest rates, falling behind the curve.", force_rule_fallback=True)

    assert parsed["fed_position"] == "behind the curve"
    assert parsed["central_bank_stance"] == "gradually tightening"


def test_ollama_parser_accepts_valid_structured_json(monkeypatch):
    payload = {
        "scenario_name": "Local Parsed Scenario A",
        "scenario_description": SCENARIO_A,
        "growth_outlook": "slowing growth",
        "inflation_direction": "moderately higher",
        "inflation_surprise": "small upside surprise",
        "central_bank_stance": "gradually tightening",
        "expected_policy_path": "The Fed delays tightening.",
        "fed_position": "behind the curve",
        "labor_market": "strong",
        "financial_conditions": "neutral",
        "market_volatility": "high",
        "credit_stress": 3,
        "dollar_outlook": "moderately stronger",
        "commodity_shock": "energy shock",
        "equity_valuation": "fair",
        "time_horizon": "7-14 months",
        "countries": ["U.S."],
        "custom_regions": [],
        "risks": ["Fed falls behind the curve."],
        "invalidation_triggers": ["Energy prices fall."],
        "confirming_indicators": ["Energy and wages rise."],
        "stated_probabilities": {},
        "parser_confidence": 0.88,
        "field_confidence": {"growth_outlook": 0.9},
        "field_excerpts": {"growth_outlook": "growth remains positive but slows"},
        "contradiction_warnings": [],
        "phases": [
            {"name": "Initial phase", "market_volatility": "normal"},
            {"name": "Later phase", "market_volatility": "high"},
        ],
    }
    monkeypatch.setenv("HCP_SCENARIO_PARSER_PROVIDER", "ollama")
    monkeypatch.setattr(
        "app.services.scenario_presentation.OllamaProvider.parse_scenario",
        lambda self, text: OllamaParseResult(True, payload, "llama3.1:8b", 120, None),
    )

    parsed = parse_free_text_scenario(SCENARIO_A)

    assert parsed["parser_provider"] == "ollama"
    assert parsed["parser_model"] == "llama3.1:8b"
    assert parsed["growth_outlook"] == "slowing growth"
    assert parsed["phases"][1]["market_volatility"] == "high"


def test_ollama_unavailable_falls_back_with_provenance(monkeypatch):
    monkeypatch.setenv("HCP_SCENARIO_PARSER_PROVIDER", "ollama")
    monkeypatch.setattr(
        "app.services.scenario_presentation.OllamaProvider.parse_scenario",
        lambda self, text: OllamaParseResult(False, None, "llama3.1:8b", 50, "connection refused"),
    )

    try:
        parse_free_text_scenario(SCENARIO_A)
    except RuntimeError as exc:
        assert "connection refused" in str(exc)
    else:
        raise AssertionError("Ollama failure should require explicit fallback")


def test_regression_scenario_a_core_fields():
    parsed = parse_free_text_scenario(SCENARIO_A, force_rule_fallback=True)

    assert parsed["growth_outlook"] == "slowing growth"
    assert parsed["inflation_direction"] == "moderately higher"
    assert parsed["inflation_surprise"] == "small upside surprise"
    assert parsed["labor_market"] == "strong"
    assert parsed["fed_position"] == "behind the curve"
    assert parsed["commodity_shock"] == "energy shock"
    assert parsed["dollar_outlook"] == "moderately stronger"
    assert parsed["phases"][0]["market_volatility"] == "normal"
    assert parsed["phases"][1]["market_volatility"] == "high"


def test_regression_scenario_b_core_fields_and_probabilities():
    parsed = parse_free_text_scenario(SCENARIO_B, force_rule_fallback=True)

    assert parsed["growth_outlook"] == "slowing growth"
    assert parsed["inflation_direction"] == "disinflation"
    assert parsed["labor_market"] in {"cooling", "weak"}
    assert parsed["financial_conditions"] == "tight"
    assert parsed["central_bank_stance"] == "gradually easing"
    assert parsed["dollar_outlook"] == "moderately weaker"
    assert parsed["commodity_shock"] == "none"
    assert parsed["stated_probabilities"] == {"mild_recession": 0.45, "soft_landing": 0.35, "deep_downturn": 0.2}


def soft_landing_ollama_payload() -> dict:
    return {
        "scenario_name": "Soft Landing / Gradual Fed Easing",
        "scenario_description": SOFT_LANDING_EASING_SCENARIO,
        "growth_outlook": "slowing growth",
        "inflation_direction": "disinflation",
        "inflation_surprise": "small downside surprise",
        "central_bank_stance": "gradually easing",
        "expected_policy_path": "The Federal Reserve begins cutting rates slowly, but not aggressively.",
        "fed_position": "roughly on time",
        "labor_market": "cooling",
        "financial_conditions": "loose",
        "market_volatility": "normal",
        "credit_stress": 2,
        "dollar_outlook": "moderately weaker",
        "commodity_shock": "none",
        "equity_valuation": None,
        "time_horizon": "6-12 months",
        "countries": ["U.S."],
        "custom_regions": [],
        "risks": ["Renewed inflation delays rate cuts.", "Mild recession risk remains."],
        "confirming_indicators": ["Inflation continues to decline.", "Credit spreads remain contained."],
        "invalidation_triggers": ["Inflation reaccelerates.", "Credit spreads widen materially."],
        "stated_probabilities": {"soft_landing": 0.55, "renewed_inflation": 0.25, "mild_recession": 0.2},
        "phases": [],
        "parser_confidence": 0.92,
        "field_confidence": {
            "growth_outlook": 0.86,
            "inflation_direction": 0.95,
            "central_bank_stance": 0.95,
            "dollar_outlook": 0.9,
        },
        "supporting_text_by_field": {
            "growth_outlook": "growth remains uneven",
            "inflation_direction": "Inflation continues to decline gradually",
            "central_bank_stance": "begin cutting rates slowly",
            "dollar_outlook": "U.S. dollar weakens somewhat",
        },
        "contradiction_warnings": [],
    }


def test_soft_landing_gradual_easing_ollama_regression(monkeypatch):
    monkeypatch.setenv("HCP_SCENARIO_PARSER_PROVIDER", "ollama")
    monkeypatch.setattr(
        "app.services.scenario_presentation.OllamaProvider.parse_scenario",
        lambda self, text: OllamaParseResult(True, soft_landing_ollama_payload(), "llama3.1:8b", 140, None),
    )

    parsed = parse_free_text_scenario(SOFT_LANDING_EASING_SCENARIO)

    assert parsed["parser_provider"] == "ollama"
    assert parsed["parser_model"] == "llama3.1:8b"
    assert parsed["scenario_name"] == "Soft Landing / Gradual Fed Easing"
    assert parsed["growth_outlook"] == "slowing growth"
    assert parsed["inflation_direction"] == "disinflation"
    assert parsed["central_bank_stance"] == "gradually easing"
    assert parsed["fed_position"] == "roughly on time"
    assert parsed["labor_market"] == "cooling"
    assert parsed["financial_conditions"] == "loose"
    assert parsed["market_volatility"] == "normal"
    assert parsed["credit_stress"] == 2
    assert parsed["dollar_outlook"] == "moderately weaker"
    assert parsed["commodity_shock"] == "none"
    assert parsed["time_horizon"] == "6-12 months"
    assert parsed["stated_probabilities"] == {"soft_landing": 0.55, "renewed_inflation": 0.25, "mild_recession": 0.2}
    assert parsed["supporting_text_by_field"]["inflation_direction"] == "Inflation continues to decline gradually"


def test_confirmation_hash_rejects_stale_state():
    parsed = parse_free_text_scenario(SCENARIO_A, force_rule_fallback=True)
    confirmed = confirm_structured_scenario(parsed)
    assert validate_confirmed_scenario(confirmed) is None

    tampered = {**confirmed, "growth_outlook": "recession"}
    assert "changed after confirmation" in validate_confirmed_scenario(tampered)


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
            "parser_provider": "ollama",
            "parser_model": "llama3.1:8b",
            "scenario_id": "scenario_visible_test",
            "scenario_hash": "abc123hash",
        }
    )

    assert summary["parser provider"] == "ollama"
    assert summary["parser model"] == "llama3.1:8b"
    assert summary["scenario ID"] == "scenario_visible_test"
    assert summary["scenario hash"] == "abc123hash"
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


def test_manager_scenario_final_output_sections_are_non_empty(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())
    parsed = parse_free_text_scenario(MANAGER_SCENARIO, force_rule_fallback=True)

    outlook = generate_presentation_outlook(parsed, sequence_name="Manager Parser Regression Test")

    assert outlook["cross_asset_outlook"]
    assert outlook["top_opportunities"]
    assert outlook["recommended_hedges"]
    assert outlook["scenario_definition"]["risks"]
    assert outlook["what_would_change_the_view"]["invalidating_indicators"]
    assert outlook["historical_analogs"]
    markdown = outlook_to_markdown(outlook)
    assert "Not enough information to populate this section." not in markdown


def test_fiscal_supply_shock_ic_report_is_specific_and_traceable(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())

    outlook = generate_presentation_outlook(FISCAL_SUPPLY_SHOCK_SCENARIO, sequence_name="Fiscal Supply Shock Regression")
    markdown = outlook_to_markdown(outlook)
    rendered = markdown.lower()

    required_phrases = [
        "defense",
        "aerospace",
        "infrastructure",
        "industrials",
        "energy",
        "industrial metals",
        "stronger usd",
        "eurozone weaker",
        "china",
        "targeted stimulus",
        "long-duration technology",
        "reit",
        "gold may be weak initially",
        "higher real-yield risk",
        "fed overtightening risk",
        "research hypothesis - requires human review",
    ]
    for phrase in required_phrases:
        assert phrase in rendered
    assert outlook["scenario_probabilities"]["user_provided_probabilities"]["scenario_probability"] == 0.50
    assert outlook["scenario_probabilities"]["user_provided_probabilities"]["recession_probability"] == 0.20
    assert outlook["base_case"]["probability"] == 0.50
    assert outlook["bear_tail_case"]["probability"] == 0.20
    assert outlook["top_opportunities"]
    assert outlook["underweights_to_avoid"]
    assert outlook["recommended_hedges"]
    assert outlook["traceability"]
    assert outlook["decisions_for_investment_committee"]["opportunities_to_approve"]


def test_fiscal_supply_shock_report_sections_non_empty_and_no_unsupported_return_ranges(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())

    outlook = generate_presentation_outlook(FISCAL_SUPPLY_SHOCK_SCENARIO, sequence_name="Fiscal Sections Regression")
    sections = [
        "macro_thesis",
        "scenario_probabilities",
        "cross_asset_outlook",
        "top_opportunities",
        "underweights_to_avoid",
        "recommended_hedges",
        "historical_analogs",
        "central_bank_analysis",
        "country_regional_views",
        "risk_register",
        "what_would_change_the_view",
        "debate_summary",
        "changes_since_last_report",
        "decisions_for_investment_committee",
    ]
    for section in sections:
        assert outlook[section]
    for row in outlook["cross_asset_outlook"]:
        assert row["expected_return_range"] == "Insufficient verified data to quantify this item."
    assert "Insufficient verified data to quantify this item." in outlook_to_markdown(outlook)


def test_probability_preservation_warning_when_stated_probabilities_do_not_sum(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())
    scenario = {
        **FISCAL_SUPPLY_SHOCK_SCENARIO,
        "stated_probabilities": {"base": 0.5, "bear": 0.2},
    }

    outlook = generate_presentation_outlook(scenario, sequence_name="Probability Preservation Regression")

    assert outlook["scenario_probabilities"]["user_provided_probabilities"]["stated_probabilities"] == {"base": 0.5, "bear": 0.2}
    assert outlook["scenario_probabilities"]["warnings"]


def test_report_retrieval_and_export_contains_human_decision_section(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())
    outlook = generate_presentation_outlook(FISCAL_SUPPLY_SHOCK_SCENARIO, sequence_name="Report Export Regression")

    reports = list_investment_committee_reports(limit=500)
    report = next(row for row in reports if row["run_id"] == outlook["run_id"])

    assert "Decisions for the Investment Committee" in report["markdown"]
    assert "Traceability" in report["markdown"]


def test_soft_landing_outlook_does_not_contain_inflation_preset_leakage(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())
    parsed = confirm_structured_scenario(soft_landing_ollama_payload() | {
        "scenario_id": "scenario_soft_landing_test",
        "scenario_hash": "temporary",
        "parser_provider": "ollama",
        "parser_model": "llama3.1:8b",
        "source_text": SOFT_LANDING_EASING_SCENARIO,
    })

    outlook = generate_presentation_outlook(parsed, sequence_name="Soft Landing Regression")
    rendered = str(outlook).lower()

    assert outlook["scenario_definition"]["name"] == "Soft Landing / Gradual Fed Easing"
    forbidden = [
        "sharply higher",
        "behind the curve",
        "strong acceleration",
        "energy shock",
        "moderately stronger",
        "sharply stronger",
        "overheating",
        "commodity shock basket",
    ]
    for phrase in forbidden:
        assert phrase not in rendered


def test_sequential_inflation_to_soft_landing_state_isolation(monkeypatch):
    monkeypatch.setattr("app.services.scenario_presentation.ingest_all_sources", lambda: FakeSnapshot())
    inflation = confirm_structured_scenario(parse_free_text_scenario(SCENARIO_A, force_rule_fallback=True))
    inflation_outlook = safe_generate_presentation_outlook(inflation, sequence_name="Sequential Inflation")
    assert inflation_outlook["status"] == "ok"
    assert inflation["commodity_shock"] == "energy shock"

    monkeypatch.setenv("HCP_SCENARIO_PARSER_PROVIDER", "ollama")
    monkeypatch.setattr(
        "app.services.scenario_presentation.OllamaProvider.parse_scenario",
        lambda self, text: OllamaParseResult(True, soft_landing_ollama_payload(), "llama3.1:8b", 140, None),
    )
    soft = confirm_structured_scenario(parse_free_text_scenario(SOFT_LANDING_EASING_SCENARIO))
    soft_outlook = safe_generate_presentation_outlook(soft, sequence_name="Sequential Soft Landing")

    assert soft_outlook["status"] == "ok"
    assert inflation["scenario_id"] != soft["scenario_id"]
    assert inflation["scenario_hash"] != soft["scenario_hash"]
    assert soft["commodity_shock"] == "none"
    assert soft["fed_position"] == "roughly on time"
    assert soft["dollar_outlook"] == "moderately weaker"
    rendered = str(soft_outlook).lower()
    assert "energy shock" not in rendered
    assert "behind the curve" not in rendered
    assert "strong acceleration" not in rendered
