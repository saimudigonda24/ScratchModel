"""Print a safe inventory of configured data sources and model providers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.env import load_env  # noqa: E402
from app.services.source_status import audit_sources  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-test-connections", action="store_true", help="Skip live connector probes and report cached/configured status only.")
    args = parser.parse_args()
    load_env()
    audit = audit_sources(test_connections=not args.no_test_connections)
    print("HCP Data Source & Model Provider Audit")
    print(f"Generated: {audit['generated_at']}")
    print("")
    for row in audit["records"]:
        required = ", ".join(row["required_environment_variables"]) or "none"
        print(
            f"- {row['source_name']} [{row['category']}] "
            f"connector={'yes' if row['connector_present'] else 'no'} "
            f"configured={'yes' if row['configured'] else 'no'} "
            f"reachable={'yes' if row['reachable'] else 'no'} "
            f"mode={row['mode']} "
            f"last_success={row['last_success'] or 'never'} "
            f"required_env={required}"
        )
        print(f"  data: {row['data_currently_retrieved']}")
        if row.get("latest_error"):
            print(f"  latest_error: {row['latest_error']}")
        print(f"  action: {row['action_needed']}")
    print("")
    print("Groups")
    for group, values in audit["groups"].items():
        print(f"- {group}: {', '.join(values) if values else 'none'}")
    print("")
    readiness = audit["comparison_readiness"]
    print(f"Scenario Comparison Readiness: {readiness['overall_status']}")
    for key, value in readiness.items():
        if key not in {"overall_status", "note"}:
            print(f"- {key}: {value}")
    print(f"Note: {readiness['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
