from __future__ import annotations

from pathlib import Path

from app.services.asset_positioning import (
    ASSET_UNIVERSE,
    INSUFFICIENT_DATA,
    build_cross_asset_outlook,
    build_portfolio_evolution,
    build_suggested_portfolio,
    evaluate_portfolio,
    historical_forward_performance,
    unexpected_opportunities,
)
from app.services.ic_pdf import generate_ic_pdf
from app.services.scenario_contract import normalize_scenario_contract
from app.services.scenario_presentation import scenario_input_options
from app.services.theme_evolution import copy_phase, create_demo_four_phase_theme


def scenario(**updates):
    values = {
        "scenario_name": "Manager feedback test",
        "growth_outlook": "moderate growth", "growth_surprise": "large upside surprise",
        "inflation_direction": "accelerating inflation", "inflation_surprise": "small upside surprise",
        "central_bank_stance": "gradually tightening", "fed_position": "behind the curve",
        "expected_fed_response": "aggressively tighten", "labor_market": "strong",
        "financial_conditions": "tight", "market_volatility": "high", "credit_stress": 6,
        "dollar_outlook": "moderately stronger", "commodity_shock": "energy shock",
        "equity_valuation": "expensive", "market_sentiment": "bullish",
        "margin_debt": "high", "time_horizon": "3-6 months",
        "recession_probability": 0.35, "countries_or_regions": ["Global"],
        "risks": ["Timing"], "invalidation_triggers": ["Inflation decelerates"],
    }
    values.update(updates)
    return values


def analogs():
    return [
        {"period": "1994-1995", "similarity_score": 0.8, "matching_features": ["growth"], "important_differences": ["valuation"]},
        {"period": "2021-2022", "similarity_score": 0.6, "matching_features": ["inflation"], "important_differences": ["pandemic"]},
    ]


def test_manager_scenario_options_and_legacy_migration():
    options = scenario_input_options()
    assert options["growth_outlook"] == ["accelerating growth", "moderate growth", "slowing growth", "stagnation", "recession"]
    assert options["growth_surprise"] == options["inflation_surprise"]
    assert options["inflation_direction"] == ["accelerating inflation", "stable inflation", "decelerating inflation", "deflation"]
    assert options["expected_fed_response"] == ["aggressively tighten", "tighten", "hold", "loosen", "aggressively loosen"]
    assert options["market_sentiment"] == ["extremely bullish", "bullish", "neutral", "bearish", "extremely bearish"]
    assert options["margin_debt"] == ["extremely high", "high", "moderate", "low", "very low"]
    assert options["commodity_shock"] == ["none", "energy shock", "food shock", "metals shock", "broad commodity shock"]
    assert options["time_horizon"] == ["1-3 months", "3-6 months", "6-9 months", "9-12 months", "12+ months"]
    assert {"Global", "Custom", "Emerging Markets"}.issubset(options["countries_or_regions"])
    migrated = normalize_scenario_contract({"growth_outlook": "strong acceleration", "inflation_direction": "disinflation"})
    assert migrated["growth_outlook"] == "accelerating growth"
    assert migrated["inflation_direction"] == "decelerating inflation"


def test_asset_universe_is_deep_and_never_recommends_individual_stocks():
    subsegments = {row[1] for row in ASSET_UNIVERSE}
    assert {"Large Cap", "Mid Cap", "Small Cap", "Growth", "Value", "Technology", "Energy"}.issubset(subsegments)
    assert {"2-Year / Short End", "5-Year / Belly", "10-Year / Belly", "30-Year / Long End"}.issubset(subsegments)
    assert {"Investment Grade Corporate", "High Yield Corporate", "TIPS", "Gold", "MLPs", "Crypto"}.issubset(subsegments)
    outlook = build_cross_asset_outlook(scenario(), analogs(), ["FRED signal current"])
    portfolio = build_suggested_portfolio(outlook)
    assert outlook
    assert portfolio["long_overweight"] and portfolio["short_underweight"]
    assert all(position["recommendation_is_security"] is False for position in portfolio["all_positions"])
    assert all(position["tracking_benchmark_proxy"] != position["subsegment"] for position in portfolio["all_positions"])


def test_analog_performance_never_fabricates_and_computes_verified_observations():
    empty = historical_forward_performance(analogs())
    assert all(row["status"] == INSUFFICIENT_DATA for row in empty["rows"])
    verified = historical_forward_performance(analogs(), [
        {"period": "1994-1995", "subsegment": "Small Cap", "horizon_months": 3, "return": 0.08, "maximum_drawdown": -0.04, "verified": True},
        {"period": "2021-2022", "subsegment": "Small Cap", "horizon_months": 3, "return": -0.02, "maximum_drawdown": -0.08, "verified": True},
    ])
    row = next(item for item in verified["rows"] if item["subsegment"] == "Small Cap" and item["horizon_months"] == 3)
    assert row["average_return"] == 0.03
    assert row["positive_hit_rate"] == 0.5


def test_unexpected_opportunities_require_evidence_threshold():
    outlook = build_cross_asset_outlook(scenario(), analogs(), ["current"])
    assert all(item["historical_support"]["normalized_similarity_support"] >= 0.45 for item in unexpected_opportunities(outlook))
    unsupported = build_cross_asset_outlook(scenario(), [{"period": "x", "similarity_score": 0.1}], [])
    assert unexpected_opportunities(unsupported) == []


def test_four_phase_evolution_copy_and_direction_changes():
    phases = [
        {"phase_id": "p1", "phase_name": "One", "window": "Months 0-3", "scenario": scenario(), "historical_analogs": analogs()},
        {"phase_id": "p2", "phase_name": "Two", "window": "Months 3-6", "scenario": scenario(growth_outlook="recession", growth_surprise="large downside surprise", inflation_direction="decelerating inflation", expected_fed_response="loosen", recession_probability=0.8), "historical_analogs": analogs()},
    ]
    copied = copy_phase(phases[0], phase_number=2)
    copied["scenario"]["growth_outlook"] = "recession"
    assert phases[0]["scenario"]["growth_outlook"] == "moderate growth"
    evolution = build_portfolio_evolution(phases)
    assert len(evolution["phases"]) == 2
    assert evolution["portfolio_changes"]
    assert evolution["portfolio_changes"][0]["direction_changes"]


def test_portfolio_paper_evaluation_at_supported_horizons():
    portfolio = build_suggested_portfolio(build_cross_asset_outlook(scenario(), analogs(), []))
    realized = {row["subsegment"]: 0.03 for row in portfolio["all_positions"]}
    result = evaluate_portfolio(portfolio["all_positions"], realized, benchmark_return=0.01, weighting="conviction")
    assert result["status"].startswith("paper evaluation")
    assert result["weighting_assumption"] == "conviction"
    assert result["portfolio_return"] is not None


def test_pdf_report_generation_is_real_pdf():
    outlook = {
        "run_id": "manager_feedback_pdf", "run_date": "2026-08-14",
        "disclaimer": "Research only. No execution.", "executive_outlook": "Test outlook.",
        "scenario_definition": scenario(), "historical_analogs": analogs(),
        "expected_asset_class_performance": build_cross_asset_outlook(scenario(), analogs(), []),
        "suggested_portfolio": build_suggested_portfolio(build_cross_asset_outlook(scenario(), analogs(), [])),
        "unexpected_opportunities": [], "risk_register": [],
        "decisions_for_investment_committee": {"review": "Human approval required"},
    }
    data = generate_ic_pdf(outlook)
    assert data.startswith(b"%PDF")
    assert len(data) > 2000
