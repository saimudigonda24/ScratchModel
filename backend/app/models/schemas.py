from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AssetClass = Literal[
    "equity",
    "fixed_income",
    "fx_rates",
    "commodity",
    "crypto",
    "mlp",
    "reit",
    "alts",
    "cross_asset",
]


class DataSignal(BaseModel):
    source: str
    name: str
    value: str
    as_of: str
    direction: Literal["improving", "deteriorating", "mixed", "neutral"]
    interpretation: str


class MacroDataSnapshot(BaseModel):
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    horizon_months: tuple[int, int] = (7, 14)
    signals: list[DataSignal]
    source_status: dict[str, str]


class HumanReport(BaseModel):
    title: str = "HCP human report"
    author: str | None = None
    content: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class CaseView(BaseModel):
    label: Literal["base", "bull", "bear_tail"]
    summary: str
    probability: float = Field(ge=0, le=1)
    evidence: list[str]


class MacroThesis(BaseModel):
    title: str
    horizon_months: tuple[int, int] = (7, 14)
    base_case: CaseView
    bull_case: CaseView
    bear_tail_case: CaseView
    key_signals: list[DataSignal]
    triggers: list[str]
    change_log: list[str]


class AgentInput(BaseModel):
    macro_snapshot: MacroDataSnapshot
    human_report: HumanReport
    thesis: MacroThesis | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class AgentFinding(BaseModel):
    title: str
    summary: str
    evidence: list[str]
    confidence: float = Field(ge=0, le=1)


class Opportunity(BaseModel):
    asset_class: AssetClass
    name: str
    thesis: str
    thesis_fit: str = "Aligned with the current macro thesis."
    catalyst: str = "Macro data confirms the expected regime."
    probability_band: str
    expected_horizon_months: tuple[int, int] = (7, 14)
    conviction_score: float = Field(ge=0, le=10)
    evidence: list[str]
    risks: list[str] = Field(default_factory=list)
    confirming_data: list[str] = Field(default_factory=list)
    invalidating_data: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    human_approval_status: Literal["pending", "approved", "rejected", "needs_revision"] = "pending"


class HedgeIdea(BaseModel):
    name: str
    asset_class: AssetClass
    rationale: str
    asymmetry: str
    thesis_fit: str = "Protects against key thesis risks."
    catalyst: str = "Hedge becomes more valuable if tail-risk indicators rise."
    evidence: list[str]
    trigger: str
    risks: list[str] = Field(default_factory=list)
    confirming_data: list[str] = Field(default_factory=list)
    invalidating_data: list[str] = Field(default_factory=list)
    conviction_score: float = Field(default=6.0, ge=0, le=10)
    human_approval_status: Literal["pending", "approved", "rejected", "needs_revision"] = "pending"


class AgentOutput(BaseModel):
    agent_name: str
    system_prompt: str
    findings: list[AgentFinding] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    hedges: list[HedgeIdea] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HumanReviewItem(BaseModel):
    item_type: Literal["opportunity", "hedge", "thesis", "workflow"]
    name: str
    reason: str
    priority: Literal["low", "medium", "high"]
    approval_status: Literal["pending", "approved", "rejected", "needs_revision"] = "pending"


class EvaluationResult(BaseModel):
    reasoning_quality: float = Field(ge=0, le=10)
    macro_consistency: float = Field(ge=0, le=10)
    evidence_quality: float = Field(ge=0, le=10)
    cross_asset_reasoning: float = Field(ge=0, le=10)
    risk_awareness: float = Field(ge=0, le=10)
    hedge_quality: float = Field(ge=0, le=10)
    clarity: float = Field(ge=0, le=10)
    actionability: float = Field(ge=0, le=10)
    notes: list[str]


class TrainingExample(BaseModel):
    example_id: str
    task: str
    input: dict[str, Any]
    output: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelRawAnswer(BaseModel):
    provider: str
    model: str
    prompt: str
    content: str
    raw: dict[str, Any] = Field(default_factory=dict)
    used_fallback: bool = False
    error: str | None = None


class ModelDebateOutput(BaseModel):
    raw_answers: list[ModelRawAnswer]
    debate_rounds: list[dict[str, Any]] = Field(default_factory=list)
    agreements: list[str]
    disagreements: list[str]
    final_probability_bands: dict[str, str] = Field(default_factory=dict)
    strongest_opportunities: list[str]
    highest_conviction_hedges: list[str] = Field(default_factory=list)
    weakest_reasoning: list[str]
    hidden_risks: list[str]
    final_ranked_ideas: list[str]
    unresolved_uncertainty: list[str] = Field(default_factory=list)
    human_review_questions: list[str] = Field(default_factory=list)
    judge_summary: str


class FinalResearchOutput(BaseModel):
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    thesis: MacroThesis
    probability_bands: dict[str, str]
    conviction_score: float = Field(ge=0, le=10)
    ranked_opportunities: list[Opportunity]
    asymmetric_hedges: list[HedgeIdea]
    ranked_hedge_ideas: list[HedgeIdea] = Field(default_factory=list)
    evidence: list[str]
    triggers: list[str]
    debate_notes: list[str]
    model_debate: ModelDebateOutput | None = None
    human_approval_status: Literal["pending", "approved", "rejected", "needs_revision"] = "pending"
    human_approval_queue: list[HumanReviewItem] = Field(default_factory=list)
    evaluation_result: EvaluationResult | None = None
    training_examples: list[TrainingExample] = Field(default_factory=list)
    saved_output_path: str | None = None
    saved_training_path: str | None = None
    source_status: dict[str, str]
    disclaimer: str = (
        "Research hypotheses for human review only. This is not financial advice, "
        "live trading, or automatic order execution."
    )


class WorkflowRequest(BaseModel):
    report_text: str | None = None
    report_title: str = "HCP mock report"
