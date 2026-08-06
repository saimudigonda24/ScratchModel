from __future__ import annotations

from datetime import datetime
from typing import Any

from app.connectors import ingest_all_sources
from app.services.database import save_investment_committee_report
from app.services.scenario_lab import (
    MacroScenario,
    create_or_update_scenario_sequence,
    cross_asset_historical_performance,
    generate_scenario_recommendations,
    identify_historical_analogs,
    save_phase,
)


DEMO_SCENARIO = {
    "scenario_name": "Demo: Inflation Surprise Cycle - Phase 1",
    "scenario_description": "Inflation surprises higher, growth remains strong, and the Fed delays tightening.",
    "scenario_date": "2026-08-06",
    "growth_direction": "strong",
    "inflation_direction": "rising",
    "inflation_surprise": "higher",
    "central_bank_policy_stance": "delayed_tightening",
    "expected_policy_path": "Fed stays patient initially, then risks a faster catch-up if inflation expectations move higher.",
    "central_bank_curve_position": "behind",
    "labor_market_conditions": "tight",
    "financial_conditions": "easy",
    "fiscal_conditions": "neutral",
    "countries_or_regions": ["United States", "Global developed markets"],
    "recession_probability": 0.25,
    "scenario_duration": "7-14 months",
    "probability": 0.55,
    "conviction": 7.4,
    "risks": [
        "Inflation falls before policy expectations reprice.",
        "Growth cracks abruptly and turns the scenario into a downturn trade.",
        "Commodity supply improves faster than expected.",
    ],
    "invalidation_triggers": [
        "Core inflation trends decisively lower for three consecutive releases.",
        "Payroll growth weakens materially and unemployment rises quickly.",
        "Fed communication turns preemptively restrictive.",
    ],
}

PROXY_MAP = {
    "Energy and commodity producers": ("XLE", "SPY"),
    "TIPS breakeven exposure": ("TIP", "IEF"),
    "Gold": ("GLD", "SPY"),
    "Long-duration nominal bonds": ("TLT", "IEF"),
    "US dollar": ("UUP", "BIL"),
    "Value over growth": ("VLUE", "SPY"),
    "Quality balance-sheet equities": ("QUAL", "SPY"),
    "High-yield credit": ("HYG", "IEF"),
    "Intermediate government bonds": ("IEF", "BIL"),
    "Equity volatility": ("VIXY", "SPY"),
    "Defensive equities": ("SPLV", "SPY"),
    "Small caps": ("IWM", "SPY"),
}


def generate_presentation_outlook(
    scenario: dict[str, Any],
    sequence_name: str = "Manager Demo Scenario",
    sequence_description: str = "Presentation-ready scenario workflow.",
    phase_number: int = 1,
    demo: bool = False,
) -> dict[str, Any]:
    """Run the scenario workflow and return a manager-ready IC briefing."""
    normalized = _normalize_scenario(scenario, demo=demo)
    sequence = create_or_update_scenario_sequence(sequence_name, sequence_description)
    snapshot = ingest_all_sources().model_dump(mode="json")
    phase = save_phase(sequence["sequence_id"], phase_number, normalized, data_snapshot=snapshot)
    analogs = identify_historical_analogs(phase)
    performance = cross_asset_historical_performance(analogs["ranked_historical_analogs"])
    recommendations = generate_scenario_recommendations(phase, analogs)
    outlook = build_presentation_outlook(phase, analogs, performance, recommendations, snapshot, demo=demo)
    markdown = outlook_to_markdown(outlook)
    save_investment_committee_report(
        outlook["run_id"],
        f"HCP Investment Committee Report - {outlook['scenario_definition']['name']}",
        outlook,
        markdown,
    )
    return {**outlook, "markdown": markdown}


def safe_generate_presentation_outlook(
    payload: dict[str, Any],
    sequence_name: str = "Manager Demo Scenario",
    sequence_description: str = "Presentation-ready scenario workflow.",
    phase_number: int = 1,
    demo: bool = False,
) -> dict[str, Any]:
    try:
        return generate_presentation_outlook(
            payload,
            sequence_name=sequence_name,
            sequence_description=sequence_description,
            phase_number=phase_number,
            demo=demo,
        )
    except Exception as exc:
        return {
            "status": "not_ready",
            "reason": "scenario_outlook_generation_failed",
            "warnings": [str(exc)],
            "report": None,
        }


