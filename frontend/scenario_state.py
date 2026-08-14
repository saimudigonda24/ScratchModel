from __future__ import annotations

from copy import deepcopy
from typing import Any, MutableMapping


REQUIRED_SCENARIO_OPTION_FIELDS = (
    "growth_outlook",
    "growth_surprise",
    "inflation_direction",
    "inflation_surprise",
    "market_volatility",
    "central_bank_stance",
    "fed_position",
    "expected_fed_response",
    "labor_market",
    "financial_conditions",
    "dollar_outlook",
    "commodity_shock",
    "equity_valuation",
    "market_sentiment",
    "margin_debt",
    "time_horizon",
    "countries_or_regions",
)

SCENARIO_OPTIONS_FALLBACK = {
    "growth_outlook": ["accelerating growth", "moderate growth", "slowing growth", "stagnation", "recession"],
    "growth_surprise": ["large downside surprise", "small downside surprise", "in line", "small upside surprise", "large upside surprise"],
    "inflation_direction": ["accelerating inflation", "stable inflation", "decelerating inflation", "deflation"],
    "inflation_surprise": [
        "large downside surprise",
        "small downside surprise",
        "in line",
        "small upside surprise",
        "large upside surprise",
    ],
    "market_volatility": ["very low", "low", "normal", "high", "crisis"],
    "central_bank_stance": [
        "aggressively easing",
        "gradually easing",
        "neutral",
        "gradually tightening",
        "aggressively tightening",
    ],
    "fed_position": ["ahead of the curve", "roughly on time", "behind the curve"],
    "expected_fed_response": ["aggressively tighten", "tighten", "hold", "loosen", "aggressively loosen"],
    "labor_market": ["overheating", "strong", "cooling", "weak", "recessionary"],
    "financial_conditions": ["very loose", "loose", "neutral", "tight", "severely tight"],
    "dollar_outlook": ["sharply weaker", "moderately weaker", "stable", "moderately stronger", "sharply stronger"],
    "commodity_shock": ["none", "energy shock", "food shock", "metals shock", "broad commodity shock"],
    "equity_valuation": ["very cheap", "cheap", "fair", "expensive", "very expensive"],
    "market_sentiment": ["extremely bullish", "bullish", "neutral", "bearish", "extremely bearish"],
    "margin_debt": ["extremely high", "high", "moderate", "low", "very low"],
    "time_horizon": ["1-3 months", "3-6 months", "6-9 months", "9-12 months", "12+ months"],
    "countries_or_regions": ["U.S.", "Eurozone", "U.K.", "Japan", "China", "India", "Emerging Markets", "Global", "Custom"],
    "presets": {},
}


def normalize_scenario_options(
    api_response: Any,
    previous_options: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return complete widget options while retaining the raw API response for diagnostics."""
    raw = api_response if isinstance(api_response, dict) else {}
    previous = previous_options if isinstance(previous_options, dict) else {}
    normalized = deepcopy(SCENARIO_OPTIONS_FALLBACK)
    fallback_fields: list[str] = []

    for field in REQUIRED_SCENARIO_OPTION_FIELDS:
        candidate = raw.get(field)
        if not isinstance(candidate, list) or not candidate:
            candidate = previous.get(field)
        if isinstance(candidate, list) and candidate:
            normalized[field] = list(candidate)
        else:
            fallback_fields.append(field)

    presets = raw.get("presets")
    if not isinstance(presets, dict) or not presets:
        presets = previous.get("presets")
    normalized["presets"] = deepcopy(presets) if isinstance(presets, dict) else {}

    api_missing_fields = [
        field for field in REQUIRED_SCENARIO_OPTION_FIELDS if not isinstance(raw.get(field), list) or not raw.get(field)
    ]
    choice_counts = {field: len(normalized[field]) for field in REQUIRED_SCENARIO_OPTION_FIELDS}
    return normalized, {
        "api_response": deepcopy(api_response),
        "choice_counts": choice_counts,
        "missing_fields": [field for field, count in choice_counts.items() if count == 0],
        "api_missing_fields": api_missing_fields,
        "fallback_fields": fallback_fields,
    }


def apply_successful_parse(
    state: MutableMapping[str, Any],
    response: Any,
    *,
    status: str = "Parsed scenario loaded into controls.",
) -> tuple[bool, str | None]:
    """Atomically move a successful backend parse into the canonical UI state."""
    state["latest_parsed_response"] = deepcopy(response)
    if not isinstance(response, dict):
        return False, "Parser response was not a JSON object."
    if response.get("status") != "ok":
        return False, str(response.get("warning") or response.get("reason") or "Parser did not return status ok.")
    scenario = response.get("scenario")
    if not isinstance(scenario, dict) or not scenario:
        return False, "Parser response did not include a scenario object."

    current = deepcopy(scenario)
    current["widgets_refreshed"] = True
    next_version = int(state.get("scenario_widget_version", 0)) + 1
    state["current_scenario"] = current
    state["scenario_builder"] = current
    state["scenario_parse_status"] = status
    state["scenario_assumptions_confirmed"] = False
    state["scenario_parse_pending"] = True
    state["scenario_outlook"] = {}
    state["active_preset"] = None
    state["scenario_widget_version"] = next_version
    state["scenario_parse_timing"] = deepcopy(current.get("parse_timing") or {})
    state["latest_current_scenario_after_assignment"] = deepcopy(current)
    state["latest_widget_version_after_assignment"] = next_version
    return True, None
