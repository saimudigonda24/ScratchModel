from collections import Counter

from app.services.database import list_historical_postmortems, list_institutional_documents, list_outcome_dashboard_data
from app.services.regime_labeling import regime_coverage_summary


def institutional_readiness_report() -> dict:
    docs = list_institutional_documents(1000)
    postmortems = list_historical_postmortems(1000)
    outcomes = list_outcome_dashboard_data()
    opportunity_outcomes = outcomes.get("opportunity_outcomes", [])
    positive = [row for row in opportunity_outcomes if row.get("hit_miss_label") == "hit"]
    negative = [row for row in opportunity_outcomes if row.get("hit_miss_label") == "miss"]
    asset_counts = Counter(row.get("asset_class") for row in opportunity_outcomes)
    successful = Counter(row.get("asset_class") for row in positive)
    failed = Counter(row.get("asset_class") for row in negative)
    return {
        "historical_hcp_reports_imported": len(docs),
        "reports_successfully_parsed": sum(1 for doc in docs if str(doc.get("parser_status", "")).startswith("parsed")),
        "reports_linked_to_outcomes": len(postmortems),
        "regime_coverage": regime_coverage_summary(),
        "asset_class_coverage": dict(asset_counts),
        "successful_thesis_distribution": dict(successful),
        "failed_thesis_distribution": dict(failed),
        "institutional_memory_coverage": {
            "indexed_documents": sum(1 for doc in docs if doc.get("memory_indexed")),
            "approved_documents": sum(1 for doc in docs if doc.get("ingestion_status") == "approved"),
        },
        "positive_training_examples": len(positive),
        "negative_training_examples": len(negative),
        "outcome_validated_examples": sum(1 for row in opportunity_outcomes if row.get("outcome_evaluated")),
    }
