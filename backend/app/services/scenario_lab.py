import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from statistics import mean
from typing import Any

from app.connectors import ingest_all_sources
from app.services.database import (
    list_lessons_learned,
    list_scenario_analogs,
    list_scenario_evaluations,
    list_scenario_phases,
    list_scenario_postmortems,
    list_scenario_recommendations,
    list_scenario_sequences,
    save_scenario_analogs,
    save_scenario_evaluation,
    save_scenario_phase,
    save_scenario_postmortem,
    save_scenario_recommendation,
    save_scenario_sequence,
)
from app.services.knowledge_base import KnowledgeBaseService


ASSET_CLASSES = [
    "US equities",
    "international equities",
    "growth stocks",
    "value stocks",
    "small caps",
    "government bonds",
    "investment-grade credit",
    "high-yield credit",
    "inflation-linked bonds",
    "US dollar",
    "major foreign currencies",
    "gold",
    "oil",
    "industrial commodities",
    "agriculture",
    "REITs",
    "MLPs",
    "crypto",
    "volatility",
    "cash",
]


HISTORICAL_ANALOG_LIBRARY = [
    {
        "period": "1968-1969",
        "regime": "Inflation pressure with resilient growth before restrictive policy",
        "features": {
            "growth_direction": "strong",
            "inflation_direction": "rising",
            "inflation_surprise": "higher",
            "central_bank_policy_stance": "delayed_tightening",
            "curve_position": "behind",
            "labor_market_conditions": "tight",
            "financial_conditions": "easy",
            "recession_probability": 0.25,
        },
        "differences": ["Fiscal impulse and market structure differ from today.", "Global supply chains are more complex now."],
    },
    {
        "period": "1973-1974",
        "regime": "Commodity shock, inflation surge, policy catch-up, recession risk",
        "features": {
            "growth_direction": "slowing",
            "inflation_direction": "rising",
            "inflation_surprise": "higher",
            "central_bank_policy_stance": "tightening",
            "curve_position": "behind",
            "labor_market_conditions": "mixed",
            "financial_conditions": "tightening",
            "recession_probability": 0.65,
        },
        "differences": ["Oil shock was larger and more direct.", "Modern inflation expectations are better anchored."],
    },
    {
        "period": "1980-1982",
        "regime": "Aggressive Fed tightening to break inflation causing downturn",
        "features": {
            "growth_direction": "contracting",
            "inflation_direction": "elevated",
            "inflation_surprise": "higher",
            "central_bank_policy_stance": "aggressive_tightening",
            "curve_position": "behind",
            "labor_market_conditions": "weakening",
            "financial_conditions": "tight",
            "recession_probability": 0.8,
        },
        "differences": ["Starting inflation and policy rates were much higher.", "Private-sector leverage composition differs."],
    },
    {
        "period": "1994-1995",
        "regime": "Fed tightening surprise without recession",
        "features": {
            "growth_direction": "strong",
            "inflation_direction": "stable",
            "inflation_surprise": "modest",
            "central_bank_policy_stance": "tightening",
            "curve_position": "ahead",
            "labor_market_conditions": "firm",
            "financial_conditions": "tightening",
            "recession_probability": 0.25,
        },
        "differences": ["Inflation problem was less severe.", "Fiscal and debt backdrop was different."],
    },
    {
        "period": "2000-2001",
        "regime": "Late-cycle tightening and growth-stock unwind into recession",
        "features": {
            "growth_direction": "slowing",
            "inflation_direction": "mixed",
            "inflation_surprise": "lower",
            "central_bank_policy_stance": "restrictive",
            "curve_position": "ahead",
            "labor_market_conditions": "weakening",
            "financial_conditions": "tight",
            "recession_probability": 0.7,
        },
        "differences": ["Equity bubble composition was more technology-specific.", "Inflation was not the dominant constraint."],
    },
    {
        "period": "2021-2022",
        "regime": "Post-pandemic inflation surge and delayed tightening",
        "features": {
            "growth_direction": "strong",
            "inflation_direction": "rising",
            "inflation_surprise": "higher",
            "central_bank_policy_stance": "delayed_tightening",
            "curve_position": "behind",
            "labor_market_conditions": "tight",
            "financial_conditions": "easy",
            "recession_probability": 0.35,
        },
        "differences": ["Pandemic reopening distortions are unique.", "Balance-sheet policy played a larger role."],
    },
]


