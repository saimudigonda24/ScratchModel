import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models import FinalResearchOutput, HumanReviewItem

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "data" / "hcp_research.sqlite3"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS macro_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                training_approved INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS macro_thesis_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                title TEXT NOT NULL,
                thesis_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                name TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                conviction_score REAL NOT NULL,
                approval_status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS hedges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                name TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                conviction_score REAL NOT NULL,
                approval_status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS model_debate_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS human_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                name TEXT NOT NULL,
                reason TEXT NOT NULL,
                priority TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS training_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                example_id TEXT NOT NULL,
                task TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evaluation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS data_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS thesis_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                thesis_title TEXT NOT NULL,
                start_date TEXT NOT NULL,
                target_horizon_months TEXT NOT NULL,
                outcome_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS opportunity_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                idea_id TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                instrument TEXT NOT NULL,
                proxy_ticker TEXT NOT NULL,
                thesis_fit TEXT NOT NULL,
                start_date TEXT NOT NULL,
                target_horizon_months TEXT NOT NULL,
                benchmark TEXT NOT NULL,
                expected_direction TEXT NOT NULL,
                expected_catalyst TEXT NOT NULL,
                invalidation_trigger TEXT NOT NULL,
                approved_probability REAL,
                conviction_score REAL NOT NULL,
                realized_return REAL,
                benchmark_return REAL,
                max_drawdown REAL,
                volatility REAL,
                sharpe_like REAL,
                hit_miss_label TEXT,
                outcome_evaluated INTEGER NOT NULL DEFAULT 0,
                outcome_quality_score REAL,
                eligible_for_fine_tuning INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS hedge_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                hedge_id TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                instrument TEXT NOT NULL,
                proxy_ticker TEXT NOT NULL,
                start_date TEXT NOT NULL,
                target_horizon_months TEXT NOT NULL,
                stress_window TEXT,
                hedge_effectiveness REAL,
                realized_return REAL,
                max_drawdown REAL,
                volatility REAL,
                outcome_evaluated INTEGER NOT NULL DEFAULT 0,
                outcome_quality_score REAL,
                eligible_for_fine_tuning INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS forecast_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                forecast_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                probability REAL NOT NULL,
                actual_outcome INTEGER,
                brier_score REAL,
                calibration_bucket TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS realized_market_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                total_return REAL NOT NULL,
                max_drawdown REAL NOT NULL,
                volatility REAL NOT NULL,
                sharpe_like REAL NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS daily_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL NOT NULL,
                adj_close REAL,
                volume REAL,
                source TEXT NOT NULL,
                raw_json TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(ticker, date, source)
            );
            CREATE TABLE IF NOT EXISTS proxy_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                item_id TEXT NOT NULL,
                proxy_ticker TEXT NOT NULL,
                benchmark_ticker TEXT NOT NULL,
                expected_direction TEXT NOT NULL,
                start_date TEXT NOT NULL,
                target_horizon_months TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(run_id, item_type, item_id)
            );
            CREATE TABLE IF NOT EXISTS scheduled_job_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                message TEXT,
                command TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                job_name TEXT PRIMARY KEY,
                cadence TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                target TEXT,
                command TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 2,
                next_run_time TEXT,
                last_success_time TEXT,
                last_failure_time TEXT,
                last_error_message TEXT,
                last_duration_seconds REAL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS regime_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT,
                labels_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(run_id, period_start)
            );
            CREATE TABLE IF NOT EXISTS lessons_learned (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_type TEXT NOT NULL,
                pattern TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                severity REAL NOT NULL,
                recommendation TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS historical_backtest_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                as_of TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(as_of)
            );
            CREATE TABLE IF NOT EXISTS institutional_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                author TEXT,
                publication_date TEXT NOT NULL,
                report_type TEXT NOT NULL,
                original_source TEXT NOT NULL,
                source_path TEXT NOT NULL,
                original_text TEXT NOT NULL,
                structured_json TEXT NOT NULL,
                parser_status TEXT NOT NULL,
                ingestion_status TEXT NOT NULL DEFAULT 'pending_approval',
                memory_indexed INTEGER NOT NULL DEFAULT 0,
                outcome_linked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS historical_postmortems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(document_id)
            );
            CREATE TABLE IF NOT EXISTS investment_committee_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                report_json TEXT NOT NULL,
                markdown TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scenario_sequences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scenario_phases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phase_id TEXT NOT NULL UNIQUE,
                sequence_id TEXT NOT NULL,
                phase_number INTEGER NOT NULL,
                scenario_json TEXT NOT NULL,
                data_snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scenario_analogs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phase_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scenario_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id TEXT NOT NULL UNIQUE,
                phase_id TEXT NOT NULL,
                sequence_id TEXT NOT NULL,
                recommendation_json TEXT NOT NULL,
                frozen_snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scenario_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recommendation_id TEXT NOT NULL,
                horizon_months INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(recommendation_id, horizon_months)
            );
            CREATE TABLE IF NOT EXISTS scenario_postmortems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phase_id TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(macro_reports)").fetchall()]
        if "training_approved" not in columns:
            conn.execute("ALTER TABLE macro_reports ADD COLUMN training_approved INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    finally:
        conn.close()


def save_daily_prices(ticker: str, rows: list[dict[str, Any]], source: str = "Yahoo Finance") -> int:
    init_db()
    conn = connect()
    inserted = 0
    try:
        for row in rows:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO daily_prices (
                    ticker, date, open, high, low, close, adj_close, volume, source, raw_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker,
                    row["date"],
                    row.get("open"),
                    row.get("high"),
                    row.get("low"),
                    row["close"],
                    row.get("adj_close"),
                    row.get("volume"),
                    source,
                    _dump(row.get("raw", row)),
                    _now(),
                ),
            )
            inserted += cursor.rowcount
        conn.commit()
        return inserted
    finally:
        conn.close()


