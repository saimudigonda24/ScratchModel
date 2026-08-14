from __future__ import annotations

from math import sqrt
from statistics import mean, median, pstdev
from typing import Any
import hashlib

from app.services.database import save_scenario_recommendation


INSUFFICIENT_DATA = "Insufficient verified data to quantify this item."
HORIZONS = (1, 3, 6, 9, 12)

# Proxies are for paper measurement only. Recommendations always use subsegment names.
ASSET_UNIVERSE = [
    ("Equities - Size", "Large Cap", "SPY"), ("Equities - Size", "Mid Cap", "MDY"),
    ("Equities - Size", "Small Cap", "IWM"), ("Equities - Style", "Growth", "VUG"),
    ("Equities - Style", "Value", "VTV"), ("Equities - Style", "Quality", "QUAL"),
    ("Equities - Style", "Momentum", "MTUM"), ("Equities - Style", "Low Volatility", "USMV"),
    ("Equities - Style", "Dividend", "VIG"), ("Equities - Sector", "Technology", "XLK"),
    ("Equities - Sector", "Communication Services", "XLC"),
    ("Equities - Sector", "Consumer Discretionary", "XLY"),
    ("Equities - Sector", "Consumer Staples", "XLP"), ("Equities - Sector", "Energy", "XLE"),
    ("Equities - Sector", "Materials", "XLB"), ("Equities - Sector", "Industrials", "XLI"),
    ("Equities - Sector", "Financials", "XLF"), ("Equities - Sector", "Healthcare", "XLV"),
    ("Equities - Sector", "Utilities", "XLU"), ("Equities - Sector", "Real Estate", "XLRE"),
    ("Equities - Theme", "Semiconductors", "SOXX"), ("Equities - Theme", "Regional Banks", "KRE"),
    ("Equities - Theme", "Defense / Aerospace", "ITA"), ("Equities - Theme", "Infrastructure", "PAVE"),
    ("Treasuries", "Cash / T-bills", "BIL"), ("Treasuries", "2-Year / Short End", "SHY"),
    ("Treasuries", "5-Year / Belly", "IEI"), ("Treasuries", "10-Year / Belly", "IEF"),
    ("Treasuries", "30-Year / Long End", "TLT"), ("Credit", "Investment Grade Corporate", "LQD"),
    ("Credit", "High Yield Corporate", "HYG"), ("Credit", "Floating Rate", "FLOT"),
    ("Credit", "Bank Loans", "BKLN"), ("Credit", "Agency / MBS", "MBB"), ("Credit", "TIPS", "TIP"),
    ("FX", "U.S. Dollar", "UUP"), ("FX", "Euro", "FXE"), ("FX", "Japanese Yen", "FXY"),
    ("Real Assets", "Gold", "GLD"), ("Real Assets", "Oil", "USO"),
    ("Real Assets", "Industrial Metals", "DBB"), ("Real Assets", "Agriculture", "DBA"),
    ("Real Assets", "Broad Commodities", "DBC"), ("Real Assets", "REITs", "VNQ"),
    ("Real Assets", "MLPs", "AMLP"), ("Alternatives", "Crypto", "BTC-USD"),
    ("Alternatives", "Cash", "BIL"), ("Alternatives", "Volatility", "VIXY"),
]

OUTLOOK_LABELS = {
    2: "Strong Outperform", 1: "Outperform", 0: "Neutral",
    -1: "Underperform", -2: "Strong Underperform",
}
DIRECTION_LABELS = {
    2: "Strong Long / Overweight", 1: "Long / Overweight", 0: "Neutral",
    -1: "Short / Underweight", -2: "Strong Short / Underweight",
}