@dataclass
class MacroScenario:
    scenario_name: str
    scenario_date: str
    growth_direction: str
    inflation_direction: str
    inflation_surprise: str
    central_bank_policy_stance: str
    expected_policy_path: str
    central_bank_curve_position: str
    labor_market_conditions: str
    financial_conditions: str
    fiscal_conditions: str
    recession_probability: float
    scenario_duration: str
    probability: float
    conviction: float
    invalidation_triggers: list[str] = field(default_factory=list)


def create_or_update_scenario_sequence(name: str, description: str = "", sequence_id: str | None = None) -> dict:
    sequence_id = sequence_id or _stable_id("scenario_seq", name)
    return save_scenario_sequence({"sequence_id": sequence_id, "name": name, "description": description})


def save_phase(sequence_id: str, phase_number: int, scenario: dict[str, Any], data_snapshot: dict | None = None) -> dict:
    created_at = scenario.get("scenario_date") or datetime.utcnow().date().isoformat()
    phase_id = scenario.get("phase_id") or _stable_id("scenario_phase", f"{sequence_id}:{phase_number}:{created_at}:{scenario['scenario_name']}")
    snapshot = data_snapshot or ingest_all_sources().model_dump(mode="json")
    return save_scenario_phase(
        {
            "phase_id": phase_id,
            "sequence_id": sequence_id,
            "phase_number": phase_number,
            "scenario": scenario,
            "data_snapshot": snapshot,
            "created_at": created_at,
        }
    )


def identify_historical_analogs(phase: dict[str, Any], limit: int = 5) -> dict:
    scenario = phase["scenario"]
    ranked = []
    for analog in HISTORICAL_ANALOG_LIBRARY:
        score, matches, differences = _similarity(scenario, analog)
        ranked.append(
            {
                "period": analog["period"],
                "similarity_score": round(score, 3),
                "matching_features": matches,
                "important_differences": analog["differences"] + differences,
                "historical_regime_description": analog["regime"],
                "confidence": round(min(0.95, 0.4 + score / 2), 3),
                "not_exact_forecast": "Historical analogs are reference cases, not forecasts; position sizing must reflect present-day differences.",
            }
        )
    result = {
        "phase_id": phase["phase_id"],
        "ranked_historical_analogs": sorted(ranked, key=lambda row: row["similarity_score"], reverse=True)[:limit],
    }
    save_scenario_analogs(phase["phase_id"], result)
    return result


def cross_asset_historical_performance(analogs: list[dict[str, Any]]) -> dict:
    rows = []
    for analog in analogs:
        period = analog["period"]
        for asset in ASSET_CLASSES:
            horizon_returns = {horizon: _mock_return(period, asset, horizon) for horizon in ["1m", "3m", "6m", "12m"]}
            returns = list(horizon_returns.values())
            rows.append(
                {
                    "period": period,
                    "asset_class": asset,
                    "returns": horizon_returns,
                    "volatility": round(abs(mean(returns)) * 1.8 + 0.04, 4),
                    "maximum_drawdown": round(min(returns) - 0.03, 4),
                    "risk_adjusted_return": round(mean(returns) / (abs(mean(returns)) * 1.8 + 0.04), 4),
                }
            )
    summary = []
    for asset in ASSET_CLASSES:
        asset_rows = [row for row in rows if row["asset_class"] == asset]
        twelve = [row["returns"]["12m"] for row in asset_rows]
        summary.append(
            {
                "asset_class": asset,
                "hit_rate_across_analogs": sum(1 for value in twelve if value > 0) / len(twelve) if twelve else 0,
                "dispersion_across_analogs": round(max(twelve) - min(twelve), 4) if twelve else 0,
                "average_12m_return": round(mean(twelve), 4) if twelve else 0,
            }
        )
    return {"rows": rows, "summary": summary}


