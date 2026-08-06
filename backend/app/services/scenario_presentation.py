from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from typing import Any

from app.connectors import ingest_all_sources
from app.models.scenario_parser import ParsedScenario
from app.services.database import list_investment_committee_reports, save_investment_committee_report
from app.services.ollama_provider import OllamaProvider
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
    "Defense and aerospace beneficiaries": ("ITA", "SPY"),
    "Infrastructure and industrial capex beneficiaries": ("PAVE", "SPY"),
    "Industrial metals producers": ("XME", "SPY"),
    "TIPS breakeven exposure": ("TIP", "IEF"),
    "Gold": ("GLD", "SPY"),
    "Two-stage gold hedge": ("GLD", "BIL"),
    "Long-duration nominal bonds": ("TLT", "IEF"),
    "US dollar": ("UUP", "BIL"),
    "Long US dollar": ("UUP", "BIL"),
    "Value over growth": ("VLUE", "SPY"),
    "Quality balance-sheet equities": ("QUAL", "SPY"),
    "High-yield credit": ("HYG", "IEF"),
    "Intermediate government bonds": ("IEF", "BIL"),
    "Equity volatility": ("VIXY", "SPY"),
    "Defensive equities": ("SPLV", "SPY"),
    "Small caps": ("IWM", "SPY"),
    "Short high-yield credit / own quality credit": ("HYG", "LQD"),
    "Long equity volatility": ("VIXY", "SPY"),
    "Commodity shock basket": ("DBC", "SPY"),
    "Defensive cash / T-bills": ("BIL", "SPY"),
    "Underweight long-duration technology": ("QQQ", "SPY"),
    "Underweight REITs": ("VNQ", "SPY"),
}

GROWTH_OPTIONS = ["strong acceleration", "moderate growth", "slowing growth", "stagnation", "recession"]
INFLATION_OPTIONS = ["sharply higher", "moderately higher", "stable", "disinflation", "deflation"]
INFLATION_SURPRISE_OPTIONS = ["large downside surprise", "small downside surprise", "in line", "small upside surprise", "large upside surprise"]
VOLATILITY_OPTIONS = ["very low", "low", "normal", "high", "crisis"]
CENTRAL_BANK_OPTIONS = ["aggressively easing", "gradually easing", "neutral", "gradually tightening", "aggressively tightening"]
FED_POSITION_OPTIONS = ["ahead of the curve", "roughly on time", "behind the curve"]
LABOR_OPTIONS = ["overheating", "strong", "cooling", "weak", "recessionary"]
FINANCIAL_CONDITIONS_OPTIONS = ["very loose", "loose", "neutral", "tight", "severely tight"]
DOLLAR_OPTIONS = ["sharply weaker", "moderately weaker", "stable", "moderately stronger", "sharply stronger"]
COMMODITY_SHOCK_OPTIONS = ["none", "energy shock", "food shock", "metals shock", "broad commodity shock"]
EQUITY_VALUATION_OPTIONS = ["very cheap", "cheap", "fair", "expensive", "very expensive"]
TIME_HORIZON_OPTIONS = ["1-3 months", "3-6 months", "6-12 months", "7-14 months", "12-24 months"]
REGION_OPTIONS = ["U.S.", "Eurozone", "U.K.", "Japan", "China", "India", "emerging markets"]


SCENARIO_PRESETS = {
    "Inflation Surprise + Strong Growth": {
        "scenario_name": "Inflation Surprise + Strong Growth",
        "scenario_description": "Inflation surprises higher while growth remains resilient and policy response lags.",
        "growth_outlook": "strong acceleration",
        "inflation_direction": "sharply higher",
        "inflation_surprise": "large upside surprise",
        "recession_probability": 0.2,
        "market_volatility": "normal",
        "central_bank_stance": "gradually tightening",
        "fed_position": "behind the curve",
        "labor_market": "overheating",
        "financial_conditions": "loose",
        "credit_stress": 2,
        "dollar_outlook": "moderately stronger",
        "commodity_shock": "energy shock",
        "equity_valuation": "expensive",
        "time_horizon": "7-14 months",
        "probability": 0.55,
        "countries_or_regions": ["U.S.", "Eurozone"],
        "custom_assumptions": "Watch whether higher nominal growth supports real assets before policy catches up.",
    },
    "Fed Behind the Curve": {
        "scenario_name": "Fed Behind the Curve",
        "scenario_description": "The Fed reacts too slowly to persistent inflation and financial conditions remain too easy.",
        "growth_outlook": "moderate growth",
        "inflation_direction": "moderately higher",
        "inflation_surprise": "small upside surprise",
        "recession_probability": 0.3,
        "market_volatility": "high",
        "central_bank_stance": "gradually tightening",
        "fed_position": "behind the curve",
        "labor_market": "strong",
        "financial_conditions": "loose",
        "credit_stress": 3,
        "dollar_outlook": "moderately stronger",
        "commodity_shock": "none",
        "equity_valuation": "expensive",
        "time_horizon": "6-12 months",
        "probability": 0.5,
        "countries_or_regions": ["U.S."],
    },
    "Fed Overtightening / Recession": {
        "scenario_name": "Fed Overtightening / Recession",
        "scenario_description": "Restrictive policy bites harder than expected and recession risk becomes the dominant regime.",
        "growth_outlook": "recession",
        "inflation_direction": "disinflation",
        "inflation_surprise": "small downside surprise",
        "recession_probability": 0.7,
        "market_volatility": "crisis",
        "central_bank_stance": "aggressively tightening",
        "fed_position": "ahead of the curve",
        "labor_market": "recessionary",
        "financial_conditions": "severely tight",
        "credit_stress": 8,
        "dollar_outlook": "sharply stronger",
        "commodity_shock": "none",
        "equity_valuation": "fair",
        "time_horizon": "6-12 months",
        "probability": 0.45,
        "countries_or_regions": ["U.S.", "Eurozone", "emerging markets"],
    },
    "Soft Landing": {
        "scenario_name": "Soft Landing",
        "scenario_description": "Growth slows but avoids recession while inflation cools enough for policy to become less restrictive.",
        "growth_outlook": "moderate growth",
        "inflation_direction": "disinflation",
        "inflation_surprise": "in line",
        "recession_probability": 0.25,
        "market_volatility": "low",
        "central_bank_stance": "gradually easing",
        "fed_position": "roughly on time",
        "labor_market": "cooling",
        "financial_conditions": "neutral",
        "credit_stress": 3,
        "dollar_outlook": "moderately weaker",
        "commodity_shock": "none",
        "equity_valuation": "fair",
        "time_horizon": "7-14 months",
        "probability": 0.5,
        "countries_or_regions": ["U.S.", "Eurozone", "Japan"],
    },
    "Stagflation": {
        "scenario_name": "Stagflation",
        "scenario_description": "Growth stagnates while inflation rises and policy faces a bad trade-off.",
        "growth_outlook": "stagnation",
        "inflation_direction": "sharply higher",
        "inflation_surprise": "large upside surprise",
        "recession_probability": 0.55,
        "market_volatility": "high",
        "central_bank_stance": "gradually tightening",
        "fed_position": "behind the curve",
        "labor_market": "cooling",
        "financial_conditions": "tight",
        "credit_stress": 6,
        "dollar_outlook": "moderately stronger",
        "commodity_shock": "broad commodity shock",
        "equity_valuation": "expensive",
        "time_horizon": "7-14 months",
        "probability": 0.4,
        "countries_or_regions": ["U.S.", "Eurozone", "U.K."],
    },
    "Deflation Shock": {
        "scenario_name": "Deflation Shock",
        "scenario_description": "Demand weakens abruptly, inflation falls below expectations, and policy pivots toward easing.",
        "growth_outlook": "recession",
        "inflation_direction": "deflation",
        "inflation_surprise": "large downside surprise",
        "recession_probability": 0.75,
        "market_volatility": "crisis",
        "central_bank_stance": "aggressively easing",
        "fed_position": "ahead of the curve",
        "labor_market": "recessionary",
        "financial_conditions": "severely tight",
        "credit_stress": 9,
        "dollar_outlook": "moderately stronger",
        "commodity_shock": "none",
        "equity_valuation": "cheap",
        "time_horizon": "3-6 months",
        "probability": 0.3,
        "countries_or_regions": ["U.S.", "China", "emerging markets"],
    },
    "Risk-On Liquidity Boom": {
        "scenario_name": "Risk-On Liquidity Boom",
        "scenario_description": "Liquidity improves, policy is easier than feared, and risk appetite broadens.",
        "growth_outlook": "strong acceleration",
        "inflation_direction": "stable",
        "inflation_surprise": "in line",
        "recession_probability": 0.15,
        "market_volatility": "very low",
        "central_bank_stance": "gradually easing",
        "fed_position": "roughly on time",
        "labor_market": "strong",
        "financial_conditions": "very loose",
        "credit_stress": 1,
        "dollar_outlook": "moderately weaker",
        "commodity_shock": "none",
        "equity_valuation": "fair",
        "time_horizon": "3-6 months",
        "probability": 0.45,
        "countries_or_regions": ["U.S.", "emerging markets"],
    },
    "Dollar Squeeze": {
        "scenario_name": "Dollar Squeeze",
        "scenario_description": "Global funding stress and U.S. rate support push the dollar sharply higher.",
        "growth_outlook": "slowing growth",
        "inflation_direction": "stable",
        "inflation_surprise": "in line",
        "recession_probability": 0.45,
        "market_volatility": "high",
        "central_bank_stance": "gradually tightening",
        "fed_position": "ahead of the curve",
        "labor_market": "cooling",
        "financial_conditions": "tight",
        "credit_stress": 7,
        "dollar_outlook": "sharply stronger",
        "commodity_shock": "none",
        "equity_valuation": "expensive",
        "time_horizon": "1-3 months",
        "probability": 0.35,
        "countries_or_regions": ["U.S.", "emerging markets", "Japan"],
    },
    "Commodity Supply Shock": {
        "scenario_name": "Commodity Supply Shock",
        "scenario_description": "Supply disruption lifts commodity prices and pushes inflation risk higher.",
        "growth_outlook": "slowing growth",
        "inflation_direction": "sharply higher",
        "inflation_surprise": "large upside surprise",
        "recession_probability": 0.5,
        "market_volatility": "high",
        "central_bank_stance": "gradually tightening",
        "fed_position": "behind the curve",
        "labor_market": "cooling",
        "financial_conditions": "tight",
        "credit_stress": 5,
        "dollar_outlook": "stable",
        "commodity_shock": "broad commodity shock",
        "equity_valuation": "fair",
        "time_horizon": "6-12 months",
        "probability": 0.4,
        "countries_or_regions": ["U.S.", "Eurozone", "China", "emerging markets"],
    },
    "Credit Stress Event": {
        "scenario_name": "Credit Stress Event",
        "scenario_description": "Credit spreads widen, refinancing risk rises, and equity risk appetite deteriorates.",
        "growth_outlook": "slowing growth",
        "inflation_direction": "disinflation",
        "inflation_surprise": "small downside surprise",
        "recession_probability": 0.65,
        "market_volatility": "crisis",
        "central_bank_stance": "gradually easing",
        "fed_position": "behind the curve",
        "labor_market": "weak",
        "financial_conditions": "severely tight",
        "credit_stress": 9,
        "dollar_outlook": "moderately stronger",
        "commodity_shock": "none",
        "equity_valuation": "cheap",
        "time_horizon": "3-6 months",
        "probability": 0.35,
        "countries_or_regions": ["U.S.", "Eurozone"],
    },
}


def scenario_input_options() -> dict[str, Any]:
    return {
        "growth_outlook": GROWTH_OPTIONS,
        "inflation_direction": INFLATION_OPTIONS,
        "inflation_surprise": INFLATION_SURPRISE_OPTIONS,
        "market_volatility": VOLATILITY_OPTIONS,
        "central_bank_stance": CENTRAL_BANK_OPTIONS,
        "fed_position": FED_POSITION_OPTIONS,
        "labor_market": LABOR_OPTIONS,
        "financial_conditions": FINANCIAL_CONDITIONS_OPTIONS,
        "dollar_outlook": DOLLAR_OPTIONS,
        "commodity_shock": COMMODITY_SHOCK_OPTIONS,
        "equity_valuation": EQUITY_VALUATION_OPTIONS,
        "time_horizon": TIME_HORIZON_OPTIONS,
        "countries_or_regions": REGION_OPTIONS,
        "presets": {name: dict(payload) for name, payload in SCENARIO_PRESETS.items()},
    }


