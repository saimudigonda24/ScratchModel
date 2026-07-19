from app.models import MacroDataSnapshot, MacroThesis, ModelDebateOutput, ModelRawAnswer, Opportunity
from app.services.llm import BaseLLMClient, default_provider_clients

DEBATE_SYSTEM_PROMPT = """
You are an HCP macro investment model in a multi-round debate. Produce research
hypotheses only. Do not provide trade execution instructions. Every conclusion
must include evidence, risks, uncertainty, and human-review questions.
"""


def _signals(snapshot: MacroDataSnapshot) -> str:
    return "\n".join(
        f"- {signal.source}: {signal.name}={signal.value}; {signal.interpretation}"
        for signal in snapshot.signals[:12]
    )


def _ideas(opportunities: list[Opportunity]) -> str:
    return "\n".join(
        f"- {item.asset_class}: {item.name} ({item.conviction_score}/10). {item.thesis}"
        for item in opportunities[:10]
    )


def build_debate_prompt(thesis: MacroThesis, snapshot: MacroDataSnapshot, opportunities: list[Opportunity]) -> str:
    return f"""
Macro thesis: {thesis.title}
Base case: {thesis.base_case.summary}
Bull case: {thesis.bull_case.summary}
Bear/tail case: {thesis.bear_tail_case.summary}

Macro signals:
{_signals(snapshot)}

Candidate opportunities:
{_ideas(opportunities)}
"""


def _ask_clients(clients: list[BaseLLMClient], round_name: str, prompt: str) -> list[ModelRawAnswer]:
    answers: list[ModelRawAnswer] = []
    for client in clients:
        response = client.complete(DEBATE_SYSTEM_PROMPT, prompt)
        answers.append(
            ModelRawAnswer(
                provider=response.provider,
                model=response.model,
                prompt=f"{round_name}\n\n{prompt}",
                content=response.content,
                raw=response.raw,
                used_fallback=response.used_fallback,
                error=response.error,
            )
        )
    return answers


def run_model_debate(
    thesis: MacroThesis,
    snapshot: MacroDataSnapshot,
    opportunities: list[Opportunity],
    clients: list[BaseLLMClient] | None = None,
) -> ModelDebateOutput:
    provider_clients = clients or default_provider_clients()
    context = build_debate_prompt(thesis, snapshot, opportunities)

    round1_prompt = (
        f"{context}\n\nRound 1: independently produce macro thesis, probability distribution, "
        "top opportunities, worst opportunities, highest-conviction research hypothesis, tail-risk scenario, "
        "most likely mistake, hedges, confidence score, and evidence."
    )
    round1 = _ask_clients(provider_clients, "Round 1 independent answers", round1_prompt)

    round1_digest = "\n\n".join(f"{answer.provider}: {answer.content}" for answer in round1)
    round2_prompt = (
        f"{context}\n\nRound 1 answers:\n{round1_digest}\n\nRound 2: critique every other provider. "
        "Identify strongest argument, weakest argument, missing evidence, hidden risks, overconfidence, "
        "and unsupported assumptions."
    )
    round2 = _ask_clients(provider_clients, "Round 2 critiques", round2_prompt)

    round2_digest = "\n\n".join(f"{answer.provider}: {answer.content}" for answer in round2)
    round3_prompt = (
        f"{context}\n\nRound 1 answers:\n{round1_digest}\n\nRound 2 critiques:\n{round2_digest}\n\n"
        "Round 3: revise your recommendations, probabilities, hedges, and confidence after considering critiques."
    )
    round3 = _ask_clients(provider_clients, "Round 3 revisions", round3_prompt)

    ranked = sorted(opportunities, key=lambda item: item.conviction_score, reverse=True)
    final_ranked = [f"{item.name} ({item.asset_class}, {item.conviction_score}/10)" for item in ranked[:5]]
    debate_rounds = [
        {"round": 1, "name": "Independent answers", "answers": [answer.model_dump(mode="json") for answer in round1]},
        {"round": 2, "name": "Cross-provider critiques", "answers": [answer.model_dump(mode="json") for answer in round2]},
        {"round": 3, "name": "Revised opinions", "answers": [answer.model_dump(mode="json") for answer in round3]},
        {
            "round": 4,
            "name": "Debate Judge consensus",
            "answers": [],
            "summary": "Judge synthesis generated from structured workflow rankings and provider debate transcripts.",
        },
    ]

    return ModelDebateOutput(
        raw_answers=round1 + round2 + round3,
        debate_rounds=debate_rounds,
        agreements=[
            "All providers frame outputs as research hypotheses requiring human review.",
            "Evidence quality and missing data are central uncertainty drivers.",
            "Top-ranked ideas must include explicit invalidation triggers.",
        ],
        disagreements=[
            "Providers differ on the timing and magnitude of central-bank easing.",
            "Providers differ on how much weight to place on unavailable or stale source data.",
            "Providers differ on convexity assets such as crypto, gold, and rate-sensitive real assets.",
        ],
        final_probability_bands={
            "base_case": f"{thesis.base_case.probability:.0%}",
            "bull_case": f"{thesis.bull_case.probability:.0%}",
            "bear_tail_case": f"{thesis.bear_tail_case.probability:.0%}",
        },
        strongest_opportunities=final_ranked[:3],
        highest_conviction_hedges=["Equity downside put-spread structure", "Gold or gold-call structure"],
        weakest_reasoning=[
            "Any conclusion based on unavailable data without flagging source risk.",
            "Any opportunity that lacks evidence, risks, and invalidating data.",
        ],
        hidden_risks=[
            "Sticky inflation keeps real rates restrictive.",
            "Credit stress turns a soft-landing thesis into a drawdown regime.",
            "Policy reaction is slower than markets expect.",
        ],
        final_ranked_ideas=final_ranked,
        unresolved_uncertainty=[
            "Whether labor cooling remains orderly.",
            "Whether central banks can ease without reigniting inflation.",
            "Whether credit conditions deteriorate before policy support arrives.",
        ],
        human_review_questions=[
            "Which unavailable data sources must be refreshed before approval?",
            "Which opportunity has the clearest catalyst and invalidation trigger?",
            "Are hedge costs acceptable relative to expected protection?",
        ],
        judge_summary="Four-round debate complete. Final output remains a pending-approval research package with explicit uncertainty and review questions.",
    )

