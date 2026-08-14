from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.asset_positioning import build_portfolio_evolution
from app.services.scenario_contract import normalize_scenario_contract
from app.services.scenario_lab import (
    create_or_update_scenario_sequence,
    identify_historical_analogs,
    save_phase,
)


PHASE_WINDOWS = ("Months 0-3", "Months 3-6", "Months 6-9", "Months 9-12")


def copy_phase(phase: dict[str, Any], *, phase_number: int, phase_name: str | None = None) -> dict[str, Any]:
    copied = deepcopy(phase)
    copied.pop("phase_id", None)
    copied["phase_number"] = phase_number
    copied["phase_name"] = phase_name or f"Phase {phase_number}"
    copied["window"] = PHASE_WINDOWS[phase_number - 1]
    copied["scenario"] = deepcopy(phase.get("scenario", {}))
    return copied


def save_theme(
    name: str,
    phases: list[dict[str, Any]],
    *,
    description: str = "",
    sequence_id: str | None = None,
) -> dict[str, Any]:
    if len(phases) != 4:
        raise ValueError("A 12-month theme requires exactly four sequential phases")
    sequence = create_or_update_scenario_sequence(name, description, sequence_id)
    prepared = []
    for index, item in enumerate(phases, start=1):
        scenario = normalize_scenario_contract(item.get("scenario", item))
        scenario.setdefault("scenario_name", item.get("phase_name", f"Phase {index}"))
        snapshot = item.get("data_snapshot") or {"source_status": {"Demo": "fallback"}, "signals": []}
        saved = save_phase(sequence["sequence_id"], index, scenario, snapshot)
        analogs = identify_historical_analogs(saved)["ranked_historical_analogs"]
        prepared.append({
            "phase_id": saved["phase_id"], "phase_name": item.get("phase_name", f"Phase {index}"),
            "window": PHASE_WINDOWS[index - 1], "scenario": scenario,
            "historical_analogs": analogs,
            "current_data_support": item.get("current_data_support", []),
        })
    evolution = build_portfolio_evolution(prepared)
    return {"sequence": sequence, **evolution}


def create_demo_four_phase_theme() -> dict[str, Any]:
    base = {
        "scenario_date": "2026-08-14", "central_bank_stance": "gradually tightening",
        "fed_position": "behind the curve", "labor_market": "strong",
        "financial_conditions": "neutral", "market_volatility": "normal",
        "credit_stress": 3, "dollar_outlook": "moderately stronger",
        "commodity_shock": "none", "equity_valuation": "expensive",
        "market_sentiment": "bullish", "margin_debt": "high",
        "recession_probability": 0.25, "probability": 0.55,
        "countries_or_regions": ["U.S.", "Global"], "time_horizon": "3-6 months",
        "risks": ["The macro sequence may occur faster or slower than assumed."],
        "invalidation_triggers": ["Incoming growth, inflation, or policy data contradict the phase assumptions."],
    }
    phases = [
        {"phase_name": "Inflation Upside Surprise / Resilient Growth", "scenario": {
            **base, "scenario_name": "Phase 1 - Inflation Upside Surprise",
            "growth_outlook": "moderate growth", "growth_surprise": "in line",
            "inflation_direction": "accelerating inflation", "inflation_surprise": "large upside surprise",
            "expected_fed_response": "tighten", "commodity_shock": "energy shock",
        }},
        {"phase_name": "Positive Growth Surprise / Elevated Inflation", "scenario": {
            **base, "scenario_name": "Phase 2 - Positive Growth Surprise",
            "growth_outlook": "accelerating growth", "growth_surprise": "large upside surprise",
            "inflation_direction": "stable inflation", "inflation_surprise": "small upside surprise",
            "expected_fed_response": "tighten",
        }},
        {"phase_name": "Fed Catch-Up Tightening", "scenario": {
            **base, "scenario_name": "Phase 3 - Aggressive Fed Catch-Up",
            "growth_outlook": "slowing growth", "growth_surprise": "small downside surprise",
            "inflation_direction": "accelerating inflation", "inflation_surprise": "small upside surprise",
            "central_bank_stance": "aggressively tightening", "expected_fed_response": "aggressively tighten",
            "market_volatility": "high", "financial_conditions": "tight", "credit_stress": 6,
        }},
        {"phase_name": "Material Growth Weakness / Recession Risk", "scenario": {
            **base, "scenario_name": "Phase 4 - Growth Weakens Materially",
            "growth_outlook": "recession", "growth_surprise": "large downside surprise",
            "inflation_direction": "decelerating inflation", "inflation_surprise": "small downside surprise",
            "central_bank_stance": "gradually easing", "expected_fed_response": "loosen",
            "fed_position": "roughly on time", "labor_market": "weak",
            "financial_conditions": "severely tight", "market_volatility": "crisis",
            "credit_stress": 9, "recession_probability": 0.75,
            "market_sentiment": "extremely bearish",
        }},
    ]
    return save_theme(
        "Demo 12-Month Inflation-to-Recession Theme", phases,
        description="Testing-only four-phase manager feedback sequence.",
        sequence_id="scenario_seq_demo_four_phase_2026",
    )