def build_presentation_outlook(
    phase: dict[str, Any],
    analogs: dict[str, Any],
    performance: dict[str, Any],
    recommendations: dict[str, Any],
    data_snapshot: dict[str, Any],
    demo: bool = False,
) -> dict[str, Any]:
    scenario = phase["scenario"]
    top_recs = _dedupe_recommendations(recommendations.get("ranked_recommendations", []))
    opportunities = [_opportunity_row(row) for row in top_recs if row.get("category") != "hedge"][:6]
    hedges = [_hedge_row(row, scenario) for row in top_recs if row.get("category") == "hedge"]
    if not hedges:
        hedges = [_fallback_hedge(scenario)]

    cross_asset = _cross_asset_outlook(scenario, top_recs)
    outlook = {
        "status": "ok",
        "demo": demo,
        "run_id": phase["phase_id"],
        "run_date": datetime.utcnow().isoformat(),
        "data_mode": data_mode_label(data_snapshot),
        "scenario_definition": {
            "name": scenario["scenario_name"],
            "description": scenario.get("scenario_description", ""),
            "growth_outlook": scenario["growth_direction"],
            "inflation_outlook": scenario["inflation_direction"],
            "central_bank_stance": scenario["central_bank_policy_stance"],
            "expected_policy_response": scenario["expected_policy_path"],
            "countries_or_regions": scenario.get("countries_or_regions", ["United States"]),
            "time_horizon": scenario["scenario_duration"],
            "probability": scenario["probability"],
            "risks": scenario.get("risks", []),
            "invalidation_triggers": scenario.get("invalidation_triggers", []),
        },
        "executive_outlook": _executive_outlook(scenario, opportunities, hedges),
        "base_case": {
            "probability": scenario["probability"],
            "growth_path": _growth_path(scenario),
            "inflation_path": _inflation_path(scenario),
            "central_bank_response": _central_bank_response(scenario),
            "market_consequence": _market_consequence(cross_asset),
        },
        "bull_case": {
            "probability": round(max(0.05, 1 - scenario["probability"] - scenario["recession_probability"]), 2),
            "key_trigger": "Inflation pressure proves temporary while nominal growth remains firm.",
            "likely_winners": ["quality equities", "cyclicals", "credit", "REITs"],
        },
        "bear_tail_case": {
            "probability": scenario["recession_probability"],
            "key_trigger": "Inflation remains sticky enough to force a sharper central-bank catch-up.",
            "likely_losers": ["long-duration equities", "long nominal duration", "high-yield credit"],
            "defensive_response": "Keep hedges explicit, shorten review intervals, and require confirmation before increasing risk.",
        },
        "cross_asset_outlook": cross_asset,
        "top_opportunities": opportunities,
        "recommended_hedges": hedges,
        "historical_analogs": _analog_rows(analogs, performance),
        "what_would_change_the_view": {
            "confirming_indicators": _confirming_indicators(scenario),
            "invalidating_indicators": scenario.get("invalidation_triggers", []),
        },
        "data_to_watch_next": _data_to_watch(scenario),
        "debate_summary": _debate_summary(scenario, opportunities, hedges),
        "approval_status": {
            "approved_content": [],
            "pending_content": [item["name"] for item in opportunities] + [item["hedge_name"] for item in hedges],
            "note": "Research hypothesis - requires human review before use in training data or investment decisions.",
        },
        "disclaimer": "Research hypotheses for human review only. No trade execution or guaranteed outcomes.",
    }
    return outlook


def data_mode_label(snapshot: dict[str, Any]) -> str:
    statuses = snapshot.get("source_status", {}) if isinstance(snapshot, dict) else {}
    if not statuses:
        return "Demo Mode: Some outputs are based on fallback data and should not be treated as live investment research."
    unavailable = [value for value in statuses.values() if "unavailable" in str(value).lower() or "error" in str(value).lower()]
    if unavailable:
        return "Demo Mode: Some outputs are based on fallback data and should not be treated as live investment research."
    return "Live Data Mode"