def load_daily_prices(ticker: str, start_date: str, end_date: str, source: str | None = None) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        if source:
            rows = conn.execute(
                """
                SELECT * FROM daily_prices
                WHERE ticker = ? AND source = ? AND date >= ? AND date <= ?
                ORDER BY date
                """,
                (ticker, source, start_date, end_date),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM daily_prices
                WHERE ticker = ? AND date >= ? AND date <= ?
                ORDER BY date
                """,
                (ticker, start_date, end_date),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def save_proxy_override(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = connect()
    now = _now()
    try:
        conn.execute(
            """
            INSERT INTO proxy_overrides (
                run_id, item_type, item_id, proxy_ticker, benchmark_ticker,
                expected_direction, start_date, target_horizon_months, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, item_type, item_id) DO UPDATE SET
                proxy_ticker = excluded.proxy_ticker,
                benchmark_ticker = excluded.benchmark_ticker,
                expected_direction = excluded.expected_direction,
                start_date = excluded.start_date,
                target_horizon_months = excluded.target_horizon_months,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                payload["run_id"],
                payload.get("item_type", "opportunity"),
                payload["item_id"],
                payload["proxy_ticker"],
                payload.get("benchmark_ticker", "SPY"),
                payload.get("expected_direction", "long"),
                payload["start_date"],
                json.dumps(payload.get("target_horizon_months", [7, 14])),
                payload.get("notes", ""),
                now,
                now,
            ),
        )
        conn.commit()
        return load_proxy_override(payload["run_id"], payload.get("item_type", "opportunity"), payload["item_id"]) or {}
    finally:
        conn.close()


def load_proxy_override(run_id: str, item_type: str, item_id: str) -> dict[str, Any] | None:
    init_db()
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM proxy_overrides WHERE run_id = ? AND item_type = ? AND item_id = ?",
            (run_id, item_type, item_id),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["target_horizon_months"] = json.loads(result["target_horizon_months"])
        return result
    finally:
        conn.close()


def list_proxy_overrides() -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM proxy_overrides ORDER BY id DESC").fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["target_horizon_months"] = json.loads(item["target_horizon_months"])
            results.append(item)
        return results
    finally:
        conn.close()