def generate_scenario_recommendations(phase: dict[str, Any], analog_result: dict[str, Any] | None = None) -> dict:
    analog_result = analog_result or identify_historical_analogs(phase)
    scenario = phase["scenario"]
    analogs = analog_result["ranked_historical_analogs"]
    memory = KnowledgeBaseService().retrieve_institutional_context(_scenario_query(scenario), limit=5)
    lessons = list_lessons_learned(10)
    templates = _recommendation_templates(scenario)
    recommendations = []
    for index, template in enumerate(templates, start=1):
        recommendation = {
            **template,
            "recommendation_date": phase["created_at"],
            "scenario_phase": phase["phase_id"],
            "scenario_name": scenario["scenario_name"],
            "expected_time_horizon": scenario["scenario_duration"],
            "historical_analog_support": [row["period"] for row in analogs[:3]],
            "current_data_support": _current_data_support(phase),
            "model_reasoning": f"Generated from scenario assumptions, analogs, HCP memory, and lessons. Retrieved memory buckets: {list(memory.keys())}.",
            "lessons_applied": [lesson.get("pattern") for lesson in lessons[:3]],
            "evaluation_horizons": [1, 3, 6, 12],
        }
        recommendation_id = _stable_id("scenario_rec", f"{phase['phase_id']}:{index}:{template['asset_or_trade']}")
        saved = save_scenario_recommendation(
            {
                "recommendation_id": recommendation_id,
                "phase_id": phase["phase_id"],
                "sequence_id": phase["sequence_id"],
                "recommendation": recommendation,
                "frozen_snapshot": {
                    "scenario": scenario,
                    "data_snapshot": phase.get("data_snapshot", {}),
                    "historical_analogs_used": analogs,
                },
                "created_at": phase["created_at"],
            }
        )
        recommendations.append(saved)
    return categorize_recommendations([row["recommendation"] for row in recommendations])


def categorize_recommendations(recommendations: list[dict[str, Any]]) -> dict:
    ranked = sorted(recommendations, key=lambda row: (row.get("conviction", 0), row.get("probability_of_success", 0)), reverse=True)
    return {
        "ranked_recommendations": ranked,
        "highest_conviction_opportunities": [row for row in ranked if row.get("conviction", 0) >= 7.5],
        "asymmetric_opportunities": [row for row in ranked if "asymmetric" in row.get("category", "")],
        "defensive_positions": [row for row in ranked if row.get("category") == "defensive"],
        "hedges": [row for row in ranked if row.get("category") == "hedge"],
        "positions_to_avoid": [row for row in ranked if row.get("category") == "avoid"],
    }


def scenario_comparison_matrix(phase_ids: list[str] | None = None) -> dict:
    phases = list_scenario_phases()
    if phase_ids:
        phases = [phase for phase in phases if phase["phase_id"] in phase_ids]
    matrix = []
    for phase in phases[:6]:
        scenario = phase["scenario"]
        for asset in ASSET_CLASSES:
            matrix.append(
                {
                    "phase_id": phase["phase_id"],
                    "scenario_name": scenario["scenario_name"],
                    "asset_class": asset,
                    "expected_behavior": _asset_behavior(asset, scenario),
                }
            )
    return {"matrix": matrix}


def evaluate_scenario_recommendation(recommendation_row: dict[str, Any], horizon_months: int) -> dict:
    rec = recommendation_row["recommendation"]
    expected_mid = mean(rec["expected_return_range"])
    realized = _mock_realized_return(rec["asset_or_trade"], horizon_months)
    direction_correct = (realized >= 0 and rec["direction"] in {"long", "overweight"}) or (realized <= 0 and rec["direction"] in {"short", "underweight", "avoid"})
    low, high = rec["expected_return_range"]
    payload = {
        "recommendation_id": recommendation_row["recommendation_id"],
        "horizon_months": horizon_months,
        "realized_return": realized,
        "benchmark_relative_return": round(realized - 0.01 * horizon_months, 4),
        "drawdown": round(min(realized, 0) - 0.04, 4),
        "direction_correct": direction_correct,
        "expected_range_accurate": low <= realized <= high,
        "probability_calibrated": abs((1 if direction_correct else 0) - rec["probability_of_success"]) <= 0.35,
        "hedge_worked": rec.get("category") == "hedge" and realized > 0,
        "assumptions_correct": ["Scenario direction was directionally useful"] if direction_correct else [],
        "assumptions_failed": [] if direction_correct else ["Recommendation direction failed against realized proxy behavior"],
        "expected_midpoint": expected_mid,
    }
    save_scenario_evaluation(recommendation_row["recommendation_id"], horizon_months, payload)
    return payload


