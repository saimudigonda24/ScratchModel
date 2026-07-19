from app.orchestration import ResearchOrchestrator
from app.models import FinalResearchOutput

DEFAULT_REPORT_TEXT = """
HCP research view: build a macro investing system that combines free market
data, human investment writing, multi-agent asset class analysis, conviction
scoring, risk hedging, human approval, evaluation, training-data capture, and
model debate. The target horizon is 7-14 months. Focus on inflation, rates,
growth, earnings, policy reaction functions, liquidity, and cross-asset
opportunities.
"""


def run_research_workflow(report_text: str | None = None, report_title: str = "HCP mock report") -> FinalResearchOutput:
    return ResearchOrchestrator().run(report_text=report_text or DEFAULT_REPORT_TEXT, report_title=report_title)