def save_opportunity_outcome(payload: dict[str, Any]) -> int:
    init_db()
    conn = connect()
    now = _now()
    try:
        cursor = conn.execute(
            """
            INSERT INTO opportunity_outcomes (
                run_id, idea_id, asset_class, instrument, proxy_ticker, thesis_fit,
                start_date, target_horizon_months, benchmark, expected_direction,
                expected_catalyst, invalidation_trigger, approved_probability,
                conviction_score, realized_return, benchmark_return, max_drawdown,
                volatility, sharpe_like, hit_miss_label, outcome_evaluated,
                outcome_quality_score, eligible_for_fine_tuning, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["run_id"],
                payload["idea_id"],
                payload["asset_class"],
                payload["instrument"],
                payload["proxy_ticker"],
                payload.get("thesis_fit", ""),
                payload["start_date"],
                json.dumps(payload.get("target_horizon_months", [7, 14])),
                payload.get("benchmark", "SPY"),
                payload.get("expected_direction", "long"),
                payload.get("expected_catalyst", ""),
                payload.get("invalidation_trigger", ""),
                payload.get("approved_probability"),
                payload.get("conviction_score", 0),
                payload.get("realized_return"),
                payload.get("benchmark_return"),
                payload.get("max_drawdown"),
                payload.get("volatility"),
                payload.get("sharpe_like"),
                payload.get("hit_miss_label"),
                int(payload.get("outcome_evaluated", False)),
                payload.get("outcome_quality_score"),
                int(payload.get("eligible_for_fine_tuning", False)),
                payload.get("notes", ""),
                now,
                now,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def save_hedge_outcome(payload: dict[str, Any]) -> int:
    init_db()
    conn = connect()
    now = _now()
    try:
        cursor = conn.execute(
            """
            INSERT INTO hedge_outcomes (
                run_id, hedge_id, asset_class, instrument, proxy_ticker, start_date,
                target_horizon_months, stress_window, hedge_effectiveness,
                realized_return, max_drawdown, volatility, outcome_evaluated,
                outcome_quality_score, eligible_for_fine_tuning, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["run_id"],
                payload["hedge_id"],
                payload["asset_class"],
                payload["instrument"],
                payload["proxy_ticker"],
                payload["start_date"],
                json.dumps(payload.get("target_horizon_months", [7, 14])),
                payload.get("stress_window"),
                payload.get("hedge_effectiveness"),
                payload.get("realized_return"),
                payload.get("max_drawdown"),
                payload.get("volatility"),
                int(payload.get("outcome_evaluated", False)),
                payload.get("outcome_quality_score"),
                int(payload.get("eligible_for_fine_tuning", False)),
                payload.get("notes", ""),
                now,
                now,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def save_thesis_outcome(payload: dict[str, Any]) -> int:
    init_db()
    conn = connect()
    now = _now()
    try:
        cursor = conn.execute(
            """
            INSERT INTO thesis_outcomes (
                run_id, thesis_title, start_date, target_horizon_months,
                outcome_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["run_id"],
                payload["thesis_title"],
                payload["start_date"],
                json.dumps(payload.get("target_horizon_months", [7, 14])),
                _dump(payload["outcome"]),
                now,
                now,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def save_forecast_outcome(payload: dict[str, Any]) -> int:
    init_db()
    conn = connect()
    now = _now()
    try:
        cursor = conn.execute(
            """
            INSERT INTO forecast_outcomes (
                run_id, forecast_id, event_name, probability, actual_outcome,
                brier_score, calibration_bucket, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["run_id"],
                payload["forecast_id"],
                payload["event_name"],
                payload["probability"],
                payload.get("actual_outcome"),
                payload.get("brier_score"),
                payload.get("calibration_bucket"),
                now,
                now,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def save_realized_market_return(payload: dict[str, Any]) -> int:
    init_db()
    conn = connect()
    try:
        cursor = conn.execute(
            """
            INSERT INTO realized_market_returns (
                ticker, start_date, end_date, total_return, max_drawdown,
                volatility, sharpe_like, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["ticker"],
                payload["start_date"],
                payload["end_date"],
                payload["total_return"],
                payload["max_drawdown"],
                payload["volatility"],
                payload["sharpe_like"],
                payload.get("source", "unknown"),
                _now(),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def list_outcome_dashboard_data() -> dict[str, list[dict[str, Any]]]:
    init_db()
    conn = connect()
    try:
        approved = conn.execute(
            """
            SELECT o.id, o.run_id, o.name, o.asset_class, o.conviction_score, o.payload_json, o.created_at
            FROM opportunities o
            LEFT JOIN opportunity_outcomes oo ON oo.run_id = o.run_id AND oo.idea_id = o.name
            WHERE o.approval_status = 'pending' OR oo.id IS NULL
            ORDER BY o.id DESC
            LIMIT 100
            """
        ).fetchall()
        opportunity_rows = []
        for row in approved:
            payload = json.loads(row["payload_json"])
            opportunity_rows.append(
                {
                    "id": row["id"],
                    "run_id": row["run_id"],
                    "name": row["name"],
                    "asset_class": row["asset_class"],
                    "conviction_score": row["conviction_score"],
                    "thesis_fit": payload.get("thesis_fit", ""),
                    "proxy_ticker": "",
                    "created_at": row["created_at"],
                }
            )
        realized = [dict(row) for row in conn.execute("SELECT * FROM realized_market_returns ORDER BY id DESC LIMIT 100").fetchall()]
        opportunity_outcomes = [dict(row) for row in conn.execute("SELECT * FROM opportunity_outcomes ORDER BY id DESC LIMIT 100").fetchall()]
        hedge_outcomes = [dict(row) for row in conn.execute("SELECT * FROM hedge_outcomes ORDER BY id DESC LIMIT 100").fetchall()]
        thesis_outcomes = [dict(row) for row in conn.execute("SELECT * FROM thesis_outcomes ORDER BY id DESC LIMIT 100").fetchall()]
        forecasts = [dict(row) for row in conn.execute("SELECT * FROM forecast_outcomes ORDER BY id DESC LIMIT 100").fetchall()]
        return {
            "approved_opportunities_awaiting_outcomes": opportunity_rows,
            "realized_market_returns": realized,
            "opportunity_outcomes": opportunity_outcomes,
            "hedge_outcomes": hedge_outcomes,
            "thesis_outcomes": thesis_outcomes,
            "forecast_outcomes": forecasts,
        }
    finally:
        conn.close()


def _now() -> str:
    return datetime.utcnow().isoformat()


def _dump(payload: Any) -> str:
    return json.dumps(payload, default=str)


def save_run(
    run_id: str,
    report_title: str,
    report_text: str,
    data_snapshot: dict[str, Any],
    agent_outputs: list[dict[str, Any]],
    debate_payload: dict[str, Any],
    result: FinalResearchOutput,
) -> None:
    init_db()
    conn = connect()
    created_at = _now()
    try:
        conn.execute(
            "INSERT INTO macro_reports (run_id, title, content, created_at, training_approved) VALUES (?, ?, ?, ?, 0)",
            (run_id, report_title, report_text, created_at),
        )
        conn.execute(
            "INSERT INTO macro_thesis_versions (run_id, title, thesis_json, created_at) VALUES (?, ?, ?, ?)",
            (run_id, result.thesis.title, _dump(result.thesis.model_dump(mode="json")), created_at),
        )
        conn.execute(
            "INSERT INTO data_snapshots (run_id, payload_json, created_at) VALUES (?, ?, ?)",
            (run_id, _dump(data_snapshot), created_at),
        )
        for output in agent_outputs:
            conn.execute(
                "INSERT INTO agent_outputs (run_id, agent_name, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (run_id, output.get("agent_name", "unknown"), _dump(output), created_at),
            )
        for item in result.ranked_opportunities:
            conn.execute(
                """
                INSERT INTO opportunities (run_id, name, asset_class, conviction_score, approval_status, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    item.name,
                    item.asset_class,
                    item.conviction_score,
                    item.human_approval_status,
                    _dump(item.model_dump(mode="json")),
                    created_at,
                ),
            )
        for item in result.ranked_hedge_ideas:
            conn.execute(
                """
                INSERT INTO hedges (run_id, name, asset_class, conviction_score, approval_status, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    item.name,
                    item.asset_class,
                    item.conviction_score,
                    item.human_approval_status,
                    _dump(item.model_dump(mode="json")),
                    created_at,
                ),
            )
        conn.execute(
            "INSERT INTO model_debate_outputs (run_id, payload_json, created_at) VALUES (?, ?, ?)",
            (run_id, _dump(debate_payload), created_at),
        )
        for item in result.human_approval_queue:
            conn.execute(
                """
                INSERT INTO human_approvals (run_id, item_type, name, reason, priority, approval_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, item.item_type, item.name, item.reason, item.priority, item.approval_status, created_at, created_at),
            )
        for item in result.training_examples:
            conn.execute(
                """
                INSERT INTO training_examples (run_id, example_id, task, approval_status, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    item.example_id,
                    item.task,
                    item.metadata.get("approval_status", "pending"),
                    _dump(item.model_dump(mode="json")),
                    created_at,
                ),
            )
        if result.evaluation_result:
            conn.execute(
                "INSERT INTO evaluation_results (run_id, payload_json, created_at) VALUES (?, ?, ?)",
                (run_id, _dump(result.evaluation_result.model_dump(mode="json")), created_at),
            )
        conn.commit()
    finally:
        conn.close()


def list_reports(limit: int = 25) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT run_id, title, created_at, training_approved FROM macro_reports ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_thesis_versions(limit: int = 25) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT run_id, title, thesis_json, created_at FROM macro_thesis_versions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{**dict(row), "thesis": json.loads(row["thesis_json"])} for row in rows]
    finally:
        conn.close()


def list_debates(limit: int = 25) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT run_id, payload_json, created_at FROM model_debate_outputs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]
    finally:
        conn.close()


def list_approval_queue(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT id, run_id, item_type, name, reason, priority, approval_status, created_at, updated_at FROM human_approvals ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _payload_for_approval(conn: sqlite3.Connection, run_id: str, item_type: str, name: str) -> dict[str, Any]:
    if item_type == "opportunity":
        row = conn.execute(
            "SELECT payload_json FROM opportunities WHERE run_id = ? AND name = ? ORDER BY id DESC LIMIT 1",
            (run_id, name),
        ).fetchone()
        return json.loads(row["payload_json"]) if row else {}
    if item_type == "hedge":
        row = conn.execute(
            "SELECT payload_json FROM hedges WHERE run_id = ? AND name = ? ORDER BY id DESC LIMIT 1",
            (run_id, name),
        ).fetchone()
        return json.loads(row["payload_json"]) if row else {}
    if item_type == "thesis":
        row = conn.execute(
            "SELECT thesis_json FROM macro_thesis_versions WHERE run_id = ? ORDER BY id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if not row:
            return {}
        thesis = json.loads(row["thesis_json"])
        return {
            "name": thesis.get("title", name),
            "asset_class": "cross_asset",
            "thesis_fit": thesis.get("base_case", {}).get("summary", ""),
            "evidence": thesis.get("base_case", {}).get("evidence", []),
            "risks": thesis.get("bear_tail_case", {}).get("evidence", []),
            "confirming_data": thesis.get("bull_case", {}).get("evidence", []),
            "invalidating_data": thesis.get("triggers", []),
        }
    return {}


def list_approval_queue_detailed(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT id, run_id, item_type, name, reason, priority, approval_status, created_at, updated_at FROM human_approvals ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        detailed: list[dict[str, Any]] = []
        debate_cache: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = dict(row)
            payload = _payload_for_approval(conn, item["run_id"], item["item_type"], item["name"])
            if item["run_id"] not in debate_cache:
                debate_row = conn.execute(
                    "SELECT payload_json FROM model_debate_outputs WHERE run_id = ? ORDER BY id DESC LIMIT 1",
                    (item["run_id"],),
                ).fetchone()
                debate_cache[item["run_id"]] = json.loads(debate_row["payload_json"]) if debate_row else {}
            debate = debate_cache[item["run_id"]]
            item.update(
                {
                    "asset_class": payload.get("asset_class", "cross_asset"),
                    "thesis_fit": payload.get("thesis_fit") or payload.get("thesis") or payload.get("rationale") or "",
                    "evidence": payload.get("evidence", []),
                    "risks": payload.get("risks", []),
                    "confirming_data": payload.get("confirming_data", []),
                    "invalidating_data": payload.get("invalidating_data", []),
                    "model_debate_notes": {
                        "judge_summary": debate.get("judge_summary"),
                        "agreements": debate.get("agreements", []),
                        "disagreements": debate.get("disagreements", []),
                        "hidden_risks": debate.get("hidden_risks", []),
                        "final_ranked_ideas": debate.get("final_ranked_ideas", []),
                    },
                }
            )
            detailed.append(item)
        return detailed
    finally:
        conn.close()


def update_approval(approval_id: int, status: str) -> dict[str, Any]:
    if status not in {"approved", "rejected", "needs_revision", "pending"}:
        raise ValueError("Invalid approval status")
    init_db()
    conn = connect()
    try:
        conn.execute(
            "UPDATE human_approvals SET approval_status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), approval_id),
        )
        row = conn.execute("SELECT * FROM human_approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            raise ValueError("Approval item not found")
        run_id = row["run_id"]
        remaining = conn.execute(
            "SELECT COUNT(*) AS count FROM human_approvals WHERE run_id = ? AND approval_status != 'approved'",
            (run_id,),
        ).fetchone()["count"]
        if remaining == 0:
            conn.execute(
                "UPDATE training_examples SET approval_status = 'approved' WHERE run_id = ?",
                (run_id,),
            )
            conn.execute(
                "UPDATE macro_reports SET training_approved = 1 WHERE run_id = ?",
                (run_id,),
            )
        elif status in {"rejected", "needs_revision"}:
            conn.execute(
                "UPDATE training_examples SET approval_status = ? WHERE run_id = ?",
                (status, run_id),
            )
            conn.execute(
                "UPDATE macro_reports SET training_approved = 0 WHERE run_id = ?",
                (run_id,),
            )
        else:
            conn.execute(
                "UPDATE macro_reports SET training_approved = 0 WHERE run_id = ?",
                (run_id,),
            )
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def approved_training_examples() -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT payload_json FROM training_examples WHERE approval_status = 'approved' ORDER BY id"
        ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]
    finally:
        conn.close()


def list_approved_training_runs() -> list[dict[str, Any]]:
    """Return approved runs with report, data snapshot, and saved output payloads."""
    init_db()
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT mr.run_id, mr.title, mr.content, mr.created_at
            FROM macro_reports mr
            JOIN training_examples te ON te.run_id = mr.run_id
            WHERE te.approval_status = 'approved' AND mr.training_approved = 1
            ORDER BY mr.id
            """
        ).fetchall()
        runs: list[dict[str, Any]] = []
        for row in rows:
            run_id = row["run_id"]
            snapshot_row = conn.execute(
                "SELECT payload_json FROM data_snapshots WHERE run_id = ? ORDER BY id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            evaluation_row = conn.execute(
                "SELECT payload_json FROM evaluation_results WHERE run_id = ? ORDER BY id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            output_path = ROOT / "reports" / "outputs" / f"{run_id}.json"
            if not snapshot_row or not evaluation_row or not output_path.exists():
                continue
            evaluation = json.loads(evaluation_row["payload_json"])
            minimum_quality = min(
                evaluation.get("reasoning_quality", 0),
                evaluation.get("macro_consistency", 0),
                evaluation.get("evidence_quality", 0),
                evaluation.get("cross_asset_reasoning", 0),
                evaluation.get("risk_awareness", 0),
                evaluation.get("hedge_quality", 0),
                evaluation.get("clarity", 0),
                evaluation.get("actionability", 0),
            )
            if minimum_quality < 6.0:
                continue
            outcome_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM opportunity_outcomes
                WHERE run_id = ? AND outcome_evaluated = 1 AND eligible_for_fine_tuning = 1
                """,
                (run_id,),
            ).fetchone()["count"]
            if outcome_count == 0:
                continue
            runs.append(
                {
                    "run_id": run_id,
                    "report_title": row["title"],
                    "human_report": row["content"],
                    "created_at": row["created_at"],
                    "macro_data_snapshot": json.loads(snapshot_row["payload_json"]),
                    "research_output": json.loads(output_path.read_text()),
                    "quality_scores": evaluation,
                    "outcome_evaluated": True,
                    "eligible_for_fine_tuning": True,
                }
            )
        return runs
    finally:
        conn.close()


def outcome_summary() -> dict[str, Any]:
    data = list_outcome_dashboard_data()
    opportunities = data["opportunity_outcomes"]
    hit_rows = [row for row in opportunities if row.get("hit_miss_label") in {"hit", "miss"}]
    hit_rate = (
        sum(1 for row in hit_rows if row["hit_miss_label"] == "hit") / len(hit_rows)
        if hit_rows
        else 0.0
    )
    by_asset: dict[str, dict[str, Any]] = {}
    for row in hit_rows:
        bucket = by_asset.setdefault(row["asset_class"], {"count": 0, "hits": 0})
        bucket["count"] += 1
        bucket["hits"] += 1 if row["hit_miss_label"] == "hit" else 0
    hit_rate_by_asset = {
        asset_class: values["hits"] / values["count"]
        for asset_class, values in by_asset.items()
        if values["count"]
    }
    conviction_buckets: dict[str, list[float]] = {}
    for row in opportunities:
        score = row.get("conviction_score") or 0
        bucket = f"{int(score // 2 * 2)}-{int(score // 2 * 2 + 2)}"
        if row.get("realized_return") is not None:
            conviction_buckets.setdefault(bucket, []).append(row["realized_return"])
    avg_return_by_conviction = {
        bucket: sum(values) / len(values)
        for bucket, values in conviction_buckets.items()
        if values
    }
    sorted_outcomes = sorted(
        [row for row in opportunities if row.get("realized_return") is not None],
        key=lambda row: row["realized_return"],
    )
    return {
        **data,
        "hit_rate": hit_rate,
        "hit_rate_by_asset_class": hit_rate_by_asset,
        "average_return_by_conviction_bucket": avg_return_by_conviction,
        "best_recommendations": sorted_outcomes[-5:],
        "worst_recommendations": sorted_outcomes[:5],
    }


def record_scheduled_job_run(job_name: str, status: str, started_at: str, finished_at: str | None, message: str, command: str) -> int:
    init_db()
    conn = connect()
    try:
        cursor = conn.execute(
            """
            INSERT INTO scheduled_job_runs (
                job_name, status, started_at, finished_at, message, command, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job_name, status, started_at, finished_at, message, command, _now()),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def list_scheduled_job_runs(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM scheduled_job_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def upsert_scheduled_job(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = connect()
    now = _now()
    try:
        conn.execute(
            """
            INSERT INTO scheduled_jobs (
                job_name, cadence, enabled, target, command, max_retries,
                next_run_time, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_name) DO UPDATE SET
                cadence = excluded.cadence,
                enabled = excluded.enabled,
                target = excluded.target,
                command = excluded.command,
                max_retries = excluded.max_retries,
                next_run_time = COALESCE(scheduled_jobs.next_run_time, excluded.next_run_time),
                updated_at = excluded.updated_at
            """,
            (
                payload["job_name"],
                payload["cadence"],
                int(payload.get("enabled", True)),
                payload.get("target", ""),
                payload.get("command", ""),
                payload.get("max_retries", 2),
                payload.get("next_run_time"),
                now,
            ),
        )
        conn.commit()
        return get_scheduled_job(payload["job_name"]) or {}
    finally:
        conn.close()


def get_scheduled_job(job_name: str) -> dict[str, Any] | None:
    init_db()
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM scheduled_jobs WHERE job_name = ?", (job_name,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_scheduled_jobs() -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM scheduled_jobs ORDER BY job_name").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_scheduled_job_state(job_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = connect()
    allowed = {
        "enabled",
        "retry_count",
        "next_run_time",
        "last_success_time",
        "last_failure_time",
        "last_error_message",
        "last_duration_seconds",
    }
    updates = {key: value for key, value in payload.items() if key in allowed}
    updates["updated_at"] = _now()
    try:
        assignments = ", ".join(f"{key} = ?" for key in updates)
        conn.execute(
            f"UPDATE scheduled_jobs SET {assignments} WHERE job_name = ?",
            (*updates.values(), job_name),
        )
        conn.commit()
        return get_scheduled_job(job_name) or {}
    finally:
        conn.close()


def save_regime_label(payload: dict[str, Any]) -> int:
    init_db()
    conn = connect()
    try:
        cursor = conn.execute(
            """
            INSERT INTO regime_labels (
                run_id, period_start, period_end, labels_json, evidence_json, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, period_start) DO UPDATE SET
                period_end = excluded.period_end,
                labels_json = excluded.labels_json,
                evidence_json = excluded.evidence_json,
                confidence = excluded.confidence
            """,
            (
                payload["run_id"],
                payload["period_start"],
                payload.get("period_end"),
                _dump(payload.get("labels", [])),
                _dump(payload.get("evidence", {})),
                payload.get("confidence", 0.0),
                _now(),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def list_regime_labels(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM regime_labels ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["labels"] = json.loads(item.pop("labels_json"))
            item["evidence"] = json.loads(item.pop("evidence_json"))
            results.append(item)
        return results
    finally:
        conn.close()


def save_lesson_learned(payload: dict[str, Any]) -> int:
    init_db()
    conn = connect()
    try:
        cursor = conn.execute(
            """
            INSERT INTO lessons_learned (
                lesson_type, pattern, evidence_json, severity, recommendation, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload["lesson_type"],
                payload["pattern"],
                _dump(payload.get("evidence", [])),
                payload.get("severity", 0.0),
                payload.get("recommendation", ""),
                _now(),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def list_lessons_learned(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM lessons_learned ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["evidence"] = json.loads(item.pop("evidence_json"))
            results.append(item)
        return results
    finally:
        conn.close()


def save_backtest_summary(as_of: str, payload: dict[str, Any]) -> int:
    init_db()
    conn = connect()
    try:
        cursor = conn.execute(
            """
            INSERT INTO historical_backtest_summaries (as_of, payload_json, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(as_of) DO UPDATE SET
                payload_json = excluded.payload_json,
                created_at = excluded.created_at
            """,
            (as_of, _dump(payload), _now()),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def list_backtest_summaries(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM historical_backtest_summaries ORDER BY as_of DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]
    finally:
        conn.close()


def save_institutional_document(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = connect()
    now = _now()
    try:
        conn.execute(
            """
            INSERT INTO institutional_documents (
                document_id, title, author, publication_date, report_type,
                original_source, source_path, original_text, structured_json,
                parser_status, ingestion_status, memory_indexed, outcome_linked,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                title = excluded.title,
                author = excluded.author,
                publication_date = excluded.publication_date,
                report_type = excluded.report_type,
                original_source = excluded.original_source,
                source_path = excluded.source_path,
                original_text = excluded.original_text,
                structured_json = excluded.structured_json,
                parser_status = excluded.parser_status,
                ingestion_status = excluded.ingestion_status,
                memory_indexed = excluded.memory_indexed,
                outcome_linked = excluded.outcome_linked,
                updated_at = excluded.updated_at
            """,
            (
                payload["document_id"],
                payload["title"],
                payload.get("author"),
                payload["publication_date"],
                payload.get("report_type", "macro_report"),
                payload.get("original_source", ""),
                payload.get("source_path", ""),
                payload.get("original_text", ""),
                _dump(payload.get("structured", {})),
                payload.get("parser_status", "parsed"),
                payload.get("ingestion_status", "pending_approval"),
                int(payload.get("memory_indexed", False)),
                int(payload.get("outcome_linked", False)),
                now,
                now,
            ),
        )
        conn.commit()
        return get_institutional_document(payload["document_id"]) or {}
    finally:
        conn.close()


def get_institutional_document(document_id: str) -> dict[str, Any] | None:
    init_db()
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM institutional_documents WHERE document_id = ?", (document_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["structured"] = json.loads(item.pop("structured_json"))
        return item
    finally:
        conn.close()


def list_institutional_documents(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM institutional_documents ORDER BY publication_date DESC, id DESC LIMIT ?", (limit,)).fetchall()
        docs = []
        for row in rows:
            item = dict(row)
            item["structured"] = json.loads(item.pop("structured_json"))
            docs.append(item)
        return docs
    finally:
        conn.close()


def approve_institutional_document(document_id: str) -> dict[str, Any]:
    init_db()
    conn = connect()
    try:
        conn.execute(
            "UPDATE institutional_documents SET ingestion_status = 'approved', updated_at = ? WHERE document_id = ?",
            (_now(), document_id),
        )
        conn.commit()
        return get_institutional_document(document_id) or {}
    finally:
        conn.close()


def mark_document_memory_indexed(document_id: str, indexed: bool = True) -> None:
    init_db()
    conn = connect()
    try:
        conn.execute(
            "UPDATE institutional_documents SET memory_indexed = ?, updated_at = ? WHERE document_id = ?",
            (int(indexed), _now(), document_id),
        )
        conn.commit()
    finally:
        conn.close()


def save_historical_postmortem(document_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO historical_postmortems (document_id, payload_json, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                payload_json = excluded.payload_json,
                created_at = excluded.created_at
            """,
            (document_id, _dump(payload), _now()),
        )
        conn.execute(
            "UPDATE institutional_documents SET outcome_linked = 1, updated_at = ? WHERE document_id = ?",
            (_now(), document_id),
        )
        conn.commit()
        return get_historical_postmortem(document_id) or {}
    finally:
        conn.close()


def get_historical_postmortem(document_id: str) -> dict[str, Any] | None:
    init_db()
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM historical_postmortems WHERE document_id = ?", (document_id,)).fetchone()
        if not row:
            return None
        return {**dict(row), "payload": json.loads(row["payload_json"])}
    finally:
        conn.close()


def list_historical_postmortems(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM historical_postmortems ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]
    finally:
        conn.close()


def save_investment_committee_report(run_id: str, title: str, report: dict[str, Any], markdown: str) -> int:
    init_db()
    conn = connect()
    try:
        cursor = conn.execute(
            """
            INSERT INTO investment_committee_reports (run_id, title, report_json, markdown, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                title = excluded.title,
                report_json = excluded.report_json,
                markdown = excluded.markdown,
                created_at = excluded.created_at
            """,
            (run_id, title, _dump(report), markdown, _now()),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def list_investment_committee_reports(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM investment_committee_reports ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "report": json.loads(row["report_json"])} for row in rows]
    finally:
        conn.close()


def save_scenario_sequence(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = connect()
    now = _now()
    try:
        conn.execute(
            """
            INSERT INTO scenario_sequences (sequence_id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(sequence_id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                updated_at = excluded.updated_at
            """,
            (payload["sequence_id"], payload["name"], payload.get("description", ""), now, now),
        )
        conn.commit()
        return get_scenario_sequence(payload["sequence_id"]) or {}
    finally:
        conn.close()


def get_scenario_sequence(sequence_id: str) -> dict[str, Any] | None:
    init_db()
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM scenario_sequences WHERE sequence_id = ?", (sequence_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_scenario_sequences(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM scenario_sequences ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def save_scenario_phase(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = connect()
    now = _now()
    try:
        conn.execute(
            """
            INSERT INTO scenario_phases (
                phase_id, sequence_id, phase_number, scenario_json,
                data_snapshot_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(phase_id) DO UPDATE SET
                scenario_json = excluded.scenario_json,
                data_snapshot_json = excluded.data_snapshot_json,
                updated_at = excluded.updated_at
            """,
            (
                payload["phase_id"],
                payload["sequence_id"],
                payload["phase_number"],
                _dump(payload["scenario"]),
                _dump(payload.get("data_snapshot", {})),
                payload.get("created_at", now),
                now,
            ),
        )
        conn.commit()
        return get_scenario_phase(payload["phase_id"]) or {}
    finally:
        conn.close()


def get_scenario_phase(phase_id: str) -> dict[str, Any] | None:
    init_db()
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM scenario_phases WHERE phase_id = ?", (phase_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["scenario"] = json.loads(item.pop("scenario_json"))
        item["data_snapshot"] = json.loads(item.pop("data_snapshot_json"))
        return item
    finally:
        conn.close()


def list_scenario_phases(sequence_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        if sequence_id:
            rows = conn.execute(
                "SELECT * FROM scenario_phases WHERE sequence_id = ? ORDER BY phase_number LIMIT ?",
                (sequence_id, limit),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM scenario_phases ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        phases = []
        for row in rows:
            item = dict(row)
            item["scenario"] = json.loads(item.pop("scenario_json"))
            item["data_snapshot"] = json.loads(item.pop("data_snapshot_json"))
            phases.append(item)
        return phases
    finally:
        conn.close()


def save_scenario_analogs(phase_id: str, payload: dict[str, Any]) -> int:
    init_db()
    conn = connect()
    try:
        cursor = conn.execute(
            "INSERT INTO scenario_analogs (phase_id, payload_json, created_at) VALUES (?, ?, ?)",
            (phase_id, _dump(payload), _now()),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def list_scenario_analogs(phase_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        if phase_id:
            rows = conn.execute("SELECT * FROM scenario_analogs WHERE phase_id = ? ORDER BY id DESC LIMIT ?", (phase_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM scenario_analogs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]
    finally:
        conn.close()


def save_scenario_recommendation(payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO scenario_recommendations (
                recommendation_id, phase_id, sequence_id, recommendation_json,
                frozen_snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(recommendation_id) DO NOTHING
            """,
            (
                payload["recommendation_id"],
                payload["phase_id"],
                payload["sequence_id"],
                _dump(payload["recommendation"]),
                _dump(payload.get("frozen_snapshot", {})),
                payload.get("created_at", _now()),
            ),
        )
        conn.commit()
        return get_scenario_recommendation(payload["recommendation_id"]) or {}
    finally:
        conn.close()


def get_scenario_recommendation(recommendation_id: str) -> dict[str, Any] | None:
    init_db()
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM scenario_recommendations WHERE recommendation_id = ?", (recommendation_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["recommendation"] = json.loads(item.pop("recommendation_json"))
        item["frozen_snapshot"] = json.loads(item.pop("frozen_snapshot_json"))
        return item
    finally:
        conn.close()


def list_scenario_recommendations(phase_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        if phase_id:
            rows = conn.execute("SELECT * FROM scenario_recommendations WHERE phase_id = ? ORDER BY id DESC LIMIT ?", (phase_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM scenario_recommendations ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["recommendation"] = json.loads(item.pop("recommendation_json"))
            item["frozen_snapshot"] = json.loads(item.pop("frozen_snapshot_json"))
            results.append(item)
        return results
    finally:
        conn.close()


def save_scenario_evaluation(recommendation_id: str, horizon_months: int, payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO scenario_evaluations (recommendation_id, horizon_months, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(recommendation_id, horizon_months) DO UPDATE SET
                payload_json = excluded.payload_json,
                created_at = excluded.created_at
            """,
            (recommendation_id, horizon_months, _dump(payload), _now()),
        )
        conn.commit()
        return payload
    finally:
        conn.close()


def list_scenario_evaluations(limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM scenario_evaluations ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]
    finally:
        conn.close()


def save_scenario_postmortem(phase_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_db()
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO scenario_postmortems (phase_id, payload_json, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(phase_id) DO UPDATE SET
                payload_json = excluded.payload_json,
                created_at = excluded.created_at
            """,
            (phase_id, _dump(payload), _now()),
        )
        conn.commit()
        return payload
    finally:
        conn.close()


def list_scenario_postmortems(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM scenario_postmortems ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]
    finally:
        conn.close()