def generate_phase_postmortem(phase_id: str) -> dict:
    recs = list_scenario_recommendations(phase_id)
    evaluations = []
    for rec in recs:
        for horizon in [1, 3, 6, 12]:
            evaluations.append(evaluate_scenario_recommendation(rec, horizon))
    misses = [item for item in evaluations if not item["direction_correct"]]
    payload = {
        "phase_id": phase_id,
        "what_model_got_right": ["Mapped scenario phase to cross-asset recommendations"] if len(misses) < len(evaluations) else [],
        "what_model_got_wrong": ["Some recommendation directions failed"] if misses else [],
        "incorrect_analogs": ["Review lowest-scoring analogs and any analogs with high dispersion"],
        "missing_variables": ["Full vintage macro data", "Live valuation inputs", "Credit spread history"],
        "overconfident_conclusions": [item["recommendation_id"] for item in evaluations if not item["probability_calibrated"]],
        "successful_indicators": ["Inflation direction", "central bank curve position"],
        "failed_indicators": ["Scenario timing"] if misses else [],
        "successful_asset_mappings": [item["recommendation_id"] for item in evaluations if item["direction_correct"]][:10],
        "failed_asset_mappings": [item["recommendation_id"] for item in misses][:10],
        "human_reviewer_feedback": "Pending human review.",
    }
    save_scenario_postmortem(phase_id, payload)
    return payload


def scenario_lab_dashboard_data() -> dict:
    return {
        "sequences": list_scenario_sequences(),
        "phases": list_scenario_phases(),
        "analogs": list_scenario_analogs(),
        "recommendations": list_scenario_recommendations(),
        "evaluations": list_scenario_evaluations(),
        "postmortems": list_scenario_postmortems(),
        "comparison_matrix": scenario_comparison_matrix()["matrix"],
    }


def create_demo_three_phase_sequence() -> dict:
    sequence = create_or_update_scenario_sequence(
        "Inflation Surprise To Fed Overtightening",
        "Three-phase HCP macro theme: delayed tightening, aggressive catch-up, and downturn risk.",
        "scenario_seq_inflation_fed_overtightening",
    )
    scenarios = [
        MacroScenario(
            scenario_name="Phase 1: Inflation Surprise With Strong Growth",
            scenario_date="2021-06-01",
            growth_direction="strong",
            inflation_direction="rising",
            inflation_surprise="higher",
            central_bank_policy_stance="delayed_tightening",
            expected_policy_path="gradual_then_faster",
            central_bank_curve_position="behind",
            labor_market_conditions="tight",
            financial_conditions="easy",
            fiscal_conditions="expansionary",
            recession_probability=0.25,
            scenario_duration="6-12 months",
            probability=0.55,
            conviction=7.0,
            invalidation_triggers=["Inflation rolls over quickly", "Labor market weakens abruptly"],
        ),
        MacroScenario(
            scenario_name="Phase 2: Fed Tightens More Than Expected",
            scenario_date="2022-03-01",
            growth_direction="slowing",
            inflation_direction="elevated",
            inflation_surprise="higher",
            central_bank_policy_stance="aggressive_tightening",
            expected_policy_path="front_loaded_hikes",
            central_bank_curve_position="behind",
            labor_market_conditions="tight",
            financial_conditions="tightening",
            fiscal_conditions="neutral",
            recession_probability=0.45,
            scenario_duration="6-12 months",
            probability=0.5,
            conviction=7.5,
            invalidation_triggers=["Fed pauses early", "Inflation expectations collapse"],
        ),
        MacroScenario(
            scenario_name="Phase 3: Fed Overtightening Downturn",
            scenario_date="2023-03-01",
            growth_direction="contracting",
            inflation_direction="falling",
            inflation_surprise="lower",
            central_bank_policy_stance="restrictive",
            expected_policy_path="cuts_after_damage",
            central_bank_curve_position="ahead",
            labor_market_conditions="weakening",
            financial_conditions="tight",
            fiscal_conditions="constrained",
            recession_probability=0.7,
            scenario_duration="6-12 months",
            probability=0.45,
            conviction=7.0,
            invalidation_triggers=["Credit stabilizes", "Growth reaccelerates", "Fed cuts preemptively"],
        ),
    ]
    phase_outputs = []
    for index, scenario in enumerate(scenarios, start=1):
        phase = save_phase(sequence["sequence_id"], index, asdict(scenario), data_snapshot={"point_in_time_only": scenario.scenario_date})
        analogs = identify_historical_analogs(phase)
        performance = cross_asset_historical_performance(analogs["ranked_historical_analogs"])
        recommendations = generate_scenario_recommendations(phase, analogs)
        phase_outputs.append({"phase": phase, "analogs": analogs, "cross_asset_performance": performance, "recommendations": recommendations})
    return {"sequence": sequence, "phases": phase_outputs}


