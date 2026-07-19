from app.services.database import save_thesis_outcome


def score_thesis_outcome(run_id: str, thesis: dict, realized_context: dict | None = None) -> dict:
    context = realized_context or {}
    scores = {
        "growth_call_accuracy": context.get("growth_call_accuracy", 0.0),
        "inflation_call_accuracy": context.get("inflation_call_accuracy", 0.0),
        "central_bank_reaction_accuracy": context.get("central_bank_reaction_accuracy", 0.0),
        "country_overlay_accuracy": context.get("country_overlay_accuracy", 0.0),
        "probability_band_accuracy": context.get("probability_band_accuracy", 0.0),
        "key_invalidation_trigger_accuracy": context.get("key_invalidation_trigger_accuracy", 0.0),
        "narrative_quality_after_fact": context.get("narrative_quality_after_fact", 0.0),
    }
    scores["overall_thesis_score"] = sum(scores.values()) / len(scores)
    return {
        "run_id": run_id,
        "thesis_title": thesis.get("title", "Untitled thesis"),
        "start_date": context.get("start_date", ""),
        "target_horizon_months": thesis.get("horizon_months", [7, 14]),
        "outcome": {
            **scores,
            "what_went_right": context.get("what_went_right", []),
            "what_went_wrong": context.get("what_went_wrong", []),
            "missed_evidence": context.get("missed_evidence", []),
        },
    }


def save_thesis_score(run_id: str, thesis: dict, realized_context: dict | None = None) -> dict:
    payload = score_thesis_outcome(run_id, thesis, realized_context)
    save_thesis_outcome(payload)
    return payload

