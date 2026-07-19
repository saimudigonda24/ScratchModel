import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter

from app.services.database import (
    get_scheduled_job,
    list_scheduled_job_runs,
    list_scheduled_jobs,
    record_scheduled_job_run,
    update_scheduled_job_state,
    upsert_scheduled_job,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = ROOT / "config" / "scheduler.yaml"


@dataclass
class ScheduledJob:
    name: str
    cadence: str
    enabled: bool
    target: str
    command: str
    max_retries: int = 2


def load_scheduler_config(path: Path = DEFAULT_CONFIG) -> list[ScheduledJob]:
    jobs: list[ScheduledJob] = []
    current: dict[str, str] | None = None
    for raw_line in path.read_text().splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped == "jobs:":
            continue
        if stripped.startswith("- "):
            if current:
                jobs.append(_job_from_dict(current))
            current = {}
            stripped = stripped[2:]
        if ":" in stripped and current is not None:
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip()
    if current:
        jobs.append(_job_from_dict(current))
    return jobs


def _job_from_dict(payload: dict[str, str]) -> ScheduledJob:
    return ScheduledJob(
        name=payload["name"],
        cadence=payload["cadence"],
        enabled=payload.get("enabled", "false").lower() == "true",
        target=payload.get("target", ""),
        command=payload.get("command", ""),
        max_retries=int(payload.get("max_retries", 2)),
    )


class LightweightScheduler:
    def __init__(self, config_path: Path = DEFAULT_CONFIG):
        self.config_path = config_path
        self.jobs = load_scheduler_config(config_path)
        self.sync_config_to_db()

    def sync_config_to_db(self) -> None:
        for job in self.jobs:
            upsert_scheduled_job(
                {
                    "job_name": job.name,
                    "cadence": job.cadence,
                    "enabled": job.enabled,
                    "target": job.target,
                    "command": job.command,
                    "max_retries": job.max_retries,
                    "next_run_time": datetime.utcnow().isoformat(),
                }
            )

    def enabled_jobs(self) -> list[ScheduledJob]:
        job_state = {row["job_name"]: row for row in list_scheduled_jobs()}
        enabled = []
        for job in self.jobs:
            state = job_state.get(job.name)
            if job.enabled and (state is None or state.get("enabled")):
                enabled.append(job)
        return enabled

    def run_once(self, dry_run: bool = False) -> list[dict]:
        results: list[dict] = []
        for job in self.enabled_jobs():
            state = get_scheduled_job(job.name) or {}
            if not dry_run and not self._is_due(state):
                continue
            results.append(self.run_job(job.name, dry_run=dry_run))
        return results

    def run_job(self, job_name: str, dry_run: bool = False) -> dict:
        job = next((item for item in self.jobs if item.name == job_name), None)
        if job is None:
            raise ValueError(f"Unknown scheduled job: {job_name}")
        started_dt = datetime.utcnow()
        started = started_dt.isoformat()
        tick = perf_counter()
        if dry_run:
            finished = datetime.utcnow().isoformat()
            result = {"job_name": job.name, "status": "dry_run", "message": job.command}
            record_scheduled_job_run(job.name, "dry_run", started, finished, job.command, job.command)
            update_scheduled_job_state(
                job.name,
                {
                    "next_run_time": self._next_run_time(job.cadence, started_dt).isoformat(),
                    "last_duration_seconds": 0.0,
                },
            )
            return result
        attempts = 0
        max_attempts = max(1, job.max_retries + 1)
        last_message = ""
        status = "failed"
        while attempts < max_attempts:
            attempts += 1
            completed = subprocess.run(job.command.split(), cwd=ROOT, capture_output=True, text=True, timeout=300)
            last_message = completed.stdout or completed.stderr
            if completed.returncode == 0:
                status = "success"
                break
        finished_dt = datetime.utcnow()
        duration = perf_counter() - tick
        finished = finished_dt.isoformat()
        record_scheduled_job_run(job.name, status, started, finished, last_message, job.command)
        if status == "success":
            update_scheduled_job_state(
                job.name,
                {
                    "retry_count": 0,
                    "next_run_time": self._next_run_time(job.cadence, finished_dt).isoformat(),
                    "last_success_time": finished,
                    "last_error_message": "",
                    "last_duration_seconds": duration,
                },
            )
        else:
            update_scheduled_job_state(
                job.name,
                {
                    "retry_count": attempts - 1,
                    "next_run_time": self._next_run_time("hourly", finished_dt).isoformat(),
                    "last_failure_time": finished,
                    "last_error_message": last_message[-2000:],
                    "last_duration_seconds": duration,
                },
            )
        return {"job_name": job.name, "status": status, "message": last_message, "attempts": attempts}

    def set_job_enabled(self, job_name: str, enabled: bool) -> dict:
        if not get_scheduled_job(job_name):
            raise ValueError(f"Unknown scheduled job: {job_name}")
        return update_scheduled_job_state(job_name, {"enabled": int(enabled)})

    def _is_due(self, state: dict) -> bool:
        raw = state.get("next_run_time")
        if not raw:
            return True
        try:
            return datetime.fromisoformat(raw) <= datetime.utcnow()
        except ValueError:
            return True

    def _next_run_time(self, cadence: str, from_time: datetime) -> datetime:
        cadence = cadence.lower()
        if cadence == "daily":
            return from_time + timedelta(days=1)
        if cadence == "weekly":
            return from_time + timedelta(days=7)
        if cadence == "monthly":
            return from_time + timedelta(days=30)
        if cadence in {"horizon_based", "hourly"}:
            return from_time + timedelta(hours=1)
        return from_time + timedelta(days=1)

    def status_summary(self) -> dict:
        runs = list_scheduled_job_runs(100)
        states = list_scheduled_jobs()
        latest_by_job = {}
        failed = []
        for run in runs:
            latest_by_job.setdefault(run["job_name"], run)
            if run["status"] == "failed":
                failed.append(run)
        return {
            "configured_jobs": [job.__dict__ for job in self.jobs],
            "durable_jobs": states,
            "latest_by_job": list(latest_by_job.values()),
            "failed_jobs": failed,
        }