def _similarity(scenario: dict[str, Any], analog: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    features = analog["features"]
    keys = ["growth_direction", "inflation_direction", "inflation_surprise", "central_bank_policy_stance", "labor_market_conditions", "financial_conditions"]
    matches = []
    differences = []
    score = 0.0
    for key in keys:
        if str(scenario.get(key, "")).lower() == str(features.get(key, "")).lower():
            score += 1
            matches.append(key)
        else:
            differences.append(f"{key}: current={scenario.get(key)} historical={features.get(key)}")
    if str(scenario.get("central_bank_curve_position", "")).lower() == str(features.get("curve_position", "")).lower():
        score += 1
        matches.append("central_bank_curve_position")
    rec_diff = abs(float(scenario.get("recession_probability", 0)) - float(features.get("recession_probability", 0)))
    score += max(0, 1 - rec_diff)
    if rec_diff > 0.25:
        differences.append(f"recession_probability differs by {rec_diff:.0%}")
    return score / 8, matches, differences


def _recommendation_templates(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    stance = scenario["central_bank_policy_stance"]
    growth = scenario["growth_direction"]
    inflation = scenario["inflation_direction"]
    if stance in {"delayed_tightening"} and growth == "strong":
        return [
            _rec("Energy and commodity producers", "overweight", "commodity", "asymmetric", 0.58, 7.8, [0.03, 0.18], "Higher inflation and delayed tightening support nominal assets.", "Long-duration growth equities"),
            _rec("TIPS breakeven exposure", "long", "fixed_income", "defensive", 0.57, 7.2, [0.01, 0.1], "Inflation surprise can support inflation-linked bonds.", "Inflation rolls over"),
            _rec("Gold", "long", "commodity", "hedge", 0.52, 6.8, [-0.03, 0.12], "Policy credibility risk supports gold.", "Real yields rise sharply"),
            _rec("Long-duration nominal bonds", "underweight", "fixed_income", "avoid", 0.6, 7.4, [-0.12, 0.02], "Delayed tightening with inflation surprise pressures duration.", "Growth shock overwhelms inflation"),
        ]
    if stance in {"aggressive_tightening", "tightening"} or inflation == "elevated":
        return [
            _rec("US dollar", "long", "fx_rates", "defensive", 0.6, 7.8, [0.02, 0.12], "Front-loaded Fed tightening can support the dollar.", "Fed signals early pause"),
            _rec("Value over growth", "overweight", "equity", "highest_conviction", 0.56, 7.6, [0.01, 0.1], "Higher real rates pressure long-duration equities.", "Rates fall quickly"),
            _rec("Quality balance-sheet equities", "overweight", "equity", "defensive", 0.55, 7.1, [0.0, 0.09], "Tighter financial conditions favor resilient margins and balance sheets.", "Risk-on liquidity surge"),
            _rec("High-yield credit", "underweight", "credit", "avoid", 0.58, 7.5, [-0.1, 0.02], "Aggressive tightening raises refinancing and spread risk.", "Growth remains above trend"),
        ]
    return [
        _rec("Intermediate government bonds", "long", "fixed_income", "highest_conviction", 0.61, 8.0, [0.03, 0.16], "Overtightening downturn can pull yields lower.", "Inflation reaccelerates"),
        _rec("Equity volatility", "long", "volatility", "hedge", 0.57, 7.4, [0.02, 0.2], "Downturn risk raises demand for convex hedges.", "Soft landing becomes dominant"),
        _rec("Defensive equities", "overweight", "equity", "defensive", 0.55, 7.2, [0.0, 0.1], "Weakening labor and tight conditions favor low-beta sectors.", "Growth reaccelerates"),
        _rec("Small caps", "underweight", "equity", "avoid", 0.59, 7.3, [-0.12, 0.03], "Credit sensitivity and margin risk rise in downturns.", "Credit conditions improve"),
    ]


def _rec(asset: str, direction: str, asset_class: str, category: str, probability: float, conviction: float, ret_range: list[float], thesis: str, invalidation: str) -> dict:
    return {
        "asset_or_trade": asset,
        "asset_class": asset_class,
        "direction": direction,
        "category": category,
        "investment_thesis": thesis,
        "expected_return_range": ret_range,
        "probability_of_success": probability,
        "conviction": conviction,
        "major_risks": ["Timing error", "Policy reaction function changes", "Analog dispersion"],
        "hedge": "Use position sizing and explicit invalidation triggers; pair with convex hedge where applicable.",
        "invalidation_condition": invalidation,
    }


def _scenario_query(scenario: dict[str, Any]) -> str:
    return " ".join(str(scenario.get(key, "")) for key in ["scenario_name", "growth_direction", "inflation_direction", "central_bank_policy_stance", "financial_conditions"])


def _current_data_support(phase: dict[str, Any]) -> list[str]:
    snapshot = phase.get("data_snapshot", {})
    signals = snapshot.get("signals", []) if isinstance(snapshot, dict) else []
    return [signal.get("interpretation", signal.get("name", "")) for signal in signals[:4]] or ["Point-in-time scenario assumptions preserved."]


def _asset_behavior(asset: str, scenario: dict[str, Any]) -> str:
    recs = _recommendation_templates(scenario)
    for rec in recs:
        if asset.lower().split()[0] in rec["asset_or_trade"].lower() or rec["asset_class"] in asset.lower():
            return f"{rec['direction']} / {rec['category']}"
    if scenario["growth_direction"] in {"contracting", "slowing"} and asset in {"government bonds", "cash", "volatility"}:
        return "likely defensive"
    if scenario["inflation_direction"] in {"rising", "elevated"} and asset in {"gold", "oil", "industrial commodities", "inflation-linked bonds"}:
        return "likely supported"
    return "mixed / monitor"


def _mock_return(period: str, asset: str, horizon: str) -> float:
    seed = int(hashlib.sha256(f"{period}:{asset}:{horizon}".encode()).hexdigest()[:8], 16)
    base = (seed % 2400) / 10000 - 0.08
    if "1980" in period and asset in {"government bonds", "US dollar", "cash"}:
        base += 0.05
    if "1973" in period and asset in {"gold", "oil", "industrial commodities"}:
        base += 0.08
    if "2021" in period and asset in {"oil", "industrial commodities", "value stocks"}:
        base += 0.05
    multiplier = {"1m": 0.25, "3m": 0.5, "6m": 0.75, "12m": 1.0}[horizon]
    return round(base * multiplier, 4)


def _mock_realized_return(asset: str, horizon_months: int) -> float:
    seed = int(hashlib.sha256(f"{asset}:{horizon_months}:realized".encode()).hexdigest()[:8], 16)
    return round(((seed % 2200) / 10000 - 0.07) * (horizon_months / 12), 4)


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:16]}"