PARSER_STATUS = {
    "mode": "Rule-Based Parser Fallback",
    "latest_successful_parse": None,
    "latest_parse_duration_ms": None,
    "fallback_count": 0,
    "latest_parser_error": None,
}


def parse_free_text_scenario(text: str, force_rule_fallback: bool = False) -> dict[str, Any]:
    provider = os.getenv("HCP_SCENARIO_PARSER_PROVIDER", "ollama").lower()
    if force_rule_fallback:
        PARSER_STATUS["fallback_count"] = int(PARSER_STATUS.get("fallback_count", 0)) + 1
        PARSER_STATUS["mode"] = "Rule-Based Parser Fallback"
        parsed = _validated_parsed_scenario(rule_based_parse_free_text_scenario(text), text, "rule_fallback", "rule-based-parser", None)
        return parsed.to_legacy_scenario()
    if provider == "ollama" and not force_rule_fallback:
        result = OllamaProvider().parse_scenario(text)
        if result.ok and result.payload:
            try:
                parsed = _validated_parsed_scenario(result.payload, text, "ollama", result.model, result.duration_ms)
                PARSER_STATUS.update(
                    {
                        "mode": "Local Scenario Parser — Connected",
                        "latest_successful_parse": datetime.utcnow().isoformat(),
                        "latest_parse_duration_ms": result.duration_ms,
                        "latest_parser_error": None,
                    }
                )
                return parsed.to_legacy_scenario()
            except Exception as exc:
                PARSER_STATUS["latest_parser_error"] = f"schema validation failed: {exc}"
        else:
            PARSER_STATUS["latest_parser_error"] = result.error
    raise RuntimeError(PARSER_STATUS.get("latest_parser_error") or "Ollama scenario parser unavailable")


def ollama_parser_health() -> dict[str, Any]:
    health = OllamaProvider().health()
    mode = "Local Scenario Parser — Connected" if health["reachable"] and health["model_available"] else "Rule-Based Parser Fallback"
    return {
        **health,
        "scenario_parser_mode": mode,
        "latest_successful_parse": PARSER_STATUS.get("latest_successful_parse"),
        "latest_parse_duration_ms": PARSER_STATUS.get("latest_parse_duration_ms"),
        "fallback_count": PARSER_STATUS.get("fallback_count", 0),
        "latest_parser_error": PARSER_STATUS.get("latest_parser_error") or health.get("error"),
    }


def rule_based_parse_free_text_scenario(text: str) -> dict[str, Any]:
    lower = text.lower()
    scenario = {
        "scenario_name": "Inflation Surprise / Fed Behind the Curve" if _behind_curve(lower) and _inflation_up(lower) else _title_from_text(text),
        "scenario_description": text.strip(),
        "growth_outlook": "moderate growth",
        "inflation_direction": "stable",
        "inflation_surprise": "in line",
        "recession_probability": 0.3,
        "market_volatility": "normal",
        "central_bank_stance": "neutral",
        "fed_position": "roughly on time",
        "labor_market": "cooling",
        "financial_conditions": "neutral",
        "credit_stress": 3,
        "dollar_outlook": "stable",
        "commodity_shock": "none",
        "equity_valuation": "fair",
        "time_horizon": "7-14 months",
        "probability": None,
        "countries_or_regions": ["U.S."],
        "risks": [],
        "invalidation_triggers": [],
    }
    confidence: dict[str, float] = {
        "scenario_name": 0.7,
        "growth_outlook": 0.45,
        "inflation_direction": 0.45,
        "inflation_surprise": 0.4,
        "central_bank_stance": 0.45,
        "fed_position": 0.45,
        "labor_market": 0.4,
        "financial_conditions": 0.35,
        "market_volatility": 0.4,
        "credit_stress": 0.35,
        "dollar_outlook": 0.35,
        "commodity_shock": 0.35,
        "equity_valuation": 0.2,
        "time_horizon": 0.4,
        "recession_probability": 0.4,
        "probability": 0.0,
    }

    if any(term in lower for term in ["growth continues to grow", "economy continues to grow", "continues to grow, but at a slower", "grow, but at a slower", "slower pace than before", "growth remains positive but slows", "growth weakens"]):
        scenario["growth_outlook"] = "slowing growth"
        confidence["growth_outlook"] = 0.9
    elif any(term in lower for term in ["growth remains strong", "strong growth"]):
        scenario["growth_outlook"] = "moderate growth" if any(term in lower for term in ["slower pace", "slows", "slowing"]) else "strong acceleration"
        confidence["growth_outlook"] = 0.75
    elif any(term in lower for term in ["growth accelerates", "accelerating growth"]):
        scenario["growth_outlook"] = "strong acceleration"
        confidence["growth_outlook"] = 0.85
    elif any(term in lower for term in ["recession", "hard landing", "contraction", "downturn"]) and not any(term in lower for term in ["probability", "risk", "if the fed", "eventually", "mild recession"]):
        scenario["growth_outlook"] = "recession"
        confidence["growth_outlook"] = 0.75

    if _inflation_up(lower):
        scenario["inflation_direction"] = "moderately higher"
        confidence["inflation_direction"] = 0.9
        scenario["inflation_surprise"] = "small upside surprise"
        confidence["inflation_surprise"] = 0.8
    if any(term in lower for term in ["inflation surprises higher", "large upside", "surprises higher"]):
        scenario["inflation_surprise"] = "large upside surprise"
        confidence["inflation_surprise"] = 0.9
    elif any(term in lower for term in ["upside surprise", "surprise higher", "higher than expected"]):
        scenario["inflation_surprise"] = "small upside surprise"
        confidence["inflation_surprise"] = 0.85
    if any(term in lower for term in ["disinflation", "inflation cools", "inflation falls", "inflation declines"]) and not _inflation_up(lower):
        scenario["inflation_direction"] = "disinflation"
        scenario["inflation_surprise"] = "small downside surprise"
        confidence["inflation_direction"] = 0.85
        confidence["inflation_surprise"] = 0.75

    if _behind_curve(lower):
        scenario["fed_position"] = "behind the curve"
        scenario["central_bank_stance"] = "gradually tightening"
        scenario["expected_policy_path"] = "The Fed treats inflation as temporary and delays tightening, raising the risk of a later catch-up."
        confidence["fed_position"] = 0.95
        confidence["central_bank_stance"] = 0.85
    elif any(term in lower for term in ["fed overtightening", "overtightening", "aggressive tightening", "tightens aggressively"]):
        scenario["central_bank_stance"] = "aggressively tightening"
        scenario["fed_position"] = "ahead of the curve"
        confidence["central_bank_stance"] = 0.85
        confidence["fed_position"] = 0.75
    elif any(term in lower for term in ["fed cuts", "easing", "pivot"]):
        scenario["central_bank_stance"] = "gradually easing"
        confidence["central_bank_stance"] = 0.75

    if any(term in lower for term in ["unemployment remains low", "low unemployment", "labor remains strong", "wage growth remains strong"]):
        scenario["labor_market"] = "strong"
        confidence["labor_market"] = 0.9
    elif any(term in lower for term in ["labor weakens", "unemployment rises", "jobless claims rise"]):
        scenario["labor_market"] = "cooling"
        confidence["labor_market"] = 0.7

    if any(term in lower for term in ["markets remain calm at first", "calm at first", "become more volatile", "more volatile as", "volatility rises later"]):
        scenario["market_volatility"] = "high"
        confidence["market_volatility"] = 0.85
    elif any(term in lower for term in ["volatility spike", "crisis", "panic"]):
        scenario["market_volatility"] = "crisis"
        confidence["market_volatility"] = 0.85
    elif "high volatility" in lower:
        scenario["market_volatility"] = "high"
        confidence["market_volatility"] = 0.75

    if any(term in lower for term in ["credit spreads stay relatively contained", "credit spreads stay contained", "spreads stay contained", "contained credit spreads"]):
        scenario["financial_conditions"] = "neutral"
        scenario["credit_stress"] = 3
        confidence["financial_conditions"] = 0.85
        confidence["credit_stress"] = 0.9
    elif any(term in lower for term in ["credit spreads widen", "credit stress", "refinancing stress", "credit conditions tighten", "credit conditions tight"]):
        scenario["financial_conditions"] = "tight"
        scenario["credit_stress"] = 7
        confidence["financial_conditions"] = 0.75
        confidence["credit_stress"] = 0.8

    if any(term in lower for term in ["financial markets remain calm at first", "markets remain calm at first"]):
        scenario["financial_conditions"] = "neutral"
        confidence["financial_conditions"] = max(confidence["financial_conditions"], 0.75)

    if any(term in lower for term in ["dollar strengthens", "dollar stronger", "usd strengthens", "usd stronger"]):
        scenario["dollar_outlook"] = "moderately stronger"
        confidence["dollar_outlook"] = 0.9
    elif any(term in lower for term in ["dollar sharply stronger", "usd sharply stronger", "dollar squeeze"]):
        scenario["dollar_outlook"] = "sharply stronger"
        confidence["dollar_outlook"] = 0.85
    elif any(term in lower for term in ["dollar weaker", "usd weaker", "dollar weakens", "usd weakens"]):
        scenario["dollar_outlook"] = "moderately weaker"
        confidence["dollar_outlook"] = 0.75

    if any(term in lower for term in ["energy prices increase", "energy prices and wages increase", "energy prices rise", "oil prices increase", "oil prices rise", "energy shock", "oil shock"]):
        scenario["commodity_shock"] = "energy shock"
        confidence["commodity_shock"] = 0.95
    elif any(term in lower for term in ["commodity prices continue to increase", "commodity prices rise", "commodity pressure", "commodity shock"]):
        scenario["commodity_shock"] = "broad commodity shock"
        confidence["commodity_shock"] = 0.8

    if any(term in lower for term in ["12 months", "next 12 months", "over the next 12"]):
        scenario["time_horizon"] = "6-12 months"
        confidence["time_horizon"] = 0.95
    elif any(term in lower for term in ["7-14 months", "7 to 14 months"]):
        scenario["time_horizon"] = "7-14 months"
        confidence["time_horizon"] = 0.95

    recession_pct = _extract_percentage_near(lower, ["recession", "falls into recession", "recession if"])
    if recession_pct is not None:
        scenario["recession_probability"] = recession_pct
        confidence["recession_probability"] = 1.0
    scenario_pct = _extract_percentage_near(lower, ["scenario probability", "probability of this scenario", "case probability"])
    if scenario_pct is not None:
        scenario["probability"] = scenario_pct
        confidence["probability"] = 1.0

    if any(term in lower for term in ["equity markets remain positive early", "equities remain positive early"]):
        scenario["custom_assumptions"] = "Equities positive early, then more volatile as higher-rate expectations build."

    scenario["risks"] = _parsed_risks(scenario)
    scenario["invalidation_triggers"] = _parsed_invalidation_triggers(scenario)
    warnings = _contradiction_warnings(lower, scenario)
    scenario["parser_confidence"] = sum(confidence.values()) / len(confidence)
    scenario["field_confidence"] = confidence
    scenario["field_excerpts"] = _rule_field_excerpts(text, scenario)
    scenario["low_confidence_fields"] = [field for field, score in confidence.items() if score < 0.55]
    scenario["contradiction_warnings"] = warnings
    scenario["parser_warnings"] = warnings
    scenario["parser_provider"] = "rule_fallback"
    scenario["parser_model"] = "rule-based-parser"
    scenario["source_text"] = text
    scenario["confirming_indicators"] = _confirming_indicators(scenario)
    scenario["stated_probabilities"] = _extract_all_probabilities(lower)
    scenario["phases"] = _rule_phases(lower)
    scenario["review_required"] = bool(warnings or scenario["low_confidence_fields"])
    return scenario


