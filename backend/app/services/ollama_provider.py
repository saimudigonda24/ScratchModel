from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.services.env import load_env

load_env()

ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = ROOT / "prompts" / "scenario_parser_system_prompt.md"


@dataclass
class OllamaParseResult:
    ok: bool
    payload: dict[str, Any] | None
    model: str
    duration_ms: int
    error: str | None = None
    timings: dict[str, int] | None = None


class OllamaProvider:
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout_seconds: float | None = None, retries: int | None = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.model = model or os.getenv("OLLAMA_SCENARIO_MODEL") or "llama3.1:8b"
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else float(os.getenv("OLLAMA_SCENARIO_TIMEOUT_SECONDS", "6"))
        self.retries = retries if retries is not None else int(os.getenv("OLLAMA_SCENARIO_RETRIES", "0"))

    def health(self) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            payload = response.json()
            models = [item.get("name") for item in payload.get("models", [])]
            return {
                "reachable": True,
                "base_url": self.base_url,
                "selected_model": self.model,
                "model_available": self.model in models,
                "models": models,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "error": None,
            }
        except Exception as exc:
            return {
                "reachable": False,
                "base_url": self.base_url,
                "selected_model": self.model,
                "model_available": False,
                "models": [],
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "error": _safe_error(exc),
            }

    def parse_scenario(self, source_text: str) -> OllamaParseResult:
        started = time.perf_counter()
        request_started = time.perf_counter()
        prompt = f"{_system_prompt()}\n\nSOURCE TEXT:\n{source_text[:4000]}\n\nReturn JSON only."
        request_creation_ms = int((time.perf_counter() - request_started) * 1000)
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                inference_started = time.perf_counter()
                response = httpx.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {
                            "temperature": 0,
                            "num_ctx": int(os.getenv("OLLAMA_SCENARIO_NUM_CTX", "2048")),
                            "num_predict": int(os.getenv("OLLAMA_SCENARIO_NUM_PREDICT", "700")),
                            "num_thread": int(os.getenv("OLLAMA_SCENARIO_NUM_THREAD", "4")),
                        },
                    },
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                content = payload.get("response", "{}")
                inference_ms = int((time.perf_counter() - inference_started) * 1000)
                json_started = time.perf_counter()
                parsed = json.loads(content)
                json_validation_ms = int((time.perf_counter() - json_started) * 1000)
                return OllamaParseResult(
                    ok=True,
                    payload=parsed,
                    model=self.model,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    timings={
                        "request_creation_ms": request_creation_ms,
                        "ollama_inference_ms": inference_ms,
                        "json_decode_ms": json_validation_ms,
                    },
                )
            except Exception as exc:
                last_error = _safe_error(exc)
                if attempt < self.retries:
                    time.sleep(0.25 * (2**attempt))
        return OllamaParseResult(
            ok=False,
            payload=None,
            model=self.model,
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=last_error or "Ollama parse failed",
            timings={"request_creation_ms": request_creation_ms, "ollama_inference_ms": int((time.perf_counter() - started) * 1000)},
        )


def _system_prompt() -> str:
    return PROMPT_PATH.read_text()


def _safe_error(exc: Exception) -> str:
    return str(exc)[:240] or exc.__class__.__name__
