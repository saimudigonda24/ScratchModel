from statistics import mean

from app.agents import (
    AltsAgent,
    CommoditiesAgent,
    ConvictionAgent,
    CryptoAgent,
    DebateJudgeAgent,
    EquityAgent,
    EvaluationAgent,
    FixedIncomeAgent,
    FXRatesAgent,
    HumanReviewAgent,
    MacroThesisAgent,
    MLPAgent,
    REITAgent,
    RiskHedgeAgent,
    TrainingDataBuilderAgent,
)
from app.connectors import ingest_all_sources
from app.models import AgentInput, FinalResearchOutput, HumanReport, MacroThesis, Opportunity
from app.services.database import save_run
from app.services.institutional_memory import retrieve_relevant_lessons
from app.services.investment_committee_report import generate_investment_committee_report
from app.services.knowledge_base import KnowledgeBaseService
from app.services.model_debate import run_model_debate
from app.services.storage import (
    save_evaluation,
    save_data_snapshots,
    save_raw_report,
    save_research_output,
    save_training_examples,
    timestamp_id,
)


class ResearchOrchestrator:
    """Coordinates the full HCP macro research workflow."""

    def run(self, report_text: str, report_title: str) -> FinalResearchOutput:
        run_id = timestamp_id("hcp_research")
        macro_snapshot = ingest_all_sources()
        save_data_snapshots(macro_snapshot, run_id)
        human_report = HumanReport(title=report_title, content=report_text)
        save_raw_report(report_text, report_title, run_id)
        knowledge_base = KnowledgeBaseService()
        knowledge_base.add_document(title=report_title, text=report_text, source_type="hcp_macro_report")
        retrieved_documents = [doc.__dict__ for doc in knowledge_base.retrieve(report_text, limit=5)]
        institutional_context = knowledge_base.retrieve_institutional_context(report_text, limit=8)
        lessons = retrieve_relevant_lessons(report_text, limit=5)

        agent_input = AgentInput(
            macro_snapshot=macro_snapshot,
            human_report=human_report,
            context={
                "run_id": run_id,
                "retrieved_documents": retrieved_documents,
                "institutional_context": institutional_context,
                "lessons_learned": lessons,
            },
        )
        agent_outputs: list[dict] = []

        thesis_output = MacroThesisAgent().run(agent_input)
        agent_outputs.append(thesis_output.model_dump(mode="json"))
        thesis = agent_input.context.get("thesis")
        if not isinstance(thesis, MacroThesis):
            raise RuntimeError("MacroThesisAgent did not produce a MacroThesis")
        agent_input.thesis = thesis

        asset_agents = [
            EquityAgent(),
            FixedIncomeAgent(),
            FXRatesAgent(),
            CommoditiesAgent(),
            CryptoAgent(),
            MLPAgent(),
            REITAgent(),
            AltsAgent(),
        ]
        opportunities: list[Opportunity] = []
        evidence: list[str] = []
        for agent in asset_agents:
            output = agent.run(agent_input)
            agent_outputs.append(output.model_dump(mode="json"))
            opportunities.extend(output.opportunities)
            for finding in output.findings:
                evidence.extend(finding.evidence)

        agent_input.context["opportunities"] = opportunities
        conviction_output = ConvictionAgent().run(agent_input)
        agent_outputs.append(conviction_output.model_dump(mode="json"))
        ranked = conviction_output.opportunities

        hedge_output = RiskHedgeAgent().run(agent_input)
        agent_outputs.append(hedge_output.model_dump(mode="json"))
        ranked_hedges = sorted(hedge_output.hedges, key=lambda item: item.conviction_score, reverse=True)
        agent_input.context["hedges"] = ranked_hedges

        model_debate = run_model_debate(thesis, macro_snapshot, ranked)
        agent_input.context["model_debate"] = model_debate
        debate_output = DebateJudgeAgent().run(agent_input)
        agent_outputs.append(debate_output.model_dump(mode="json"))
        human_review_output = HumanReviewAgent().run(agent_input)
        agent_outputs.append(human_review_output.model_dump(mode="json"))
        evaluation_output = EvaluationAgent().run(agent_input)
        agent_outputs.append(evaluation_output.model_dump(mode="json"))
        training_output = TrainingDataBuilderAgent().run(agent_input)
        agent_outputs.append(training_output.model_dump(mode="json"))

        conviction_score = mean([item.conviction_score for item in ranked]) if ranked else 0.0
        evidence.extend(thesis.base_case.evidence)
        evidence.extend([finding.summary for finding in thesis_output.findings])
        triggers = thesis.triggers + [trigger for item in ranked for trigger in item.triggers]

        result = FinalResearchOutput(
            thesis=thesis,
            probability_bands={
                "base_case": f"{thesis.base_case.probability:.0%}",
                "bull_case": f"{thesis.bull_case.probability:.0%}",
                "bear_tail_case": f"{thesis.bear_tail_case.probability:.0%}",
            },
            conviction_score=round(conviction_score, 1),
            ranked_opportunities=ranked,
            asymmetric_hedges=ranked_hedges,
            ranked_hedge_ideas=ranked_hedges,
            evidence=list(dict.fromkeys(evidence)),
            triggers=list(dict.fromkeys(triggers)),
            debate_notes=debate_output.notes,
            model_debate=model_debate,
            human_approval_status="pending",
            human_approval_queue=human_review_output.review_items,
            evaluation_result=evaluation_output.evaluation_result,
            training_examples=training_output.training_examples,
            source_status=macro_snapshot.source_status,
        )

        output_path = save_research_output(result.model_dump(mode="json"), run_id)
        training_path = save_training_examples([example.model_dump(mode="json") for example in result.training_examples], run_id)
        if result.evaluation_result:
            save_evaluation(result.evaluation_result.model_dump(mode="json"), run_id)

        result.saved_output_path = str(output_path)
        result.saved_training_path = str(training_path)
        save_research_output(result.model_dump(mode="json"), run_id)
        save_run(
            run_id=run_id,
            report_title=report_title,
            report_text=report_text,
            data_snapshot=macro_snapshot.model_dump(mode="json"),
            agent_outputs=agent_outputs,
            debate_payload=model_debate.model_dump(mode="json"),
            result=result,
        )
        ic_report = generate_investment_committee_report(
            run_id=run_id,
            result=result,
            retrieved_context=institutional_context,
            lessons=lessons,
        )
        result.saved_output_path = str(output_path)
        result.debate_notes = result.debate_notes + [f"Investment committee report saved: {ic_report['path']}"]
        return result