def outlook_to_markdown(outlook: dict[str, Any]) -> str:
    scenario = outlook["scenario_definition"]
    lines = [
        "# HCP Investment Committee Report",
        "",
        f"Run ID: {outlook['run_id']}",
        f"Run Date: {outlook['run_date']}",
        f"Data Mode: {outlook['data_mode']}",
        "",
        "## Executive Summary",
        outlook["executive_outlook"],
        "",
        "## Scenario Definition",
        _bullet_dict(scenario),
        "",
        "## Macro Outlook",
        _bullet_dict(outlook["base_case"]),
        "",
        "## Central Bank Outlook",
        str(outlook["base_case"]["central_bank_response"]),
        "",
        "## Historical Analogs",
        _table(outlook["historical_analogs"], ["period", "similarity_score", "why_it_matters", "why_it_may_fail"]),
        "",
        "## Cross-Asset Allocation",
        _table(outlook["cross_asset_outlook"], ["asset_class", "expected_direction", "conviction", "rationale", "main_risk"]),
        "",
        "## Ranked Opportunities",
        _table(outlook["top_opportunities"], ["name", "asset_class", "direction", "conviction_score", "proxy_ticker", "invalidation_condition"]),
        "",
        "## Ranked Hedges",
        _table(outlook["recommended_hedges"], ["hedge_name", "risk_protected_against", "implementation_concept", "expected_payoff_condition"]),
        "",
        "## Key Risks",
        _bullets(scenario.get("risks", [])),
        "",
        "## Probability Distribution",
        _bullet_dict({"base_case": outlook["base_case"]["probability"], "bull_case": outlook["bull_case"]["probability"], "bear_tail_case": outlook["bear_tail_case"]["probability"]}),
        "",
        "## Debate Summary",
        outlook["debate_summary"],
        "",
        "## Invalidation Conditions",
        _bullets(outlook["what_would_change_the_view"]["invalidating_indicators"]),
        "",
        "## Indicators to Watch",
        _bullets(outlook["data_to_watch_next"]),
        "",
        "## Conclusion",
        "Treat the output as a prioritized research agenda. The investment implication is conditional, measurable, and subject to human approval.",
        "",
        "## Disclaimer",
        outlook["disclaimer"],
        "",
    ]
    return "\n".join(lines)


def _normalize_scenario(scenario: dict[str, Any], demo: bool = False) -> dict[str, Any]:
    defaults = DEMO_SCENARIO if demo else {}
    merged = {**defaults, **scenario}
    model = MacroScenario(
        scenario_name=merged.get("scenario_name") or "Custom Macro Scenario",
        scenario_date=merged.get("scenario_date") or datetime.utcnow().date().isoformat(),
        growth_direction=merged.get("growth_direction") or merged.get("growth_outlook") or "mixed",
        inflation_direction=merged.get("inflation_direction") or merged.get("inflation_outlook") or "mixed",
        inflation_surprise=merged.get("inflation_surprise") or "modest",
        central_bank_policy_stance=merged.get("central_bank_policy_stance") or merged.get("central_bank_stance") or "neutral",
        expected_policy_path=merged.get("expected_policy_path") or merged.get("expected_policy_response") or "data dependent",
        central_bank_curve_position=merged.get("central_bank_curve_position") or "neutral",
        labor_market_conditions=merged.get("labor_market_conditions") or "mixed",
        financial_conditions=merged.get("financial_conditions") or "mixed",
        fiscal_conditions=merged.get("fiscal_conditions") or "neutral",
        recession_probability=float(merged.get("recession_probability", 0.3)),
        scenario_duration=merged.get("scenario_duration") or merged.get("time_horizon") or "7-14 months",
        probability=float(merged.get("probability", 0.5)),
        conviction=float(merged.get("conviction", 7.0)),
        invalidation_triggers=list(merged.get("invalidation_triggers", [])),
    )
    payload = model.__dict__
    payload["scenario_description"] = merged.get("scenario_description", "")
    payload["countries_or_regions"] = merged.get("countries_or_regions", ["United States"])
    payload["risks"] = merged.get("risks", [])
    return payload