def scenario_summary(scenario: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_scenario(scenario)
    return {
        "growth": normalized["growth_outlook"],
        "inflation": normalized["inflation_direction"],
        "Fed stance": normalized["central_bank_stance"],
        "recession probability": f"{normalized['recession_probability']:.0%}",
        "volatility": normalized["market_volatility"],
        "credit stress": normalized["credit_stress"],
        "dollar": normalized["dollar_outlook"],
        "commodity shock": normalized["commodity_shock"],
        "time horizon": normalized["scenario_duration"],
        "scenario probability": "not specified" if normalized.get("probability") is None else f"{normalized['probability']:.0%}",
        "countries": ", ".join(normalized.get("countries_or_regions", [])),
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
        validation_error = validate_confirmed_scenario(payload)
        if validation_error:
            return {"status": "not_ready", "reason": "stale_or_unconfirmed_scenario", "warnings": [validation_error], "report": None}
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


def validate_confirmed_scenario(scenario: dict[str, Any]) -> str | None:
    scenario_id = scenario.get("scenario_id")
    scenario_hash = scenario.get("scenario_hash")
    confirmed_id = scenario.get("confirmed_scenario_id")
    confirmed_hash = scenario.get("confirmed_scenario_hash")
    if scenario_id or scenario_hash:
        if not confirmed_id or not confirmed_hash:
            return "Scenario analysis requires confirmed scenario ID and hash."
        if confirmed_id != scenario_id:
            return "Confirmed scenario ID does not match the current parsed scenario ID."
        if confirmed_hash != scenario_hash:
            return "Confirmed scenario hash does not match the current structured scenario."
        current_hash = scenario_hash_for_payload(scenario)
        if current_hash != scenario_hash:
            return "Structured input changed after confirmation; re-confirm before analysis."
    return None


def confirm_structured_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    confirmed = dict(scenario)
    confirmed["scenario_id"] = confirmed.get("scenario_id") or f"scenario_{uuid.uuid4().hex[:12]}"
    confirmed["scenario_hash"] = scenario_hash_for_payload(confirmed)
    confirmed["confirmed_scenario_id"] = confirmed["scenario_id"]
    confirmed["confirmed_scenario_hash"] = confirmed["scenario_hash"]
    return confirmed


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
    top_recs = _dedupe_recommendations(_scenario_specific_recommendations(scenario) + top_recs)
    opportunities = [_opportunity_row(row, scenario, rank=index) for index, row in enumerate([row for row in top_recs if row.get("category") not in {"hedge", "avoid"}][:8], start=1)]
    hedges = [_hedge_row(row, scenario) for row in top_recs if row.get("category") == "hedge"]
    if not hedges:
        hedges = [_fallback_hedge(scenario)]

    cross_asset = _cross_asset_outlook(scenario, top_recs)
    probabilities = _probability_detail(scenario)
    underweights = _underweights_to_avoid(scenario, top_recs)
    traceability = _traceability_map(scenario, data_snapshot, analogs, opportunities)
    confirming = _structured_confirming_indicators(scenario)
    invalidating = _structured_invalidating_indicators(scenario)
    risk_register = _risk_register(scenario, hedges)
    prior_report = _prior_report_comparison(scenario)
    outlook = {
        "status": "ok",
        "demo": demo,
        "run_id": phase["phase_id"],
        "run_date": datetime.utcnow().isoformat(),
        "data_mode": data_mode_label(data_snapshot),
        "scenario_definition": {
            "scenario_id": scenario.get("scenario_id"),
            "scenario_hash": scenario.get("scenario_hash"),
            "name": scenario["scenario_name"],
            "description": scenario.get("scenario_description", ""),
            "growth_outlook": scenario["growth_outlook"],
            "inflation_outlook": scenario["inflation_direction"],
            "central_bank_stance": scenario["central_bank_stance"],
            "expected_policy_response": scenario["expected_policy_path"],
            "countries_or_regions": scenario.get("countries_or_regions", ["United States"]),
            "time_horizon": scenario["scenario_duration"],
            "probability": scenario["probability"],
            "market_volatility": scenario["market_volatility"],
            "fed_position": scenario["fed_position"],
            "labor_market": scenario["labor_market"],
            "financial_conditions": scenario["financial_conditions"],
            "credit_stress": scenario["credit_stress"],
            "dollar_outlook": scenario["dollar_outlook"],
            "commodity_shock": scenario["commodity_shock"],
            "equity_valuation": scenario["equity_valuation"],
            "custom_assumptions": scenario.get("custom_assumptions", ""),
            "risks": scenario.get("risks", []),
            "invalidation_triggers": scenario.get("invalidation_triggers", []),
            "parser_provider": scenario.get("parser_provider"),
            "parser_model": scenario.get("parser_model"),
            "phases": scenario.get("phases", []),
            "stated_probabilities": scenario.get("stated_probabilities", {}),
        },
        "executive_outlook": _executive_outlook(scenario, opportunities, hedges),
        "macro_thesis": _macro_thesis(scenario, cross_asset),
        "scenario_probabilities": probabilities,
        "base_case": {
            "probability": _case_probabilities(scenario)["base"],
            "growth_path": _growth_path(scenario),
            "inflation_path": _inflation_path(scenario),
            "central_bank_response": _central_bank_response(scenario),
            "market_consequence": _market_consequence(cross_asset),
        },
        "bull_case": {
            "probability": _case_probabilities(scenario)["bull"],
            "key_trigger": "Inflation pressure proves temporary while nominal growth remains firm.",
            "likely_winners": ["quality equities", "cyclicals", "credit", "REITs"],
        },
        "bear_tail_case": {
            "probability": _case_probabilities(scenario)["bear_tail"],
            "key_trigger": "Inflation remains sticky enough to force a sharper central-bank catch-up.",
            "likely_losers": ["long-duration equities", "long nominal duration", "high-yield credit"],
            "defensive_response": "Keep hedges explicit, shorten review intervals, and require confirmation before increasing risk.",
        },
        "cross_asset_outlook": cross_asset,
        "top_opportunities": opportunities,
        "underweights_to_avoid": underweights,
        "recommended_hedges": hedges,
        "historical_analogs": _analog_rows(analogs, performance),
        "central_bank_analysis": _central_bank_analysis(scenario),
        "country_regional_views": _country_regional_views(scenario),
        "risk_register": risk_register,
        "what_would_change_the_view": {
            "confirming_indicators": confirming,
            "invalidating_indicators": invalidating,
        },
        "data_to_watch_next": _data_to_watch(scenario),
        "debate_summary": _debate_summary(scenario, opportunities, hedges),
        "traceability": traceability,
        "changes_since_last_report": prior_report,
        "decisions_for_investment_committee": _investment_committee_decisions(scenario, opportunities, underweights, hedges),
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
    fred_status = statuses.get("FRED", "")
    if "live" in str(fred_status).lower() or "connected" in str(fred_status).lower():
        return "Live Data Mode - FRED connected"
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
        "## Probability Framework",
        _probability_markdown(outlook["scenario_probabilities"]),
        "",
        "## Macro Thesis",
        _bullet_dict(outlook["macro_thesis"]),
        "",
        "## Macro Outlook",
        _bullet_dict(outlook["base_case"]),
        "",
        "## Base Case / Bull Case / Bear-Tail Case",
        _case_markdown(outlook),
        "",
        "## Central Bank Outlook",
        _bullet_dict(outlook["central_bank_analysis"]),
        "",
        "## Country and Regional Views",
        _table(outlook["country_regional_views"], ["region", "growth_outlook", "inflation_outlook", "central_bank_path", "currency_implication", "equity_implication", "bond_implication", "commodity_sensitivity", "major_risk"]),
        "",
        "## Historical Analogs",
        _table(outlook["historical_analogs"], ["period", "similarity_score", "matching_conditions", "major_differences", "subsequent_asset_performance", "why_it_matters", "why_it_may_fail", "supports_or_contradicts"]),
        "",
        "## Cross-Asset Outlook",
        _table(outlook["cross_asset_outlook"], ["asset_class", "expected_direction", "conviction", "time_horizon", "expected_return_range", "rationale", "key_catalyst", "main_risk", "invalidation_condition", "historical_analog_support", "data_support", "proxy_ticker"]),
        "",
        "## Ranked Opportunities",
        _table(outlook["top_opportunities"], ["rank", "label", "name", "asset_class", "direction", "proxy_ticker", "thesis", "why_now", "catalyst", "probability_of_success", "conviction_score", "upside_case", "downside_case", "invalidation_condition", "recommended_human_review_question"]),
        "",
        "## Underweights / Positions to Avoid",
        _table(outlook["underweights_to_avoid"], ["asset_or_exposure", "reason_to_avoid", "expected_failure_mechanism", "conditions_that_would_make_view_wrong", "tactical_or_strategic"]),
        "",
        "## Ranked Hedges",
        _table(outlook["recommended_hedges"], ["hedge_name", "hedge_category", "risk_protected_against", "implementation_concept", "expected_cost_or_drag", "expected_payoff_condition", "timing_considerations", "convexity_or_asymmetry", "major_limitation", "conditions_for_removing_hedge"]),
        "",
        "## Risk Register",
        _table(outlook["risk_register"], ["risk", "probability", "impact", "transmission_mechanism", "affected_assets", "early_warning_indicator", "hedge_or_response", "already_priced"]),
        "",
        "## Confirming Indicators",
        _table(outlook["what_would_change_the_view"]["confirming_indicators"], ["indicator", "current_status", "threshold_or_direction", "why_it_matters", "affected_recommendation"]),
        "",
        "## Invalidating Indicators",
        _table(outlook["what_would_change_the_view"]["invalidating_indicators"], ["indicator", "current_status", "threshold_or_direction", "why_it_matters", "affected_recommendation"]),
        "",
        "## Invalidation Conditions",
        _table(outlook["what_would_change_the_view"]["invalidating_indicators"], ["indicator", "threshold_or_direction", "why_it_matters", "affected_recommendation"]),
        "",
        "## What Changed Since the Last Report",
        _bullet_dict(outlook["changes_since_last_report"]),
        "",
        "## Debate Summary",
        outlook["debate_summary"],
        "",
        "## Indicators to Watch",
        _bullets(outlook["data_to_watch_next"]),
        "",
        "## Traceability",
        _table(outlook["traceability"], ["conclusion", "supporting_scenario_assumption", "supporting_data_source", "supporting_historical_analog", "supporting_agent_conclusion", "confidence_level"]),
        "",
        "## Decisions for the Investment Committee",
        _bullet_dict(outlook["decisions_for_investment_committee"]),
        "",
        "## Disclaimer",
        outlook["disclaimer"],
        "",
    ]
    return "\n".join(lines)


def _normalize_scenario(scenario: dict[str, Any], demo: bool = False) -> dict[str, Any]:
    defaults = DEMO_SCENARIO if demo else {}
    merged = {**defaults, **scenario}
    growth_outlook = _choice(merged, "growth_outlook", "growth_direction", default="moderate growth")
    inflation_direction = _choice(merged, "inflation_direction", default="stable")
    inflation_surprise = _choice(merged, "inflation_surprise", default="in line")
    central_bank_stance = _choice(merged, "central_bank_stance", "central_bank_policy_stance", default="neutral")
    fed_position = _choice(merged, "fed_position", "central_bank_curve_position", default="roughly on time")
    labor_market = _choice(merged, "labor_market", "labor_market_conditions", default="cooling")
    financial_conditions = _choice(merged, "financial_conditions", default="neutral")
    time_horizon = _choice(merged, "time_horizon", "scenario_duration", default="7-14 months")
    scenario_probability = _optional_probability(merged.get("probability"))
    model = MacroScenario(
        scenario_name=merged.get("scenario_name") or "Custom Macro Scenario",
        scenario_date=merged.get("scenario_date") or datetime.utcnow().date().isoformat(),
        growth_direction=_internal_growth(growth_outlook),
        inflation_direction=_internal_inflation(inflation_direction),
        inflation_surprise=_internal_inflation_surprise(inflation_surprise),
        central_bank_policy_stance=_internal_central_bank_stance(central_bank_stance, fed_position),
        expected_policy_path=merged.get("expected_policy_path") or merged.get("expected_policy_response") or "data dependent",
        central_bank_curve_position=_internal_fed_position(fed_position),
        labor_market_conditions=_internal_labor(labor_market),
        financial_conditions=_internal_financial_conditions(financial_conditions),
        fiscal_conditions=merged.get("fiscal_conditions") or "neutral",
        recession_probability=_clamp_probability(merged.get("recession_probability", 0.3)),
        scenario_duration=time_horizon,
        probability=scenario_probability if scenario_probability is not None else _case_probabilities_for_unspecified(merged),
        conviction=float(merged.get("conviction", 7.0)),
        invalidation_triggers=_as_list(merged.get("invalidation_triggers", [])),
    )
    payload = model.__dict__
    payload["growth_outlook"] = growth_outlook
    payload["inflation_direction"] = inflation_direction
    payload["inflation_surprise_label"] = inflation_surprise
    payload["central_bank_stance"] = central_bank_stance
    payload["fed_position"] = fed_position
    payload["labor_market"] = labor_market
    payload["financial_conditions"] = financial_conditions
    payload["market_volatility"] = _choice(merged, "market_volatility", default="normal")
    credit_value = merged.get("credit_stress")
    payload["credit_stress"] = max(0, min(10, int(float(credit_value if credit_value is not None else 3))))
    payload["dollar_outlook"] = _choice(merged, "dollar_outlook", default="stable")
    payload["commodity_shock"] = _choice(merged, "commodity_shock", default="none")
    payload["equity_valuation"] = _choice(merged, "equity_valuation", default="fair")
    payload["custom_assumptions"] = merged.get("custom_assumptions", "")
    payload["scenario_description"] = merged.get("scenario_description", "")
    payload["scenario_id"] = merged.get("scenario_id")
    payload["scenario_hash"] = merged.get("scenario_hash")
    payload["source_text"] = merged.get("source_text")
    payload["countries_or_regions"] = _as_list(merged.get("countries_or_regions", ["United States"]))
    payload["risks"] = _as_list(merged.get("risks", []))
    payload["probability"] = scenario_probability
    payload["parser_confidence"] = merged.get("parser_confidence", {})
    payload["low_confidence_fields"] = _as_list(merged.get("low_confidence_fields", []))
    payload["parser_warnings"] = _as_list(merged.get("parser_warnings", []))
    payload["review_required"] = bool(merged.get("review_required", False))
    payload["field_excerpts"] = merged.get("field_excerpts", {})
    payload["stated_probabilities"] = merged.get("stated_probabilities", {})
    payload["phases"] = merged.get("phases", [])
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


def _scenario_specific_recommendations(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    recs = []
    recession = float(scenario.get("recession_probability", 0.3))
    volatility = scenario.get("market_volatility", "normal")
    financial = scenario.get("financial_conditions", "neutral")
    credit_stress = int(scenario.get("credit_stress", 3))
    fed = scenario.get("central_bank_stance", "neutral")
    dollar = scenario.get("dollar_outlook", "stable")
    commodity_shock = scenario.get("commodity_shock", "none")
    custom = _scenario_text(scenario)
    fiscal_supply_shock = _is_fiscal_supply_shock(scenario)

    if fiscal_supply_shock:
        recs.append(_presentation_rec("Defense and aerospace beneficiaries", "overweight", "equity", "highest_conviction", 0.61, 8.3, "Research hypothesis - requires human review: fiscal stimulus and defense spending could support defense and aerospace earnings even as higher real yields pressure broader multiples.", "Defense appropriations weaken, order books roll over, or real-yield pressure overwhelms earnings revisions.", "Defense/aerospace order momentum and fiscal spending confirmation."))
        recs.append(_presentation_rec("Infrastructure and industrial capex beneficiaries", "overweight", "equity", "highest_conviction", 0.6, 8.1, "Research hypothesis - requires human review: infrastructure spending, tariffs, and supply-chain reshoring can support industrials tied to capex, construction, and defense supply chains.", "Infrastructure funding disappoints, industrial PMIs contract, or tariffs destroy demand more than they support pricing.", "Infrastructure outlays, industrial new orders, and capex guidance."))
        recs.append(_presentation_rec("Energy and commodity producers", "overweight", "commodity_equity", "asymmetric", 0.59, 7.9, "Research hypothesis - requires human review: energy and broad commodity pressure can lift nominal cash flows for energy producers while also hedging sticky inflation.", "Energy supply normalizes, China stimulus disappoints, or demand destruction dominates price support.", "Oil inventory draws, energy prices, and commodity breadth."))
        recs.append(_presentation_rec("Industrial metals producers", "overweight", "commodity_equity", "asymmetric", 0.57, 7.6, "Research hypothesis - requires human review: targeted China stimulus and infrastructure demand can support industrial metals despite a stronger dollar headwind.", "China stimulus is too narrow, the dollar squeeze intensifies, or global manufacturing weakens.", "China credit impulse, copper/industrial metals breadth, and EM funding stress."))
        recs.append(_presentation_rec("Long US dollar", "long", "fx_rates", "defensive", 0.58, 7.5, "Research hypothesis - requires human review: Fed behind-the-curve repricing and higher U.S. real-yield risk can support a stronger USD, pressuring Europe, EM, and dollar-sensitive commodities.", "Fed rhetoric turns dovish or non-U.S. growth leadership improves enough to narrow rate differentials.", "DXY trend, real-yield differentials, and cross-currency funding stress."))
        recs.append(_presentation_rec("Two-stage gold hedge", "long", "commodity", "hedge", 0.54, 6.8, "Research hypothesis - requires human review: gold may be weak initially if real yields rise, then stabilize as geopolitical risk and policy-credibility concerns rise.", "Real yields rise without geopolitical stress or inflation credibility concern.", "Real yields, gold drawdowns, and geopolitical risk indicators."))
    if "long-duration technology" in custom or (scenario.get("equity_valuation") in {"expensive", "very expensive"} and fed in {"gradually tightening", "aggressively tightening"}):
        recs.append(_presentation_rec("Underweight long-duration technology", "underweight", "equity", "avoid", 0.6, 7.8, "Research hypothesis - requires human review: expensive long-duration technology is vulnerable if higher inflation forces real yields higher.", "Inflation rolls over, real yields fall, or AI/earnings revisions offset multiple compression.", "Real yields, Nasdaq duration factor performance, and earnings revision breadth."))
    if "reit" in custom or financial in {"tight", "severely tight"}:
        recs.append(_presentation_rec("Underweight REITs", "underweight", "real_assets", "avoid", 0.57, 7.4, "Research hypothesis - requires human review: REITs face pressure from higher real yields, tight financing conditions, and weaker Europe/property sensitivity.", "Long rates fall, credit conditions ease, or property fundamentals reaccelerate.", "REIT credit spreads, cap rates, and real-yield trend."))
    if recession >= 0.6 or financial == "severely tight" or credit_stress >= 7:
        recs.append(_presentation_rec("Short high-yield credit / own quality credit", "underweight", "credit", "defensive", 0.62, 8.2, "High recession probability, tight financial conditions, and credit stress argue for avoiding weak balance sheets.", "Credit spreads tighten and refinancing risk falls."))
        recs.append(_presentation_rec("Defensive cash / T-bills", "overweight", "fixed_income", "defensive", 0.6, 7.5, "Cash/T-bill optionality matters when stress and drawdown risk are elevated.", "Policy eases quickly and risk assets recover."))
    if volatility in {"high", "crisis"}:
        recs.append(_presentation_rec("Long equity volatility", "long", "volatility", "hedge", 0.58, 7.8, "High selected volatility raises the value of convex protection during stress windows.", "Volatility mean-reverts before portfolio stress materializes."))
    if fed == "aggressively tightening":
        recs.append(_presentation_rec("Long-duration nominal bonds", "underweight", "fixed_income", "avoid", 0.6, 7.7, "Aggressive tightening can pressure duration until growth damage dominates.", "Inflation collapses and the Fed pivots."))
    if fed in {"aggressively easing", "gradually easing"} and recession < 0.5:
        recs.append(_presentation_rec("Quality balance-sheet equities", "overweight", "equity", "highest_conviction", 0.57, 7.4, "Easing with contained recession risk can support quality risk assets.", "Earnings recession overwhelms easier policy."))
    if dollar in {"moderately stronger", "sharply stronger"}:
        recs.append(_presentation_rec("Long US dollar", "long", "fx_rates", "defensive", 0.59, 7.6, "Dollar strength can protect against global funding stress and pressure foreign-risk exposure.", "Fed repricing turns dovish or non-U.S. growth surprises higher."))
    if commodity_shock != "none":
        recs.append(_presentation_rec("Commodity shock basket", "long", "commodity", "asymmetric", 0.58, 7.8, f"{commodity_shock} raises inflation risk and supports real-asset hedges.", "Supply normalizes or demand destruction dominates."))
    return recs


def _case_probabilities(scenario: dict[str, Any]) -> dict[str, float]:
    bear = _clamp_probability(scenario.get("recession_probability", 0.3))
    selected_base = _optional_probability(scenario.get("probability"))
    if selected_base is None:
        selected_base = max(0.05, min(0.7, 1 - bear - 0.15))
    base = min(selected_base, max(0.05, 1 - bear))
    bull = max(0.0, 1 - base - bear)
    if bull < 0.05 and bear < 0.95:
        shortfall = 0.05 - bull
        base = max(0.05, base - shortfall)
        bull = max(0.0, 1 - base - bear)
    return {"base": round(base, 2), "bull": round(bull, 2), "bear_tail": round(bear, 2)}


def _presentation_rec(asset: str, direction: str, asset_class: str, category: str, probability: float, conviction: float, thesis: str, invalidation: str, catalyst: str | None = None) -> dict[str, Any]:
    return {
        "asset_or_trade": asset,
        "asset_class": asset_class,
        "direction": direction,
        "category": category,
        "investment_thesis": thesis,
        "expected_return_range": None,
        "probability_of_success": probability,
        "conviction": conviction,
        "major_risks": ["Timing error", "Scenario path changes", "Implementation basis risk"],
        "hedge": "Research hypothesis - requires human review.",
        "invalidation_condition": invalidation,
        "expected_time_horizon": "7-14 months",
        "catalyst": catalyst or "Scenario confirmation through inflation, rates, growth, and policy reaction data.",
    }


def _opportunity_row(row: dict[str, Any], scenario: dict[str, Any], rank: int) -> dict[str, Any]:
    proxy, benchmark = PROXY_MAP.get(row["asset_or_trade"], ("SPY", "SPY"))
    return {
        "rank": rank,
        "label": "Research hypothesis - requires human review.",
        "name": row["asset_or_trade"],
        "asset_class": row["asset_class"],
        "direction": row["direction"],
        "conviction_score": row["conviction"],
        "expected_horizon": row.get("expected_time_horizon", "7-14 months"),
        "proxy_ticker": proxy,
        "benchmark": benchmark,
        "probability_of_success": row.get("probability_of_success"),
        "conditions_for_entry": "Enter research queue when incoming data confirms the scenario direction and liquidity is adequate.",
        "conditions_for_exit": "Exit or resize if the invalidation condition is met or realized data contradicts the thesis.",
        "thesis": row["investment_thesis"],
        "why_now": _why_now(row, scenario),
        "catalyst": row.get("catalyst", "Scenario confirmation through inflation, rates, growth, and policy reaction data."),
        "upside_case": _upside_case(row, scenario),
        "downside_case": row["invalidation_condition"],
        "risks": row["major_risks"],
        "confirmation_indicators": _confirmation_for_asset(row["asset_or_trade"], scenario),
        "invalidation_condition": row["invalidation_condition"],
        "historical_analog_support": "Analog support is directional only; insufficient verified data to quantify this item.",
        "recommended_human_review_question": _human_review_question(row, scenario),
    }


def _hedge_row(row: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    proxy, _ = PROXY_MAP.get(row["asset_or_trade"], ("GLD", "SPY"))
    return {
        "label": "Research hypothesis - requires human review.",
        "hedge_name": row["asset_or_trade"],
        "hedge_category": _hedge_category(row, scenario),
        "risk_protected_against": _hedge_risk(row, scenario),
        "implementation_concept": f"Use proxy {proxy} as the measurable research instrument; size against approved portfolio risk.",
        "expected_cost_or_drag": "May lag in risk-on periods or when real yields move against the hedge.",
        "expected_payoff_condition": row["investment_thesis"],
        "timing_considerations": "Review after major inflation, FOMC, payroll, real-yield, and stress-window updates.",
        "convexity_or_asymmetry": "Potentially asymmetric if stress or policy credibility risk rises faster than carry cost.",
        "major_limitation": row["invalidation_condition"],
        "conditions_for_removing_hedge": "Remove or reduce if the hedged risk is invalidated, carry becomes excessive, or approved opportunity exposure is reduced.",
    }


def _hedge_risk(row: dict[str, Any], scenario: dict[str, Any]) -> str:
    if row.get("asset_or_trade") == "Long equity volatility":
        return "High volatility, equity drawdown, and stress-window risk."
    if scenario.get("credit_stress", 0) >= 7:
        return "Credit spread widening and refinancing stress."
    if scenario.get("commodity_shock") != "none":
        return "Commodity-led inflation shock and policy credibility risk."
    return "Policy mistake, growth shock, or inflation credibility risk."


def _hedge_category(row: dict[str, Any], scenario: dict[str, Any]) -> str:
    if row.get("asset_or_trade") == "Two-stage gold hedge":
        return "thesis-failure hedge"
    if row.get("asset_or_trade") == "Long equity volatility":
        return "portfolio-protection hedge"
    if scenario.get("commodity_shock") != "none":
        return "tail-risk hedge"
    return "opportunistic hedge"


def _scenario_text(scenario: dict[str, Any]) -> str:
    return " ".join(
        str(scenario.get(key, ""))
        for key in ["scenario_name", "scenario_description", "custom_assumptions", "source_text"]
    ).lower()


def _is_fiscal_supply_shock(scenario: dict[str, Any]) -> bool:
    text = _scenario_text(scenario)
    return (
        "fiscal" in text
        and any(term in text for term in ["tariff", "supply constraint", "infrastructure", "defense"])
        and scenario.get("commodity_shock") in {"broad commodity shock", "energy shock", "metals shock"}
    )


def _why_now(row: dict[str, Any], scenario: dict[str, Any]) -> str:
    if _is_fiscal_supply_shock(scenario):
        return "The selected scenario combines fiscal demand support, supply constraints, higher real-yield risk, and a delayed Fed response over the stated horizon."
    return "The recommendation belongs in the research queue because the selected scenario makes the catalyst measurable over the stated horizon."


def _upside_case(row: dict[str, Any], scenario: dict[str, Any]) -> str:
    if row["direction"] in {"underweight", "short", "avoid"}:
        return "Upside is downside avoided if the exposure underperforms or drawdown risk rises as expected."
    return "Upside depends on the scenario transmission mechanism showing up in earnings, rates, FX, spreads, or commodity leadership."


def _confirmation_for_asset(asset: str, scenario: dict[str, Any]) -> list[str]:
    asset_lower = asset.lower()
    indicators = ["Scenario-specific data confirms the selected macro path."]
    if "defense" in asset_lower:
        indicators.append("Defense order books and fiscal appropriations improve.")
    if "infrastructure" in asset_lower or "industrial" in asset_lower:
        indicators.append("Infrastructure outlays, industrial orders, and capex guidance firm.")
    if "energy" in asset_lower or "commodity" in asset_lower or "metals" in asset_lower:
        indicators.append("Energy and industrial metals prices rise with breadth.")
    if "dollar" in asset_lower:
        indicators.append("DXY and real-yield differentials confirm stronger USD pressure.")
    if "technology" in asset_lower or "reit" in asset_lower:
        indicators.append("Real yields rise and valuation-sensitive exposures lag.")
    return indicators


def _human_review_question(row: dict[str, Any], scenario: dict[str, Any]) -> str:
    return f"Does the committee agree that {row['asset_or_trade']} is measurable with the selected proxy and directly follows from the confirmed scenario assumptions?"


def _default_asset_catalyst(asset: str, scenario: dict[str, Any]) -> str:
    if asset in {"government bonds", "growth equities", "REITs"}:
        return "Real-yield and central-bank repricing."
    if asset in {"oil", "industrial metals", "broad commodities", "MLPs"}:
        return "Commodity supply-demand confirmation and inflation persistence."
    if asset in {"U.S. dollar", "major currencies", "international equities", "emerging-market equities"}:
        return "Rate differentials, dollar trend, and regional growth divergence."
    if asset in {"investment-grade credit", "high-yield credit"}:
        return "Credit-spread behavior and financing conditions."
    return "Incoming macro and market data confirm or reject the scenario transmission mechanism."


def _data_support_for_asset(asset: str, scenario: dict[str, Any]) -> str:
    if asset in {"government bonds", "inflation-linked bonds", "U.S. dollar", "gold"}:
        return "FRED rates, inflation, labor, and yield-curve data; market prices when available."
    if asset in {"oil", "industrial metals", "broad commodities", "MLPs"}:
        return "Yahoo Finance proxy prices and macro inflation data when available."
    if "credit" in asset:
        return "Credit proxy prices and financial-conditions indicators when available."
    return "Current data support is directional; insufficient verified data to quantify this item."


def _proxy_for_asset(asset: str) -> str:
    mapping = {
        "U.S. equities": "SPY",
        "international equities": "VEA",
        "emerging-market equities": "EEM",
        "growth equities": "QQQ",
        "value equities": "VLUE",
        "small caps": "IWM",
        "government bonds": "IEF/TLT",
        "inflation-linked bonds": "TIP",
        "investment-grade credit": "LQD",
        "high-yield credit": "HYG",
        "U.S. dollar": "UUP",
        "major currencies": "FX pairs",
        "gold": "GLD",
        "oil": "USO",
        "industrial metals": "XME",
        "broad commodities": "DBC",
        "REITs": "VNQ",
        "MLPs": "AMLP",
        "crypto": "BTC-USD/ETH-USD",
        "cash": "BIL",
        "volatility": "VIXY",
    }
    return mapping.get(asset, "Instrument requires human mapping.")


def _probability_detail(scenario: dict[str, Any]) -> dict[str, Any]:
    case_probs = _case_probabilities(scenario)
    stated = scenario.get("stated_probabilities") or {}
    user = {
        "scenario_probability": scenario.get("probability"),
        "recession_probability": scenario.get("recession_probability"),
        "stated_probabilities": stated,
    }
    numeric = [value for value in stated.values() if isinstance(value, (int, float))]
    total = sum(numeric) if numeric else None
    warnings = []
    if total is not None and abs(total - 1.0) > 0.01:
        warnings.append("User-provided probabilities do not sum to 100%; they are preserved and not silently normalized.")
    if scenario.get("probability") is None:
        warnings.append("Scenario probability unavailable because the user did not provide one.")
    return {
        "user_provided_probabilities": user,
        "model_derived_case_probabilities": case_probs,
        "normalized_probabilities": "Unavailable unless explicitly approved; user probabilities are preserved.",
        "warnings": warnings,
    }


def _macro_thesis(scenario: dict[str, Any], cross_asset: list[dict[str, Any]]) -> dict[str, Any]:
    chain = _transmission_chain(scenario)
    return {
        "7_14_month_base_case": f"{scenario['growth_outlook']} with inflation {scenario['inflation_direction']} and the Fed {scenario['fed_position']}.",
        "transmission_mechanism": " -> ".join(chain),
        "key_assumptions": _key_assumptions(scenario),
        "expected_sequence_of_events": chain,
        "central_bank_reaction_function": _central_bank_response(scenario),
        "country_and_regional_divergences": _regional_divergence_summary(scenario),
        "confidence_score": round(float(scenario.get("conviction", 7.0)), 1),
        "evidence_quality_score": _evidence_quality_score(scenario),
        "invalidation_conditions": scenario.get("invalidation_triggers") or ["Insufficient verified data to quantify this item."],
    }


def _transmission_chain(scenario: dict[str, Any]) -> list[str]:
    chain = []
    text = _scenario_text(scenario)
    if "fiscal" in text:
        chain.append("Fiscal stimulus supports nominal demand")
    else:
        chain.append(f"Growth remains {scenario['growth_outlook']}")
    if "tariff" in text or "supply constraint" in text:
        chain.append("Tariffs and supply constraints keep inflation risk elevated")
    elif scenario.get("commodity_shock") != "none":
        chain.append(f"{scenario['commodity_shock']} reinforces inflation pressure")
    else:
        chain.append(f"Inflation is {scenario['inflation_direction']}")
    chain.append(f"The Fed is {scenario['fed_position']} and policy is {scenario['central_bank_stance']}")
    if scenario.get("dollar_outlook") in {"moderately stronger", "sharply stronger"}:
        chain.append("Real-yield risk and dollar strength tighten global conditions")
    if scenario.get("commodity_shock") != "none":
        chain.append("Commodity-sensitive cash flows gain support while duration assets face pressure")
    chain.append("Human review decides which hypotheses are approved for tracking")
    return chain


def _key_assumptions(scenario: dict[str, Any]) -> list[str]:
    assumptions = [
        f"Growth: {scenario['growth_outlook']}",
        f"Inflation: {scenario['inflation_direction']} with {scenario.get('inflation_surprise_label', 'in line')} surprise risk",
        f"Fed: {scenario['central_bank_stance']} and {scenario['fed_position']}",
        f"Financial conditions: {scenario['financial_conditions']}; credit stress {scenario['credit_stress']}/10",
        f"USD: {scenario['dollar_outlook']}; commodity shock: {scenario['commodity_shock']}",
    ]
    custom = scenario.get("custom_assumptions")
    if custom:
        assumptions.append(f"User custom assumptions: {custom}")
    return assumptions


def _evidence_quality_score(scenario: dict[str, Any]) -> float:
    score = 5.5
    if scenario.get("custom_assumptions"):
        score += 0.8
    if scenario.get("stated_probabilities"):
        score += 0.5
    if scenario.get("field_excerpts"):
        score += 0.5
    return round(min(score, 8.0), 1)


def _regional_divergence_summary(scenario: dict[str, Any]) -> str:
    regions = {region.lower() for region in scenario.get("countries_or_regions", [])}
    pieces = []
    if "eurozone" in regions:
        pieces.append("Eurozone weaker if energy costs rise and USD strength tightens external conditions.")
    if "china" in regions:
        pieces.append("China improves at the margin if targeted stimulus supports industrial demand.")
    if "emerging markets" in regions:
        pieces.append("Emerging markets are split between commodity exporters and USD-funding pressure.")
    if not pieces:
        pieces.append("Regional divergence is limited to selected regions; insufficient verified data for broader country ranking.")
    return " ".join(pieces)


def _central_bank_analysis(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_stance": scenario["central_bank_stance"],
        "likely_reaction_function": f"React to inflation persistence, labor tightness, and financial conditions; current scenario has the Fed {scenario['fed_position']}.",
        "market_implied_path": "Insufficient verified data to quantify this item.",
        "behind_or_ahead_curve_risk": f"Fed position selected by user/model: {scenario['fed_position']}.",
        "expected_policy_transition": scenario["expected_policy_path"],
        "cross_country_policy_divergence": _regional_divergence_summary(scenario),
        "likely_asset_consequences": "Higher real-yield risk pressures duration-sensitive assets; policy credibility risk supports explicit hedges.",
    }


def _country_regional_views(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for region in scenario.get("countries_or_regions", ["U.S."]):
        lower = region.lower()
        if lower in {"eurozone", "europe"}:
            row = {
                "region": region,
                "growth_outlook": "weaker / energy-sensitive",
                "inflation_outlook": "vulnerable to energy pass-through",
                "central_bank_path": "more constrained by weak growth and imported inflation",
                "currency_implication": "weaker versus stronger USD",
                "equity_implication": "underweight energy-import-sensitive Europe until evidence improves",
                "bond_implication": "mixed; growth weakness helps bonds but inflation risk limits duration confidence",
                "commodity_sensitivity": "negative if energy costs rise",
                "major_risk": "Energy prices fall or European growth proves more resilient.",
            }
        elif lower == "china":
            row = {
                "region": region,
                "growth_outlook": "targeted stimulus support",
                "inflation_outlook": "less central unless commodity demand tightens supply",
                "central_bank_path": "policy support remains possible",
                "currency_implication": "stronger USD remains a headwind",
                "equity_implication": "selective support for commodity and infrastructure-linked beneficiaries",
                "bond_implication": "policy easing can support local duration selectively",
                "commodity_sensitivity": "positive for industrial metals if stimulus broadens",
                "major_risk": "Stimulus is too narrow to lift commodity demand.",
            }
        elif "emerging" in lower:
            row = {
                "region": region,
                "growth_outlook": "mixed",
                "inflation_outlook": "commodity exporters benefit; importers face pressure",
                "central_bank_path": "divergent by inflation and FX pressure",
                "currency_implication": "USD strength is a funding headwind",
                "equity_implication": "favor commodity exporters over externally financed cyclicals",
                "bond_implication": "local bonds vulnerable where FX and inflation pressure rise",
                "commodity_sensitivity": "high",
                "major_risk": "Dollar weakens or commodity shock fades.",
            }
        else:
            row = {
                "region": region,
                "growth_outlook": scenario["growth_outlook"],
                "inflation_outlook": scenario["inflation_direction"],
                "central_bank_path": scenario["central_bank_stance"],
                "currency_implication": scenario["dollar_outlook"],
                "equity_implication": "selective; favor exposures tied to confirmed scenario catalysts",
                "bond_implication": "duration faces real-yield and inflation-repricing risk",
                "commodity_sensitivity": scenario["commodity_shock"],
                "major_risk": "Scenario assumptions fail to appear in realized data.",
            }
        rows.append(row)
    return rows


def _underweights_to_avoid(scenario: dict[str, Any], recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    avoid_recs = [row for row in recommendations if row.get("category") == "avoid"]
    for row in avoid_recs:
        rows.append(
            {
                "asset_or_exposure": row["asset_or_trade"],
                "reason_to_avoid": row["investment_thesis"],
                "expected_failure_mechanism": row["invalidation_condition"] if row["direction"] in {"overweight", "long"} else "Higher real yields, tighter financing, or weaker earnings revisions pressure the exposure.",
                "conditions_that_would_make_view_wrong": row["invalidation_condition"],
                "tactical_or_strategic": "tactical",
            }
        )
    if _is_fiscal_supply_shock(scenario):
        names = {row["asset_or_exposure"] for row in rows}
        if "Underweight long-duration technology" not in names:
            rows.append({"asset_or_exposure": "Long-duration technology", "reason_to_avoid": "Expensive equity valuation plus higher real-yield risk creates multiple-compression vulnerability.", "expected_failure_mechanism": "Real yields rise and duration-like equity cash flows de-rate.", "conditions_that_would_make_view_wrong": "Inflation rolls over or earnings revisions overwhelm rate pressure.", "tactical_or_strategic": "tactical"})
        if "Underweight REITs" not in names:
            rows.append({"asset_or_exposure": "REITs", "reason_to_avoid": "Tight financial conditions and higher real yields pressure cap rates and funding costs.", "expected_failure_mechanism": "Cap rates rise and credit availability tightens.", "conditions_that_would_make_view_wrong": "Long rates fall and property fundamentals improve.", "tactical_or_strategic": "tactical"})
    return rows or [{"asset_or_exposure": "No explicit avoid identified", "reason_to_avoid": "Not enough information to populate this section.", "expected_failure_mechanism": "Insufficient verified data to quantify this item.", "conditions_that_would_make_view_wrong": "Not applicable.", "tactical_or_strategic": "not applicable"}]


def _structured_confirming_indicators(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in _confirming_indicators(scenario):
        rows.append({
            "indicator": item,
            "current_status": "Insufficient verified data to quantify this item.",
            "threshold_or_direction": _indicator_threshold(item),
            "why_it_matters": "Confirms whether the scenario assumptions are becoming observable in macro or market data.",
            "affected_recommendation": _affected_recommendation(item),
        })
    return rows


def _structured_invalidating_indicators(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    triggers = scenario.get("invalidation_triggers") or ["Scenario assumptions fail to appear in realized data."]
    return [
        {
            "indicator": item,
            "current_status": "Insufficient verified data to quantify this item.",
            "threshold_or_direction": _indicator_threshold(item),
            "why_it_matters": "Would require weakening, revising, or invalidating the thesis before it enters training data.",
            "affected_recommendation": _affected_recommendation(item),
        }
        for item in triggers
    ]


def _indicator_threshold(item: str) -> str:
    lower = item.lower()
    if "inflation" in lower or "cpi" in lower or "pce" in lower:
        return "Watch direction across multiple releases; exact threshold requires committee approval."
    if "dollar" in lower or "dxy" in lower:
        return "Trend must confirm selected USD direction."
    if "credit" in lower or "spread" in lower:
        return "Spread direction must confirm or reject stress assumption."
    if "real yield" in lower or "treasury" in lower:
        return "Real-yield trend must match rate-repricing thesis."
    return "Direction must be consistent with confirmed scenario assumptions."


def _affected_recommendation(item: str) -> str:
    lower = item.lower()
    if "commodity" in lower or "energy" in lower or "metals" in lower:
        return "Energy, industrial metals, commodities, inflation hedges."
    if "dollar" in lower or "dxy" in lower:
        return "USD, international equities, emerging markets, commodities."
    if "credit" in lower:
        return "Credit, equities, REITs, cash optionality."
    if "fed" in lower or "real yield" in lower or "treasury" in lower:
        return "Duration, growth equities, REITs, gold, USD."
    return "Macro thesis and ranked opportunities."


def _risk_register(scenario: dict[str, Any], hedges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hedge_name = hedges[0]["hedge_name"] if hedges else "Explicit hedge review required."
    base = [
        ("Thesis risk", "medium", "high", "Inflation, growth, or Fed path differs from confirmed assumptions.", "All ranked opportunities", "CPI/PCE, payrolls, FOMC language", hedge_name, "partly"),
        ("Implementation risk", "medium", "medium", "Proxy instrument does not match intended exposure.", "Proxy-tracked opportunities", "Proxy basis versus intended exposure", "Manual proxy review", "not fully"),
        ("Liquidity risk", "low to medium", "medium", "Volatility rises and liquidity deteriorates during execution windows.", "Small caps, credit, hedges", "Bid/ask spreads and volume", "Cash/T-bill optionality", "mixed"),
        ("Policy risk", "medium", "high", _policy_risk_mechanism(scenario), "Duration, growth equities, credit", "FOMC reaction function and real yields", hedge_name, "partly"),
        ("Model/data-quality risk", "medium", "medium", "Unavailable or stale data weakens evidence quality.", "All sections", "Source-status monitor", "Human review and data-refresh gate", "not fully"),
    ]
    if _is_fiscal_supply_shock(scenario):
        base.append(("Geopolitical / tariff risk", "medium", "high", "Tariffs and supply constraints keep inflation elevated while regional winners diverge.", "Europe, commodities, industrials, USD", "Tariff announcements, energy prices, shipping/supply indicators", "Commodity and volatility hedges", "mixed"))
    return [
        {
            "risk": risk,
            "probability": probability,
            "impact": impact,
            "transmission_mechanism": mechanism,
            "affected_assets": assets,
            "early_warning_indicator": indicator,
            "hedge_or_response": response,
            "already_priced": priced,
        }
        for risk, probability, impact, mechanism, assets, indicator, response, priced in base
    ]


def _policy_risk_mechanism(scenario: dict[str, Any]) -> str:
    if scenario.get("fed_position") == "behind the curve":
        return "Fed overtightening risk rises if delayed tightening later becomes aggressive."
    if scenario.get("central_bank_stance") in {"gradually easing", "aggressively easing"}:
        return "Fed easing may arrive too slowly if growth deterioration accelerates or inflation reappears."
    if scenario.get("fed_position") == "ahead of the curve":
        return "Fed may stay too restrictive relative to growth and inflation conditions."
    return "Policy reaction function differs from the selected scenario path."


def _traceability_map(scenario: dict[str, Any], data_snapshot: dict[str, Any], analogs: dict[str, Any], opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_status = data_snapshot.get("source_status", {}) if isinstance(data_snapshot, dict) else {}
    live_sources = [source for source, status in source_status.items() if "ok" in str(status).lower() or "live" in str(status).lower()]
    analog = "Insufficient verified analog data to quantify this item."
    ranked = analogs.get("ranked_historical_analogs", []) if isinstance(analogs, dict) else []
    if ranked:
        analog = ranked[0].get("period", analog)
    rows = [
        {
            "conclusion": "Macro thesis",
            "supporting_scenario_assumption": "; ".join(_key_assumptions(scenario)[:4]),
            "supporting_data_source": ", ".join(live_sources) if live_sources else "Insufficient verified data to quantify this item.",
            "supporting_historical_analog": analog,
            "supporting_agent_conclusion": "Scenario Lab, historical analog, recommendation, and hedge logic agree directionally.",
            "confidence_level": f"{_evidence_quality_score(scenario)}/10 evidence quality",
        }
    ]
    for opportunity in opportunities[:5]:
        rows.append(
            {
                "conclusion": opportunity["name"],
                "supporting_scenario_assumption": opportunity["thesis"],
                "supporting_data_source": opportunity.get("confirmation_indicators", ["Insufficient verified data to quantify this item."])[0],
                "supporting_historical_analog": opportunity.get("historical_analog_support", analog),
                "supporting_agent_conclusion": opportunity["label"],
                "confidence_level": f"{opportunity['conviction_score']}/10 conviction",
            }
        )
    return rows


def _prior_report_comparison(scenario: dict[str, Any]) -> dict[str, Any]:
    reports = list_investment_committee_reports(limit=5)
    previous = next((row for row in reports if row.get("report", {}).get("scenario_definition", {}).get("name") != scenario.get("scenario_name")), None)
    if not previous:
        return {
            "thesis_changes": "No prior comparable report exists.",
            "probability_changes": "No prior comparable report exists.",
            "ranking_changes": "No prior comparable report exists.",
            "new_opportunities": "Current run creates the initial opportunity set for this scenario.",
            "removed_opportunities": "No prior comparable report exists.",
            "hedge_changes": "Current run creates the initial hedge menu for this scenario.",
            "changed_risks": "No prior comparable report exists.",
            "changed_invalidation_conditions": "No prior comparable report exists.",
            "data_that_caused_change": "No prior comparable report exists.",
        }
    prior_report = previous.get("report", {})
    return {
        "thesis_changes": "Current scenario uses a distinct confirmed scenario definition versus the most recent report.",
        "probability_changes": "Probability changes require comparable prior scenario probabilities; otherwise preserved as user/model labels.",
        "ranking_changes": "Ranking changes are scenario-specific and should be reviewed in the report selector.",
        "new_opportunities": "See ranked opportunities table.",
        "removed_opportunities": "Insufficient verified data to quantify this item.",
        "hedge_changes": "See hedge menu and risk register.",
        "changed_risks": "Risk register reflects current scenario assumptions.",
        "changed_invalidation_conditions": "Invalidation conditions are derived from current assumptions.",
        "data_that_caused_change": "Scenario assumptions and available source-status data.",
    }


def _investment_committee_decisions(scenario: dict[str, Any], opportunities: list[dict[str, Any]], underweights: list[dict[str, Any]], hedges: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "decisions_requested": "Approve, reject, or request revisions to each research hypothesis; no trade execution is authorized.",
        "opportunities_to_approve": [item["name"] for item in opportunities[:5]],
        "opportunities_to_reject": "None automatically rejected; committee should reject any item without a measurable proxy or causal link.",
        "items_requiring_more_research": [item["asset_or_exposure"] for item in underweights[:4]],
        "data_releases_to_wait_for": _data_to_watch(scenario)[:5],
        "recommended_review_date": "Next major CPI/PCE, payroll, FOMC, or credit-spread update.",
        "thesis_status": "maintain pending human review",
    }


def _case_markdown(outlook: dict[str, Any]) -> str:
    return "\n".join(
        [
            "### Base Case",
            _bullet_dict(outlook["base_case"]),
            "",
            "### Bull Case",
            _bullet_dict(outlook["bull_case"]),
            "",
            "### Bear / Tail Case",
            _bullet_dict(outlook["bear_tail_case"]),
        ]
    )


def _probability_markdown(probabilities: dict[str, Any]) -> str:
    lines = ["### User-Provided Probabilities", _bullet_dict(probabilities.get("user_provided_probabilities", {})), "", "### Model-Derived Probabilities", _bullet_dict(probabilities.get("model_derived_case_probabilities", {})), "", "### Normalized Probabilities", str(probabilities.get("normalized_probabilities", ""))]
    warnings = probabilities.get("warnings", [])
    if warnings:
        lines.extend(["", "### Probability Warnings", _bullets(warnings)])
    return "\n".join(lines)


def _fallback_hedge(scenario: dict[str, Any]) -> dict[str, Any]:
    if scenario.get("market_volatility") in {"high", "crisis"}:
        return {
            "label": "Research hypothesis - requires human review.",
            "hedge_name": "Long equity volatility",
            "hedge_category": "portfolio-protection hedge",
            "risk_protected_against": "High volatility, equity drawdown, and credit-spread shock.",
            "implementation_concept": "Use VIXY as a liquid proxy for measurement; human review required.",
            "expected_cost_or_drag": "High carry drag if volatility mean-reverts or markets rally.",
            "expected_payoff_condition": "Pays if stress windows deepen or volatility remains elevated.",
            "timing_considerations": "Review around FOMC, inflation, payroll, and credit-spread updates.",
            "convexity_or_asymmetry": "Convex if volatility rises faster than carry cost.",
            "major_limitation": "Timing and roll costs can overwhelm payoff if stress arrives late.",
            "conditions_for_removing_hedge": "Remove if volatility normalizes and thesis-risk exposure is reduced.",
        }
    return {
        "label": "Research hypothesis - requires human review.",
        "hedge_name": "Gold / policy credibility hedge",
        "hedge_category": "thesis-failure hedge",
        "risk_protected_against": "Sticky inflation and delayed central-bank response.",
        "implementation_concept": "Use GLD as a proxy for measurement; human review required.",
        "expected_cost_or_drag": "Can drag if real yields rise sharply.",
        "expected_payoff_condition": "Pays if inflation credibility or policy confidence deteriorates.",
        "timing_considerations": "Review after real-yield, inflation, and geopolitical-risk updates.",
        "convexity_or_asymmetry": "Asymmetric if policy credibility worsens after initial real-yield pressure.",
        "major_limitation": "Fails if inflation falls quickly and real yields rise.",
        "conditions_for_removing_hedge": "Remove if inflation and policy credibility risks are invalidated.",
    }


def _cross_asset_outlook(scenario: dict[str, Any], recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assets = [
        "U.S. equities",
        "international equities",
        "emerging-market equities",
        "growth equities",
        "value equities",
        "small caps",
        "government bonds",
        "inflation-linked bonds",
        "investment-grade credit",
        "high-yield credit",
        "U.S. dollar",
        "major currencies",
        "gold",
        "oil",
        "industrial metals",
        "broad commodities",
        "REITs",
        "MLPs",
        "crypto",
        "cash",
        "volatility",
    ]
    rows = []
    for asset in assets:
        rec = _matching_rec(asset, recommendations)
        if rec:
            direction = rec["direction"]
            conviction = rec["conviction"]
            rationale = rec["investment_thesis"]
            risk = rec["invalidation_condition"]
            catalyst = rec.get("catalyst", "Scenario confirmation through data.")
        else:
            direction, conviction, rationale, risk = _default_asset_view(asset, scenario)
            catalyst = _default_asset_catalyst(asset, scenario)
        rows.append(
            {
                "asset_class": asset,
                "expected_direction": direction,
                "conviction": conviction,
                "time_horizon": scenario["scenario_duration"],
                "expected_return_range": "Insufficient verified data to quantify this item.",
                "rationale": rationale,
                "key_catalyst": catalyst,
                "main_risk": risk,
                "invalidation_condition": risk,
                "historical_analog_support": "Directional analog only; not a deterministic forecast.",
                "data_support": _data_support_for_asset(asset, scenario),
                "proxy_ticker": _proxy_for_asset(asset),
            }
        )
    return rows


def _matching_rec(asset: str, recommendations: list[dict[str, Any]]) -> dict[str, Any] | None:
    text = asset.lower()
    for rec in recommendations:
        haystack = f"{rec.get('asset_or_trade', '')} {rec.get('asset_class', '')}".lower()
        if (
            text.split()[0] in haystack
            or ("gold" in text and "gold" in haystack)
            or ("oil" in text and "energy" in haystack)
            or ("industrial metals" in text and "metals" in haystack)
            or ("reit" in text and "reit" in haystack)
            or ("growth equities" in text and "technology" in haystack)
            or ("u.s. dollar" in text and "dollar" in haystack)
        ):
            return rec
    return None


def _default_asset_view(asset: str, scenario: dict[str, Any]) -> tuple[str, float, str, str]:
    recession = float(scenario.get("recession_probability", 0.3))
    volatility = scenario.get("market_volatility", "normal")
    financial = scenario.get("financial_conditions", "neutral")
    credit_stress = int(scenario.get("credit_stress", 3))
    dollar = scenario.get("dollar_outlook", "stable")
    commodity_shock = scenario.get("commodity_shock", "none")
    valuation = scenario.get("equity_valuation", "fair")
    if asset in {"U.S. equities", "international equities", "emerging-market equities"} and (recession >= 0.6 or volatility in {"high", "crisis"} or financial in {"tight", "severely tight"}):
        return "cautious / underweight candidate", 7.0, f"Recession probability at {recession:.0%}, {volatility} volatility, and {financial} financial conditions argue for lower equity beta.", "Growth reaccelerates or policy eases quickly."
    if asset in {"U.S. equities", "value equities"} and valuation in {"very cheap", "cheap"} and recession < 0.35:
        return "positive / overweight candidate", 6.7, "Valuation support and contained recession risk can improve equity asymmetry.", "Earnings revisions deteriorate."
    if asset in {"investment-grade credit", "high-yield credit"} and (credit_stress >= 6 or financial in {"tight", "severely tight"}):
        return "underweight / avoid weakest credit", 7.5, f"Credit stress at {credit_stress}/10 and {financial} financial conditions raise refinancing and spread risk.", "Spreads stabilize and default risk falls."
    if asset in {"U.S. dollar", "major currencies"} and dollar in {"moderately stronger", "sharply stronger"}:
        return "favor USD strength", 7.0, "Dollar strength pressures non-U.S. assets, commodities, and EM funding conditions.", "Fed turns dovish or global growth leadership broadens."
    if asset in {"U.S. dollar", "major currencies"} and dollar in {"moderately weaker", "sharply weaker"}:
        return "favor non-USD exposure", 6.7, "A weaker dollar can support international equities, EM assets, and commodity liquidity.", "U.S. real rates rise or funding stress returns."
    if asset in {"broad commodities", "oil", "industrial metals", "MLPs"} and commodity_shock != "none":
        return "positive / overweight candidate", 7.4, f"{commodity_shock} can lift inflation risk and support real-asset cash flows.", "Supply normalizes or demand weakens."
    if asset == "gold" and (volatility in {"high", "crisis"} or commodity_shock != "none" or dollar in {"sharply weaker", "moderately weaker"}):
        return "two-stage hedge candidate", 7.0, "Gold may lag while real yields rise, then stabilize if geopolitical or policy-credibility risk builds.", "Real yields rise sharply without a risk premium."
    if asset == "cash" and (volatility in {"high", "crisis"} or credit_stress >= 7):
        return "overweight optionality", 7.0, "Cash protects optionality when volatility or credit stress is high.", "Risk-on liquidity returns quickly."
    if scenario["inflation_direction"] in {"rising", "elevated"} and asset in {"broad commodities", "gold", "oil", "industrial metals", "MLPs"}:
        return "positive / overweight candidate", 6.8, "Inflation surprise can support real assets and nominal cash-flow beneficiaries.", "Inflation rolls over or real rates rise sharply."
    if scenario["central_bank_policy_stance"] == "delayed_tightening" and asset == "cash":
        return "neutral", 5.5, "Cash optionality improves if policy repricing becomes disorderly.", "Risk assets continue higher without volatility."
    if asset in {"government bonds", "growth equities", "crypto", "inflation-linked bonds"}:
        return "cautious / underweight candidate", 6.2, "Delayed tightening with inflation surprise can pressure duration-sensitive assets.", "Growth shock forces dovish repricing."
    if asset == "volatility" and volatility in {"high", "crisis"}:
        return "long / hedge candidate", 7.2, "High selected volatility raises the value of convex portfolio protection.", "Volatility normalizes before portfolio drawdown risk appears."
    return "mixed / selective", 5.8, "Scenario creates dispersion; require instrument-level confirmation.", "Scenario fails to translate into asset-price leadership."


def _choice(values: dict[str, Any], primary: str, legacy: str | None = None, default: str = "") -> str:
    value = values.get(primary)
    if value is None and legacy:
        value = values.get(legacy)
    return str(value or default)


def _clamp_probability(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.5
    if number > 1:
        number = number / 100
    return max(0.0, min(1.0, number))


def _optional_probability(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return _clamp_probability(value)


def _case_probabilities_for_unspecified(values: dict[str, Any]) -> float:
    bear = _clamp_probability(values.get("recession_probability", 0.3))
    return max(0.05, min(0.7, 1 - bear - 0.15))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        pieces = []
        for line in value.replace(";", "\n").replace(",", "\n").splitlines():
            item = line.strip()
            if item:
                pieces.append(item)
        return pieces
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value)]


def scenario_hash_for_payload(payload: dict[str, Any]) -> str:
    excluded = {
        "scenario_hash",
        "confirmed_scenario_id",
        "confirmed_scenario_hash",
        "parser_warnings",
        "review_required",
        "parse_duration_ms",
    }
    canonical = {key: value for key, value in payload.items() if key not in excluded}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _validated_parsed_scenario(payload: dict[str, Any], source_text: str, provider: str, model: str | None, duration_ms: int | None) -> ParsedScenario:
    cleaned = _clean_llm_payload(payload, source_text)
    cleaned["scenario_id"] = cleaned.get("scenario_id") or f"scenario_{uuid.uuid4().hex[:12]}"
    cleaned["source_text"] = source_text
    cleaned["parser_provider"] = provider
    cleaned["parser_model"] = model
    cleaned["parse_duration_ms"] = duration_ms
    if not cleaned.get("field_confidence") and isinstance(cleaned.get("parser_confidence"), dict):
        cleaned["field_confidence"] = cleaned["parser_confidence"]
    else:
        cleaned["field_confidence"] = cleaned.get("field_confidence", {})
    if isinstance(cleaned.get("parser_confidence"), dict):
        values = list(cleaned["parser_confidence"].values())
        cleaned["parser_confidence"] = sum(values) / len(values) if values else 0.5
    cleaned["parser_confidence"] = float(cleaned.get("parser_confidence") or 0.65)
    cleaned["low_confidence_fields"] = [
        field for field, score in (cleaned.get("field_confidence") or {}).items() if isinstance(score, (int, float)) and score < 0.55
    ]
    cleaned["contradiction_warnings"] = list(dict.fromkeys((cleaned.get("contradiction_warnings") or []) + _contradiction_warnings(source_text.lower(), cleaned)))
    cleaned["scenario_hash"] = scenario_hash_for_payload(cleaned)
    return ParsedScenario(**cleaned)


def _clean_llm_payload(payload: dict[str, Any], source_text: str) -> dict[str, Any]:
    cleaned = {key: value for key, value in payload.items()}
    if "countries_or_regions" in cleaned and "countries" not in cleaned:
        cleaned["countries"] = cleaned["countries_or_regions"]
    if "supporting_text_by_field" in cleaned and "field_excerpts" not in cleaned:
        cleaned["field_excerpts"] = cleaned["supporting_text_by_field"]
    cleaned.setdefault("countries", ["U.S."])
    cleaned.setdefault("custom_regions", [])
    cleaned.setdefault("risks", [])
    cleaned.setdefault("invalidation_triggers", [])
    cleaned.setdefault("confirming_indicators", [])
    cleaned.setdefault("stated_probabilities", {})
    cleaned.setdefault("field_excerpts", {})
    cleaned.setdefault("supporting_text_by_field", cleaned.get("field_excerpts", {}))
    cleaned.setdefault("phases", [])
    cleaned.setdefault("scenario_name", _title_from_text(source_text))
    cleaned.setdefault("scenario_description", source_text.strip())
    return cleaned


def _extract_all_probabilities(text: str) -> dict[str, float]:
    results: dict[str, float] = {}
    for match in re.finditer(r"([a-zA-Z][a-zA-Z /_-]{1,50}?)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%", text):
        label = _probability_label(match.group(1))
        if label:
            results[label] = float(match.group(2)) / 100
    recession = _extract_percentage_near(text, ["recession", "falls into recession", "recession if"])
    if recession is not None and not results:
        results["recession"] = recession
    return results


def _probability_label(value: str) -> str:
    label = value.strip(" .,:;-").lower().replace(" ", "_").replace("/", "_").replace("-", "_")
    stop_words = {"assume_there_is_a", "there_is_a", "probability_that_the_economy_eventually_falls_into_recession_if_the_fed_has_to_tighten_policy_aggressively_later"}
    if not label or label in stop_words or len(label) > 40:
        return ""
    return label


def _rule_field_excerpts(text: str, scenario: dict[str, Any]) -> dict[str, str]:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
    fields = {
        "growth_outlook": ["grow", "growth", "economy"],
        "inflation_direction": ["inflation", "energy", "wage"],
        "central_bank_stance": ["federal reserve", "fed", "interest rates"],
        "market_volatility": ["volatile", "volatility", "calm"],
        "credit_stress": ["credit spreads"],
        "dollar_outlook": ["dollar"],
        "commodity_shock": ["energy", "commodity", "oil"],
        "labor_market": ["unemployment", "wage"],
    }
    excerpts = {}
    for field, terms in fields.items():
        excerpts[field] = next((sentence for sentence in sentences if any(term in sentence.lower() for term in terms)), "")
    return excerpts


def _rule_phases(text: str) -> list[dict[str, Any]]:
    if any(term in text for term in ["calm at first", "initially", "later", "then become more volatile", "volatility rises later"]):
        return [
            {"name": "Initial phase", "market_volatility": "normal", "supporting_excerpt": "Markets remain calm at first."},
            {"name": "Later phase", "market_volatility": "high", "supporting_excerpt": "Volatility rises later as policy concern builds."},
        ]
    return []


def _inflation_up(text: str) -> bool:
    return any(
        term in text
        for term in [
            "inflation begins to rise",
            "inflation rises",
            "inflation rise",
            "inflation surprises higher",
            "inflation surprise higher",
            "inflation will be higher",
            "sticky inflation",
            "energy prices increase",
            "energy prices and wages increase",
            "energy prices rise",
            "commodity prices continue to increase",
        ]
    )


def _behind_curve(text: str) -> bool:
    return any(
        term in text
        for term in [
            "delays raising interest rates",
            "delays tightening",
            "fed delays",
            "temporary and delays",
            "falling behind the curve",
            "behind the curve",
            "too accommodative",
            "too slow",
        ]
    )


def _extract_percentage_near(text: str, anchors: list[str]) -> float | None:
    matches = [(match.start(), float(match.group(1)) / 100) for match in re.finditer(r"(\d+(?:\.\d+)?)\s*%", text)]
    if not matches:
        return None
    for position, value in matches:
        window = text[max(0, position - 80): position + 120]
        if any(anchor in window for anchor in anchors):
            return value
    return None


def _parsed_risks(scenario: dict[str, Any]) -> list[str]:
    risks = [
        "Fed delay allows inflation expectations and Treasury yields to rise further.",
        "Higher rates eventually undermine equity multiples and credit risk appetite.",
    ]
    if float(scenario.get("recession_probability", 0)) > 0:
        risks.append("Later aggressive tightening could push the economy into recession.")
    if scenario.get("commodity_shock") != "none":
        risks.append("Energy or commodity pressure keeps inflation sticky for longer than expected.")
    return risks


def _parsed_invalidation_triggers(scenario: dict[str, Any]) -> list[str]:
    triggers = [
        "Energy prices reverse lower and inflation pressure fades.",
        "Wage growth cools materially while unemployment begins to rise.",
        "Fed communication turns preemptively hawkish before markets price a behind-the-curve risk.",
    ]
    if scenario.get("dollar_outlook") in {"moderately stronger", "sharply stronger"}:
        triggers.append("The U.S. dollar weakens despite higher yields.")
    return triggers


def _contradiction_warnings(text: str, scenario: dict[str, Any]) -> list[str]:
    warnings = []
    if _inflation_up(text) and scenario.get("inflation_direction") in {"disinflation", "deflation"}:
        warnings.append("Review required: extracted assumptions may conflict with the scenario.")
    if "unemployment remains low" in text and scenario.get("labor_market") in {"weak", "recessionary"}:
        warnings.append("Review required: extracted assumptions may conflict with the scenario.")
    if "credit spreads stay" in text and scenario.get("financial_conditions") == "severely tight":
        warnings.append("Review required: extracted assumptions may conflict with the scenario.")
    if _behind_curve(text) and scenario.get("central_bank_stance") == "aggressively tightening":
        warnings.append("Review required: extracted assumptions may conflict with the scenario.")
    return list(dict.fromkeys(warnings))


def _internal_growth(value: str) -> str:
    mapping = {
        "strong acceleration": "strong",
        "moderate growth": "strong",
        "slowing growth": "slowing",
        "stagnation": "slowing",
        "recession": "contracting",
        "strong": "strong",
        "mixed": "mixed",
        "slowing": "slowing",
        "contracting": "contracting",
    }
    return mapping.get(value, "mixed")


def _internal_inflation(value: str) -> str:
    mapping = {
        "sharply higher": "rising",
        "moderately higher": "rising",
        "stable": "stable",
        "disinflation": "falling",
        "deflation": "falling",
        "rising": "rising",
        "elevated": "elevated",
        "falling": "falling",
        "mixed": "mixed",
    }
    return mapping.get(value, "mixed")


def _internal_inflation_surprise(value: str) -> str:
    mapping = {
        "large downside surprise": "lower",
        "small downside surprise": "lower",
        "in line": "none",
        "small upside surprise": "higher",
        "large upside surprise": "higher",
        "higher": "higher",
        "lower": "lower",
        "modest": "modest",
        "none": "none",
    }
    return mapping.get(value, "modest")


def _internal_central_bank_stance(value: str, fed_position: str) -> str:
    mapping = {
        "aggressively easing": "easing",
        "gradually easing": "easing",
        "neutral": "restrictive" if fed_position == "ahead of the curve" else "delayed_tightening" if fed_position == "behind the curve" else "restrictive",
        "gradually tightening": "delayed_tightening" if fed_position == "behind the curve" else "tightening",
        "aggressively tightening": "aggressive_tightening",
        "delayed_tightening": "delayed_tightening",
        "tightening": "tightening",
        "aggressive_tightening": "aggressive_tightening",
        "restrictive": "restrictive",
        "easing": "easing",
    }
    return mapping.get(value, "restrictive")


def _internal_fed_position(value: str) -> str:
    mapping = {
        "ahead of the curve": "ahead",
        "roughly on time": "neutral",
        "behind the curve": "behind",
        "ahead": "ahead",
        "neutral": "neutral",
        "behind": "behind",
    }
    return mapping.get(value, "neutral")


def _internal_labor(value: str) -> str:
    mapping = {
        "overheating": "tight",
        "strong": "tight",
        "cooling": "mixed",
        "weak": "weakening",
        "recessionary": "weakening",
        "tight": "tight",
        "firm": "firm",
        "mixed": "mixed",
        "weakening": "weakening",
    }
    return mapping.get(value, "mixed")


def _internal_financial_conditions(value: str) -> str:
    mapping = {
        "very loose": "easy",
        "loose": "easy",
        "neutral": "mixed",
        "tight": "tightening",
        "severely tight": "tight",
        "easy": "easy",
        "tightening": "tightening",
        "mixed": "mixed",
        "tight": "tight",
    }
    return mapping.get(value, "mixed")


def _title_from_text(text: str) -> str:
    clean = " ".join(text.strip().split())
    if not clean:
        return "Custom Macro Scenario"
    return clean[:70].rstrip(".") if len(clean) <= 70 else clean[:67].rstrip() + "..."


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
                "supports_or_contradicts": "Supports the thesis directionally only; historical analogs are not deterministic forecasts.",
            }
        )
    return rows


def _executive_outlook(scenario: dict[str, Any], opportunities: list[dict[str, Any]], hedges: list[dict[str, Any]]) -> str:
    lead = opportunities[0]["name"] if opportunities else "selective cross-asset opportunities"
    hedge = hedges[0]["hedge_name"] if hedges else "explicit downside hedges"
    return (
        f"The scenario describes a {scenario['scenario_duration']} window where growth is {scenario['growth_outlook']} "
        f"while inflation is {scenario['inflation_direction']} and policy is {scenario['central_bank_stance']}. "
        f"Recession risk is {float(scenario['recession_probability']):.0%}, volatility is {scenario['market_volatility']}, credit stress is {scenario['credit_stress']}/10, and the dollar outlook is {scenario['dollar_outlook']}. "
        f"The central macro implication is that nominal growth may stay firm before central banks fully react, which can favor real-asset and inflation-sensitive research hypotheses. "
        f"The main investment implication is to prioritize {lead} while avoiding unhedged exposure to assets most vulnerable to higher real-rate repricing. "
        f"Central-bank risk is asymmetric because a delayed response can eventually require faster tightening. "
        f"The recommended posture is opportunity-led but risk-controlled, with {hedge} reviewed as a hedge rather than a standalone forecast. "
        f"Every recommendation remains conditional and requires human approval."
    )


def _growth_path(scenario: dict[str, Any]) -> str:
    return f"Growth expected to follow a {scenario['growth_outlook']} path; labor market is {scenario['labor_market']} and recession risk is {float(scenario['recession_probability']):.0%}."


def _inflation_path(scenario: dict[str, Any]) -> str:
    shock = scenario.get("commodity_shock", "none")
    shock_text = "" if shock == "none" else f" Commodity shock assumption: {shock}."
    return f"Inflation expected to be {scenario['inflation_direction']} with surprise risk skewed {scenario['inflation_surprise_label']}.{shock_text}"


def _central_bank_response(scenario: dict[str, Any]) -> str:
    return f"Central banks likely remain {scenario['central_bank_stance']} with the Fed {scenario['fed_position']}; expected path: {scenario['expected_policy_path']}."


def _market_consequence(cross_asset: list[dict[str, Any]]) -> str:
    positives = [row["asset_class"] for row in cross_asset if "positive" in row["expected_direction"] or "overweight" in row["expected_direction"]]
    cautious = [row["asset_class"] for row in cross_asset if "underweight" in row["expected_direction"] or "cautious" in row["expected_direction"]]
    return f"Likely support for {', '.join(positives[:4]) or 'selective risk assets'}; caution on {', '.join(cautious[:4]) or 'crowded duration exposure'}."


def _confirming_indicators(scenario: dict[str, Any]) -> list[str]:
    indicators = [
        "Core CPI/PCE and inflation expectations continue to surprise higher.",
        "Payrolls, wages, and real activity data remain resilient.",
        "Fed communication stays patient relative to incoming inflation data.",
        "Commodity and breakeven signals confirm sticky nominal pressure.",
    ]
    if scenario.get("credit_stress", 0) >= 6:
        indicators.append("Credit spreads and lending standards confirm rising financing stress.")
    if scenario.get("dollar_outlook") in {"moderately stronger", "sharply stronger"}:
        indicators.append("DXY and cross-currency funding indicators confirm dollar pressure.")
    if scenario.get("market_volatility") in {"high", "crisis"}:
        indicators.append("VIX and equity drawdown signals confirm stress-window behavior.")
    return indicators


def _data_to_watch(scenario: dict[str, Any]) -> list[str]:
    items = [
        "CPI and core PCE inflation releases",
        "Payrolls, unemployment rate, and wage growth",
        "FOMC statement, dot plot, and press conference language",
        "10-year Treasury yield, real yields, and breakeven inflation",
        "Oil, gold, and broad commodity indexes",
        "Credit spreads and financial conditions indexes",
    ]
    if scenario.get("dollar_outlook") != "stable":
        items.append("DXY, USD funding spreads, and major FX pairs")
    if scenario.get("commodity_shock") != "none":
        items.append(f"Supply indicators linked to {scenario['commodity_shock']}")
    return items


def _debate_summary(scenario: dict[str, Any], opportunities: list[dict[str, Any]], hedges: list[dict[str, Any]]) -> str:
    strongest = opportunities[0]["name"] if opportunities else "no single opportunity"
    weakest = "timing risk: the scenario can be directionally right but early."
    hidden = f"selected stress inputs may dominate: recession {float(scenario['recession_probability']):.0%}, volatility {scenario['market_volatility']}, credit stress {scenario['credit_stress']}/10."
    hedge = hedges[0]["hedge_name"] if hedges else "no hedge identified"
    return (
        f"Consensus view: the scenario is internally consistent and most supportive of {strongest}. "
        f"Main disagreement: how quickly central banks respond if inflation remains firm. "
        f"Weakest reasoning: {weakest} Hidden risk: {hidden} Highest-conviction hedge to review: {hedge}."
    )


def _table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "Not enough information to populate this section."
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(_compact(row.get(column, "")) for column in columns) + " |")
    return "\n".join([header, divider, *body])


def _bullet_dict(values: dict[str, Any]) -> str:
    return "\n".join(f"- {key.replace('_', ' ').title()}: {_compact(value)}" for key, value in values.items())


def _bullets(values: list[Any]) -> str:
    return "\n".join(f"- {_compact(value)}" for value in values) if values else "Not enough information to populate this section."


def _compact(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(_compact(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {_compact(item)}" for key, item in value.items())
    return str(value).replace("\n", " ").replace("|", "/")
