from app.services.database import list_lessons_learned, list_regime_labels


def training_eligibility_gate(example: dict, quality_threshold: float = 7.0) -> dict:
    rejection_notes = example.get("rejection_notes") or example.get("unresolved_rejection_notes") or []
    failure_pattern = example.get("repeated_failure_pattern", False)
    negative_training = example.get("negative_training_example", False)
    checks = {
        "human_approved": bool(example.get("human_approved") or example.get("approval_status") == "approved"),
        "evidence_complete": bool(example.get("evidence")),
        "risks_complete": bool(example.get("risks")),
        "proxy_mapped": bool(example.get("proxy_ticker")),
        "outcome_evaluated": bool(example.get("outcome_evaluated")),
        "regime_labeled": bool(example.get("regime_labels")),
        "no_unresolved_rejection_notes": not bool(rejection_notes),
        "quality_above_threshold": (example.get("quality_score") or 0) >= quality_threshold,
        "failure_pattern_allowed": not failure_pattern or negative_training,
    }
    eligible = all(checks.values())
    return {
        "eligible_for_fine_tuning": eligible,
        "checks": checks,
        "explanation": [
            name for name, passed in checks.items() if not passed
        ],
    }


def readiness_gate_explanation() -> list[str]:
    return [
        "Human approval is required before an example can enter the training set.",
        "Evidence, risks, proxy mapping, realized outcomes, and regime labels must be complete.",
        "The quality score must clear the configured threshold.",
        "Repeated failure patterns are blocked unless intentionally labeled as negative training examples.",
    ]


def repeated_failure_patterns() -> list[dict]:
    return list_lessons_learned(25)


def has_regime_label(run_id: str) -> bool:
    return any(row.get("run_id") == run_id for row in list_regime_labels())