def _dedupe_recommendations(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for row in sorted(recommendations, key=lambda item: (item.get("conviction", 0), item.get("probability_of_success", 0)), reverse=True):
        key = (row.get("asset_or_trade"), row.get("direction"), row.get("category"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _opportunity_row(row: dict[str, Any]) -> dict[str, Any]:
    proxy, benchmark = PROXY_MAP.get(row["asset_or_trade"], ("SPY", "SPY"))
    return {
        "label": "Research hypothesis - requires human review.",
        "name": row["asset_or_trade"],
        "asset_class": row["asset_class"],
        "direction": row["direction"],
        "conviction_score": row["conviction"],
        "expected_horizon": row["expected_time_horizon"],
        "proxy_ticker": proxy,
        "benchmark": benchmark,
        "conditions_for_entry": "Enter research queue when incoming data confirms the scenario direction and liquidity is adequate.",
        "conditions_for_exit": "Exit or resize if the invalidation condition is met or realized data contradicts the thesis.",
        "thesis": row["investment_thesis"],
        "catalyst": "Scenario confirmation through inflation, rates, growth, and policy reaction data.",
        "risks": row["major_risks"],
        "invalidation_condition": row["invalidation_condition"],
    }


def _hedge_row(row: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    proxy, _ = PROXY_MAP.get(row["asset_or_trade"], ("GLD", "SPY"))
    return {
        "label": "Research hypothesis - requires human review.",
        "hedge_name": row["asset_or_trade"],
        "risk_protected_against": "Policy mistake, growth shock, or inflation credibility risk.",
        "implementation_concept": f"Use proxy {proxy} as the measurable research instrument; size against approved portfolio risk.",
        "expected_cost_or_drag": "May lag in risk-on periods or when real yields move against the hedge.",
        "expected_payoff_condition": row["investment_thesis"],
        "major_limitation": row["invalidation_condition"],
    }


def _fallback_hedge(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": "Research hypothesis - requires human review.",
        "hedge_name": "Gold / policy credibility hedge",
        "risk_protected_against": "Sticky inflation and delayed central-bank response.",
        "implementation_concept": "Use GLD as a proxy for measurement; human review required.",
        "expected_cost_or_drag": "Can drag if real yields rise sharply.",
        "expected_payoff_condition": "Pays if inflation credibility or policy confidence deteriorates.",
        "major_limitation": "Fails if inflation falls quickly and real yields rise.",
    }


def _cross_asset_outlook(scenario: dict[str, Any], recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assets = ["equities", "government bonds", "credit", "currencies", "commodities", "gold", "oil", "crypto", "REITs", "MLPs", "cash"]
    rows = []
    for asset in assets:
        rec = _matching_rec(asset, recommendations)
        if rec:
            direction = rec["direction"]
            conviction = rec["conviction"]
            rationale = rec["investment_thesis"]
            risk = rec["invalidation_condition"]
        else:
            direction, conviction, rationale, risk = _default_asset_view(asset, scenario)
        rows.append(
            {
                "asset_class": asset,
                "expected_direction": direction,
                "conviction": conviction,
                "time_horizon": scenario["scenario_duration"],
                "rationale": rationale,
                "main_risk": risk,
            }
        )
    return rows


def _matching_rec(asset: str, recommendations: list[dict[str, Any]]) -> dict[str, Any] | None:
    text = asset.lower()
    for rec in recommendations:
        haystack = f"{rec.get('asset_or_trade', '')} {rec.get('asset_class', '')}".lower()
        if text.split()[0] in haystack or ("gold" in text and "gold" in haystack) or ("oil" in text and "energy" in haystack):
            return rec
    return None


def _default_asset_view(asset: str, scenario: dict[str, Any]) -> tuple[str, float, str, str]:
    if scenario["inflation_direction"] in {"rising", "elevated"} and asset in {"commodities", "gold", "oil", "MLPs"}:
        return "positive / overweight candidate", 6.8, "Inflation surprise can support real assets and nominal cash-flow beneficiaries.", "Inflation rolls over or real rates rise sharply."
    if scenario["central_bank_policy_stance"] == "delayed_tightening" and asset == "cash":
        return "neutral", 5.5, "Cash optionality improves if policy repricing becomes disorderly.", "Risk assets continue higher without volatility."
    if asset in {"government bonds", "credit", "crypto"}:
        return "cautious / underweight candidate", 6.2, "Delayed tightening with inflation surprise can pressure duration-sensitive assets.", "Growth shock forces dovish repricing."
    return "mixed / selective", 5.8, "Scenario creates dispersion; require instrument-level confirmation.", "Scenario fails to translate into asset-price leadership."


def _analog_rows(analogs: dict[str, Any], performance: dict[str, Any]) -> list[dict[str, Any]]:
    perf_by_period: dict[str, list[dict[str, Any]]] = {}
    for row in performance.get("rows", []):
        perf_by_period.setdefault(row["period"], []).append(row)
    rows = []
    for analog in analogs.get("ranked_historical_analogs", []):
        period_perf = perf_by_period.get(analog["period"], [])[:5]
        rows.append(
            {
                "period": analog["period"],
                "similarity_score": analog["similarity_score"],
                "matching_conditions": analog["matching_features"],
                "major_differences": analog["important_differences"],
                "subsequent_asset_performance": [
                    {"asset_class": item["asset_class"], **item["returns"]} for item in period_perf
                ],
                "why_it_matters": analog["historical_regime_description"],
                "why_it_may_fail": analog["not_exact_forecast"],
            }
        )
    return rows


def _executive_outlook(scenario: dict[str, Any], opportunities: list[dict[str, Any]], hedges: list[dict[str, Any]]) -> str:
    lead = opportunities[0]["name"] if opportunities else "selective cross-asset opportunities"
    hedge = hedges[0]["hedge_name"] if hedges else "explicit downside hedges"
    return (
        f"The scenario describes a {scenario['scenario_duration']} window where growth remains {scenario['growth_direction']} "
        f"while inflation is {scenario['inflation_direction']} and policy is {scenario['central_bank_policy_stance'].replace('_', ' ')}. "
        f"The central macro implication is that nominal growth may stay firm before central banks fully react, which can favor real-asset and inflation-sensitive research hypotheses. "
        f"The main investment implication is to prioritize {lead} while avoiding unhedged exposure to assets most vulnerable to higher real-rate repricing. "
        f"Central-bank risk is asymmetric because a delayed response can eventually require faster tightening. "
        f"The recommended posture is opportunity-led but risk-controlled, with {hedge} reviewed as a hedge rather than a standalone forecast. "
        f"Every recommendation remains conditional and requires human approval."
    )


def _growth_path(scenario: dict[str, Any]) -> str:
    return f"Growth expected to remain {scenario['growth_direction']} over the stated horizon unless labor or credit data weakens."


def _inflation_path(scenario: dict[str, Any]) -> str:
    return f"Inflation expected to be {scenario['inflation_direction']} with surprise risk skewed {scenario['inflation_surprise']}."


def _central_bank_response(scenario: dict[str, Any]) -> str:
    return f"Central banks likely remain {scenario['central_bank_policy_stance'].replace('_', ' ')} initially; expected path: {scenario['expected_policy_path']}."


def _market_consequence(cross_asset: list[dict[str, Any]]) -> str:
    positives = [row["asset_class"] for row in cross_asset if "positive" in row["expected_direction"] or "overweight" in row["expected_direction"]]
    cautious = [row["asset_class"] for row in cross_asset if "underweight" in row["expected_direction"] or "cautious" in row["expected_direction"]]
    return f"Likely support for {', '.join(positives[:4]) or 'selective risk assets'}; caution on {', '.join(cautious[:4]) or 'crowded duration exposure'}."


def _confirming_indicators(scenario: dict[str, Any]) -> list[str]:
    return [
        "Core CPI/PCE and inflation expectations continue to surprise higher.",
        "Payrolls, wages, and real activity data remain resilient.",
        "Fed communication stays patient relative to incoming inflation data.",
        "Commodity and breakeven signals confirm sticky nominal pressure.",
    ]


def _data_to_watch(scenario: dict[str, Any]) -> list[str]:
    return [
        "CPI and core PCE inflation releases",
        "Payrolls, unemployment rate, and wage growth",
        "FOMC statement, dot plot, and press conference language",
        "10-year Treasury yield, real yields, and breakeven inflation",
        "Oil, gold, and broad commodity indexes",
        "Credit spreads and financial conditions indexes",
    ]


def _debate_summary(scenario: dict[str, Any], opportunities: list[dict[str, Any]], hedges: list[dict[str, Any]]) -> str:
    strongest = opportunities[0]["name"] if opportunities else "no single opportunity"
    weakest = "timing risk: the scenario can be directionally right but early."
    hidden = "central banks may shift from delayed to abrupt tightening faster than the base case assumes."
    hedge = hedges[0]["hedge_name"] if hedges else "no hedge identified"
    return (
        f"Consensus view: the scenario is internally consistent and most supportive of {strongest}. "
        f"Main disagreement: how quickly central banks respond if inflation remains firm. "
        f"Weakest reasoning: {weakest} Hidden risk: {hidden} Highest-conviction hedge to review: {hedge}."
    )


def _table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "None recorded."
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(_compact(row.get(column, "")) for column in columns) + " |")
    return "\n".join([header, divider, *body])


def _bullet_dict(values: dict[str, Any]) -> str:
    return "\n".join(f"- {key.replace('_', ' ').title()}: {_compact(value)}" for key, value in values.items())


def _bullets(values: list[Any]) -> str:
    return "\n".join(f"- {_compact(value)}" for value in values) if values else "None recorded."


def _compact(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(_compact(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {_compact(item)}" for key, item in value.items())
    return str(value).replace("\n", " ").replace("|", "/")