def normalized_analog_weights(analogs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores = [max(0.0, float(row.get("similarity_score", 0))) for row in analogs]
    total = sum(scores)
    return [
        {**row, "analog_weight": round(score / total, 4) if total else 0.0,
         "weight_label": "normalized similarity weight (not probability)"}
        for row, score in zip(analogs, scores)
    ]


def historical_forward_performance(
    analogs: list[dict[str, Any]],
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Aggregate only caller-supplied verified observations; never synthesize returns."""
    observations = observations or []
    weights = {row["period"]: row["analog_weight"] for row in normalized_analog_weights(analogs)}
    rows: list[dict[str, Any]] = []
    for asset_class, subsegment, _ in ASSET_UNIVERSE:
        for horizon in HORIZONS:
            values = [
                float(row["return"])
                for row in observations
                if row.get("verified") is True
                and row.get("subsegment") == subsegment
                and int(row.get("horizon_months", 0)) == horizon
            ]
            matching = [
                row for row in observations
                if row.get("verified") is True and row.get("subsegment") == subsegment
                and int(row.get("horizon_months", 0)) == horizon
            ]
            if not values:
                rows.append({
                    "asset_class": asset_class, "subsegment": subsegment,
                    "horizon_months": horizon, "status": INSUFFICIENT_DATA,
                    "average_return": None, "median_return": None, "positive_hit_rate": None,
                    "dispersion": None, "volatility": None, "maximum_drawdown": None,
                    "analog_weighted_return": None,
                })
                continue
            weighted_total = sum(weights.get(str(row.get("period")), 0) for row in matching)
            weighted = (
                sum(float(row["return"]) * weights.get(str(row.get("period")), 0) for row in matching) / weighted_total
                if weighted_total else None
            )
            drawdowns = [float(row["maximum_drawdown"]) for row in matching if row.get("maximum_drawdown") is not None]
            rows.append({
                "asset_class": asset_class, "subsegment": subsegment, "horizon_months": horizon,
                "status": "verified historical observations",
                "average_return": mean(values), "median_return": median(values),
                "positive_hit_rate": sum(value > 0 for value in values) / len(values),
                "dispersion": max(values) - min(values), "volatility": pstdev(values) if len(values) > 1 else None,
                "maximum_drawdown": min(drawdowns) if drawdowns else None,
                "analog_weighted_return": weighted,
            })
    return {"methodology": "Only observations explicitly marked verified are quantified.", "rows": rows}


def build_cross_asset_outlook(
    scenario: dict[str, Any],
    analogs: list[dict[str, Any]],
    current_support: list[str] | None = None,
) -> list[dict[str, Any]]:
    weighted = normalized_analog_weights(analogs)
    analog_support = round(sum(row["analog_weight"] * float(row.get("similarity_score", 0)) for row in weighted), 3)
    periods = [row.get("period") for row in weighted[:3]]
    rows = []
    for asset_class, subsegment, proxy in ASSET_UNIVERSE:
        score, drivers, risks = _score_subsegment(subsegment, scenario)
        score = max(-2, min(2, score))
        rows.append({
            "asset_class": asset_class,
            "subsegment": subsegment,
            "outlook": OUTLOOK_LABELS[score],
            "score": score,
            "conviction": round(min(9.0, 5.0 + abs(score) + analog_support), 1),
            "historical_analog_support": {
                "periods": periods,
                "normalized_similarity_support": analog_support,
                "note": "Similarity evidence is directional and is not a return forecast.",
            },
            "current_data_support": current_support or ["Current-source confirmation requires manager review."],
            "primary_macro_driver": "; ".join(drivers),
            "major_risk": "; ".join(risks),
            "relevant_horizon": scenario.get("time_horizon", scenario.get("scenario_duration", "3-6 months")),
            "tracking_proxy": proxy,
            "expected_return": INSUFFICIENT_DATA,
        })
    return sorted(rows, key=lambda row: (-row["score"], -row["conviction"], row["subsegment"]))


def build_suggested_portfolio(outlook: list[dict[str, Any]]) -> dict[str, Any]:
    positions = []
    for row in outlook:
        if row["score"] == 0:
            continue
        support = row["historical_analog_support"]
        positions.append({
            "asset_class": row["asset_class"], "subsegment": row["subsegment"],
            "direction": DIRECTION_LABELS[row["score"]], "conviction": row["conviction"],
            "expected_holding_horizon": row["relevant_horizon"],
            "historical_analog_support": support, "current_data_support": row["current_data_support"],
            "why_now": row["primary_macro_driver"],
            "main_catalyst": f"Incoming data confirms: {row['primary_macro_driver']}",
            "main_risk": row["major_risk"],
            "confirmation_condition": f"{row['primary_macro_driver']} remains directionally intact.",
            "invalidation_condition": row["major_risk"],
            "portfolio_role": _portfolio_role(row),
            "hedge_relationship": _hedge_relationship(row),
            "tracking_benchmark_proxy": row["tracking_proxy"],
            "recommendation_is_security": False,
            "research_status": "Research recommendation for human IC review; not an executed trade.",
        })
    strongest = sorted(positions, key=lambda row: (-row["conviction"], row["subsegment"]))[:18]
    return {
        "weighting_assumption": "No capital weights implied; conviction ranks research priority.",
        "long_overweight": [row for row in strongest if "Long" in row["direction"]],
        "short_underweight": [row for row in strongest if "Short" in row["direction"]],
        "hedges": [row for row in strongest if row["portfolio_role"] == "hedge"],
        "all_positions": strongest,
    }


def freeze_suggested_portfolio(
    phase: dict[str, Any],
    portfolio: dict[str, Any],
    analogs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Persist an immutable paper-research snapshot for later horizon evaluation."""
    frozen = []
    for position in portfolio.get("all_positions", []):
        key = f"{phase['phase_id']}:{position['subsegment']}:{position['direction']}"
        recommendation_id = "portfolio_rec_" + hashlib.sha256(key.encode()).hexdigest()[:16]
        recommendation = {
            **position,
            "run_id": phase["phase_id"], "theme_id": phase["sequence_id"],
            "phase_id": phase["phase_id"], "scenario_id": phase["scenario"].get("scenario_id"),
            "recommendation_date": phase["created_at"], "entry_reference_price": None,
            "target_evaluation_horizons_months": [1, 3, 6, 9, 12],
            "primary_evaluation_horizon_months": 3,
        }
        frozen.append(save_scenario_recommendation({
            "recommendation_id": recommendation_id,
            "phase_id": phase["phase_id"], "sequence_id": phase["sequence_id"],
            "recommendation": recommendation,
            "frozen_snapshot": {
                "scenario_assumptions": phase["scenario"],
                "historical_analogs_used": analogs,
                "weighting_assumption": portfolio["weighting_assumption"],
                "paper_research_only": True,
            },
            "created_at": phase["created_at"],
        }))
    return frozen


def unexpected_opportunities(outlook: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = {"Defense / Aerospace", "Infrastructure", "MLPs", "5-Year / Belly", "Industrial Metals"}
    results = []
    for row in outlook:
        support = row["historical_analog_support"]["normalized_similarity_support"]
        if row["subsegment"] not in candidates or row["score"] <= 0 or support < 0.45:
            continue
        results.append({
            "asset_class": row["asset_class"], "subsegment": row["subsegment"],
            "why_not_obvious": "The exposure is a second-order beneficiary rather than the headline macro trade.",
            "why_model_surfaced_it": row["primary_macro_driver"],
            "historical_support": row["historical_analog_support"],
            "current_support": row["current_data_support"],
            "what_would_make_it_wrong": row["major_risk"],
            "human_review_required": True,
        })
    return results


def build_portfolio_evolution(phases: list[dict[str, Any]]) -> dict[str, Any]:
    if not 1 <= len(phases) <= 4:
        raise ValueError("A theme must contain between one and four phases")
    outputs = []
    previous: dict[str, dict[str, Any]] = {}
    changes = []
    for index, phase in enumerate(phases, start=1):
        scenario = phase["scenario"]
        analogs = phase.get("historical_analogs", [])
        outlook = build_cross_asset_outlook(scenario, analogs, phase.get("current_data_support"))
        portfolio = build_suggested_portfolio(outlook)
        current = {row["subsegment"]: row for row in portfolio["all_positions"]}
        if previous:
            changes.append(_phase_changes(index - 1, index, previous, current))
        outputs.append({
            "phase_number": index, "phase_id": phase.get("phase_id", f"phase-{index}"),
            "phase_name": phase.get("phase_name", f"Phase {index}"),
            "window": phase.get("window", f"Months {(index - 1) * 3}-{index * 3}"),
            "scenario": scenario, "historical_analogs": normalized_analog_weights(analogs),
            "expected_asset_class_performance": outlook, "suggested_portfolio": portfolio,
            "risks": scenario.get("risks", []), "invalidation_conditions": scenario.get("invalidation_triggers", []),
        })
        previous = current
    return {"phases": outputs, "portfolio_changes": changes}


def evaluate_portfolio(
    positions: list[dict[str, Any]],
    realized_returns: dict[str, float],
    benchmark_return: float = 0.0,
    weighting: str = "equal",
) -> dict[str, Any]:
    evaluated = [row for row in positions if row["subsegment"] in realized_returns]
    if not evaluated:
        return {"status": INSUFFICIENT_DATA}
    raw_weights = [float(row["conviction"]) if weighting == "conviction" else 1.0 for row in evaluated]
    total = sum(raw_weights)
    weights = [value / total for value in raw_weights]
    signed = []
    hits = []
    for row, weight in zip(evaluated, weights):
        realized = float(realized_returns[row["subsegment"]])
        is_short = "Short" in row["direction"]
        contribution_return = -realized if is_short else realized
        signed.append((row, contribution_return, weight))
        hits.append(contribution_return > 0)
    portfolio_return = sum(value * weight for _, value, weight in signed)
    longs = [value for row, value, _ in signed if "Long" in row["direction"]]
    shorts = [value for row, value, _ in signed if "Short" in row["direction"]]
    return {
        "status": "paper evaluation; no execution implied", "weighting_assumption": weighting,
        "long_book_return": mean(longs) if longs else None,
        "short_book_return": mean(shorts) if shorts else None,
        "long_short_spread": (mean(longs) - mean(shorts)) if longs and shorts else None,
        "portfolio_return": portfolio_return,
        "benchmark_relative_return": portfolio_return - benchmark_return,
        "volatility": pstdev([value for _, value, _ in signed]) if len(signed) > 1 else None,
        "maximum_drawdown": None,
        "hit_rate": sum(hits) / len(hits),
        "conviction_weighted_accuracy": sum(weight for hit, weight in zip(hits, weights) if hit),
    }


def _score_subsegment(subsegment: str, scenario: dict[str, Any]) -> tuple[int, list[str], list[str]]:
    score = 0
    drivers: list[str] = []
    risks: list[str] = []
    growth = scenario.get("growth_outlook", scenario.get("growth_direction", "moderate growth"))
    growth_surprise = scenario.get("growth_surprise", "in line")
    inflation = scenario.get("inflation_direction", "stable inflation")
    inflation_surprise = scenario.get("inflation_surprise", "in line")
    fed = scenario.get("expected_fed_response", "hold")
    recession = float(scenario.get("recession_probability", 0.3))
    sentiment = scenario.get("market_sentiment", "neutral")
    margin = scenario.get("margin_debt", "moderate")
    shock = scenario.get("commodity_shock", "none")
    duration = {"Growth", "Technology", "Utilities", "Real Estate", "30-Year / Long End", "REITs"}
    cyclicals = {"Small Cap", "Mid Cap", "Value", "Consumer Discretionary", "Energy", "Materials", "Industrials", "Financials", "Regional Banks", "Infrastructure", "MLPs", "Industrial Metals"}
    defensives = {"Quality", "Low Volatility", "Dividend", "Consumer Staples", "Healthcare", "Cash / T-bills", "Cash", "Gold"}
    real_assets = {"Energy", "Materials", "Gold", "Oil", "Industrial Metals", "Broad Commodities", "MLPs", "TIPS", "Agriculture"}
    credit_risk = {"High Yield Corporate", "Bank Loans", "Regional Banks", "Small Cap"}
    if growth in {"accelerating growth", "moderate growth"} or "upside surprise" in growth_surprise:
        if subsegment in cyclicals: score += 1
        drivers.append("resilient or positively surprising growth")
    if growth in {"slowing growth", "stagnation", "recession"} or recession >= 0.6:
        if subsegment in cyclicals or subsegment in credit_risk: score -= 1
        if subsegment in defensives or subsegment in {"10-Year / Belly", "30-Year / Long End"}: score += 1
        drivers.append("growth deterioration and recession risk")
    if inflation == "accelerating inflation" or "upside surprise" in inflation_surprise or shock != "none":
        if subsegment in real_assets: score += 1
        if subsegment in duration: score -= 1
        drivers.append("inflation pressure or commodity shock")
    if inflation in {"decelerating inflation", "deflation"}:
        if subsegment in {"5-Year / Belly", "10-Year / Belly", "30-Year / Long End", "Growth"}: score += 1
        if subsegment in real_assets - {"Gold"}: score -= 1
        drivers.append("disinflation or deflation")
    if fed in {"tighten", "aggressively tighten"}:
        if subsegment in duration or subsegment in credit_risk: score -= 1
        if subsegment in {"Cash / T-bills", "Cash", "U.S. Dollar", "Floating Rate"}: score += 1
        drivers.append("expected Fed tightening")
    if fed in {"loosen", "aggressively loosen"}:
        if subsegment in {"5-Year / Belly", "10-Year / Belly", "30-Year / Long End", "Quality"}: score += 1
        drivers.append("expected Fed easing")
    if sentiment in {"extremely bullish", "bullish"} and margin in {"extremely high", "high"}:
        if subsegment in {"Growth", "Technology", "Crypto", "Small Cap"}: score -= 1
        if subsegment in {"Low Volatility", "Cash", "Gold"}: score += 1
        drivers.append("crowded sentiment and elevated leverage")
    if not drivers: drivers.append("mixed macro signals")
    risks.append("scenario path or timing differs from assumptions")
    return score, drivers, risks


def _portfolio_role(row: dict[str, Any]) -> str:
    if row["subsegment"] in {"Gold", "Volatility", "Cash", "Cash / T-bills"}:
        return "hedge"
    return "return-seeking exposure" if row["score"] > 0 else "risk reduction / relative underweight"


def _hedge_relationship(row: dict[str, Any]) -> str:
    if row["score"] < 0:
        return "Reduces exposure to the scenario's vulnerable segment."
    if _portfolio_role(row) == "hedge":
        return "Offsets growth, inflation, or volatility tail risk."
    return "Diversify against other recommended exposures; review correlations."


def _phase_changes(
    from_phase: int, to_phase: int,
    previous: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    transitions = []
    conviction = []
    for name in sorted(set(previous) & set(current)):
        before, after = previous[name], current[name]
        if before["direction"] != after["direction"]:
            transitions.append({
                "subsegment": name, "from": before["direction"], "to": after["direction"],
                "change_type": "long-to-short" if "Long" in before["direction"] and "Short" in after["direction"] else "short-to-long" if "Short" in before["direction"] and "Long" in after["direction"] else "direction change",
                "reason": after["why_now"],
            })
        if before["conviction"] != after["conviction"]:
            conviction.append({"subsegment": name, "from": before["conviction"], "to": after["conviction"]})
    return {
        "from_phase": from_phase, "to_phase": to_phase,
        "positions_added": added, "positions_removed": removed,
        "direction_changes": transitions, "conviction_changes": conviction,
    }
