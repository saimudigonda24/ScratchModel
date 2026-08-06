from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


GrowthOutlook = Literal["strong acceleration", "moderate growth", "slowing growth", "stagnation", "recession"]
InflationDirection = Literal["sharply higher", "moderately higher", "stable", "disinflation", "deflation"]
InflationSurprise = Literal["large downside surprise", "small downside surprise", "in line", "small upside surprise", "large upside surprise"]
MarketVolatility = Literal["very low", "low", "normal", "high", "crisis"]
CentralBankStance = Literal["aggressively easing", "gradually easing", "neutral", "gradually tightening", "aggressively tightening"]
FedPosition = Literal["ahead of the curve", "roughly on time", "behind the curve"]
LaborMarket = Literal["overheating", "strong", "cooling", "weak", "recessionary"]
FinancialConditions = Literal["very loose", "loose", "neutral", "tight", "severely tight"]
DollarOutlook = Literal["sharply weaker", "moderately weaker", "stable", "moderately stronger", "sharply stronger"]
CommodityShock = Literal["none", "energy shock", "food shock", "metals shock", "broad commodity shock"]
EquityValuation = Literal["very cheap", "cheap", "fair", "expensive", "very expensive"]
TimeHorizon = Literal["1-3 months", "3-6 months", "6-12 months", "7-14 months", "12-24 months"]


class ScenarioPhase(BaseModel):
    name: str
    growth_outlook: GrowthOutlook | None = None
    inflation_direction: InflationDirection | None = None
    central_bank_stance: CentralBankStance | None = None
    market_volatility: MarketVolatility | None = None
    financial_conditions: FinancialConditions | None = None
    dollar_outlook: DollarOutlook | None = None
    commodity_shock: CommodityShock | None = None
    supporting_excerpt: str | None = None


class ParsedScenario(BaseModel):
    scenario_id: str
    scenario_hash: str
    scenario_name: str
    scenario_description: str
    growth_outlook: GrowthOutlook | None = None
    inflation_direction: InflationDirection | None = None
    inflation_surprise: InflationSurprise | None = None
    central_bank_stance: CentralBankStance | None = None
    expected_policy_path: str | None = None
    fed_position: FedPosition | None = None
    labor_market: LaborMarket | None = None
    financial_conditions: FinancialConditions | None = None
    market_volatility: MarketVolatility | None = None
    credit_stress: int | None = Field(default=None, ge=0, le=10)
    dollar_outlook: DollarOutlook | None = None
    commodity_shock: CommodityShock | None = None
    equity_valuation: EquityValuation | None = None
    time_horizon: TimeHorizon | None = None
    countries: list[str] = Field(default_factory=list)
    custom_regions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    invalidation_triggers: list[str] = Field(default_factory=list)
    confirming_indicators: list[str] = Field(default_factory=list)
    stated_probabilities: dict[str, float] = Field(default_factory=dict)
    probability_total_warning: str | None = None
    source_text: str
    parser_provider: Literal["ollama", "rule_fallback", "manual"]
    parser_model: str | None = None
    parser_confidence: float = Field(ge=0, le=1)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    field_excerpts: dict[str, str] = Field(default_factory=dict)
    supporting_text_by_field: dict[str, str] = Field(default_factory=dict)
    contradiction_warnings: list[str] = Field(default_factory=list)
    low_confidence_fields: list[str] = Field(default_factory=list)
    phases: list[ScenarioPhase] = Field(default_factory=list)
    parse_duration_ms: int | None = None
    parse_timing: dict[str, int] = Field(default_factory=dict)

    @field_validator("stated_probabilities")
    @classmethod
    def validate_probability_values(cls, value: dict[str, float]) -> dict[str, float]:
        for label, probability in value.items():
            if probability < 0 or probability > 1:
                raise ValueError(f"probability {label!r} must be between 0 and 1")
        return value

    @model_validator(mode="after")
    def add_probability_warning(self):
        if len(self.stated_probabilities) > 1:
            total = sum(self.stated_probabilities.values())
            if abs(total - 1.0) > 0.03:
                self.probability_total_warning = f"Stated probabilities sum to {total:.0%}; values were preserved and not normalized."
        return self

    def to_legacy_scenario(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "scenario_hash": self.scenario_hash,
            "scenario_name": self.scenario_name,
            "scenario_description": self.scenario_description,
            "growth_outlook": self.growth_outlook,
            "inflation_direction": self.inflation_direction,
            "inflation_surprise": self.inflation_surprise,
            "central_bank_stance": self.central_bank_stance,
            "expected_policy_path": self.expected_policy_path or "data dependent",
            "fed_position": self.fed_position,
            "labor_market": self.labor_market,
            "financial_conditions": self.financial_conditions,
            "market_volatility": self.market_volatility,
            "credit_stress": self.credit_stress,
            "dollar_outlook": self.dollar_outlook,
            "commodity_shock": self.commodity_shock,
            "equity_valuation": self.equity_valuation,
            "time_horizon": self.time_horizon,
            "recession_probability": self.stated_probabilities.get("recession", self.stated_probabilities.get("mild_recession", 0.3)),
            "probability": None,
            "countries_or_regions": self.countries + self.custom_regions,
            "custom_assumptions": "",
            "risks": self.risks,
            "invalidation_triggers": self.invalidation_triggers,
            "confirming_indicators": self.confirming_indicators,
            "stated_probabilities": self.stated_probabilities,
            "parser_provider": self.parser_provider,
            "parser_model": self.parser_model,
            "parser_confidence": self.parser_confidence,
            "field_confidence": self.field_confidence,
            "field_excerpts": self.field_excerpts,
            "supporting_text_by_field": self.supporting_text_by_field or self.field_excerpts,
            "low_confidence_fields": self.low_confidence_fields,
            "parser_warnings": self.contradiction_warnings + ([self.probability_total_warning] if self.probability_total_warning else []),
            "contradiction_warnings": self.contradiction_warnings,
            "review_required": bool(self.contradiction_warnings or self.low_confidence_fields or self.probability_total_warning),
            "source_text": self.source_text,
            "phases": [phase.model_dump(mode="json") for phase in self.phases],
            "parse_duration_ms": self.parse_duration_ms,
            "parse_timing": self.parse_timing,
        }
