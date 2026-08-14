from __future__ import annotations

from copy import deepcopy
from typing import Any


GROWTH_OPTIONS = ["accelerating growth", "moderate growth", "slowing growth", "stagnation", "recession"]
SURPRISE_OPTIONS = ["large downside surprise", "small downside surprise", "in line", "small upside surprise", "large upside surprise"]
INFLATION_OPTIONS = ["accelerating inflation", "stable inflation", "decelerating inflation", "deflation"]
EXPECTED_FED_RESPONSE_OPTIONS = ["aggressively tighten", "tighten", "hold", "loosen", "aggressively loosen"]
MARKET_SENTIMENT_OPTIONS = ["extremely bullish", "bullish", "neutral", "bearish", "extremely bearish"]
MARGIN_DEBT_OPTIONS = ["extremely high", "high", "moderate", "low", "very low"]
COMMODITY_SHOCK_OPTIONS = ["none", "energy shock", "food shock", "metals shock", "broad commodity shock"]
TIME_HORIZON_OPTIONS = ["1-3 months", "3-6 months", "6-9 months", "9-12 months", "12+ months"]
REGION_OPTIONS = ["U.S.", "Eurozone", "U.K.", "Japan", "China", "India", "Emerging Markets", "Global", "Custom"]

ALIASES = {
    "growth_outlook": {
        "strong acceleration": "accelerating growth",
        "strong": "accelerating growth",
        "contracting": "recession",
    },
    "inflation_direction": {
        "sharply higher": "accelerating inflation",
        "moderately higher": "accelerating inflation",
        "rising": "accelerating inflation",
        "elevated": "stable inflation",
        "stable": "stable inflation",
        "disinflation": "decelerating inflation",
        "falling": "decelerating inflation",
    },
    "growth_surprise": {"higher": "small upside surprise", "lower": "small downside surprise"},
    "inflation_surprise": {"higher": "small upside surprise", "lower": "small downside surprise", "modest": "in line"},
    "time_horizon": {
        "6-12 months": "6-9 months",
        "7-14 months": "9-12 months",
        "12-24 months": "12+ months",
    },
    "countries_or_regions": {"emerging markets": "Emerging Markets", "global": "Global", "United States": "U.S."},
}


def normalize_scenario_contract(scenario: dict[str, Any]) -> dict[str, Any]:
    """Migrate legacy scenario labels while retaining unknown narrative fields."""
    normalized = deepcopy(scenario)
    for field, aliases in ALIASES.items():
        value = normalized.get(field)
        if field == "countries_or_regions":
            normalized[field] = [aliases.get(str(item), str(item)) for item in (value or ["U.S."])]
        elif value is not None:
            normalized[field] = aliases.get(str(value), str(value))
    normalized.setdefault("growth_outlook", "moderate growth")
    normalized.setdefault("growth_surprise", "in line")
    normalized.setdefault("inflation_direction", "stable inflation")
    normalized.setdefault("inflation_surprise", "in line")
    normalized.setdefault("expected_fed_response", "hold")
    normalized.setdefault("market_sentiment", "neutral")
    normalized.setdefault("margin_debt", "moderate")
    normalized.setdefault("commodity_shock", "none")
    normalized.setdefault("time_horizon", "3-6 months")
    normalized.setdefault("countries_or_regions", ["U.S."])
    return normalized
