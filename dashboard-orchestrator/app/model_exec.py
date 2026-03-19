from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass

import httpx


class ModelExecutionError(RuntimeError):
    pass


@dataclass
class ExecutionResult:
    output: str
    latency_ms: int
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_estimate: float | None = None
    error: str | None = None


def estimate_tokens(text: str) -> int:
    text = text or ""
    return max(1, len(text) // 4) if text else 0


def estimate_cost(provider: str, model: str, tokens_in: int | None, tokens_out: int | None) -> float | None:
    if tokens_in is None and tokens_out is None:
        return None
    tin = tokens_in or 0
    tout = tokens_out or 0
    total = tin + tout
    rates = {
        "openai/gpt-4o": 0.00001,
        "openai/gpt-4o-mini": 0.000003,
        "gemini/gemini-2.5-pro": 0.000008,
        "gemini/gemini-2.5-flash": 0.000002,
    }
    rate = rates.get(model) or rates.get(f"{provider}/{model}") or 0.000005
    return round(total * rate, 6)


def execute_model(provider: str, model: str, input_text: str, timeout_seconds: int = 90) -> ExecutionResult:
    provider = provider.lower().strip()
    if provider == "gemini":
        return _execute_gemini(model, input_text, timeout_seconds)
    if provider == "openai":
        return _execute_openai(model, input_text, timeout_seconds)
    raise ModelExecutionError(f"Unsupported provider: {provider}")


def _execute_gemini(model: str, input_text: str, timeout_seconds: int) -> ExecutionResult:
    cli = shutil.which("gemini")
    started = time.perf_counter()
    if cli:
        try:
            proc = subprocess.run(
                [cli, "--model", model, "-p", input_text],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            stdout = (proc.stdout or "").strip()
            stderr = (proc.stderr or "").strip()
            if proc.returncode != 0:
                raise ModelExecutionError(stderr or stdout or f"gemini exited with code {proc.returncode}")
            output = stdout or stderr or ""
            tokens_in = estimate_tokens(input_text)
            tokens_out = estimate_tokens(output)
            return ExecutionResult(
                output=output,
                latency_ms=latency_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_estimate=estimate_cost("gemini", model, tokens_in, tokens_out),
            )
        except subprocess.TimeoutExpired as exc:
            raise ModelExecutionError(f"gemini timeout after {timeout_seconds}s") from exc
    return _mock_result("gemini", model, input_text, started, reason="gemini CLI unavailable")


def _execute_openai(model: str, input_text: str, timeout_seconds: int) -> ExecutionResult:
    api_key = os.getenv("OPENAI_API_KEY")
    started = time.perf_counter()
    if not api_key:
        return _mock_result("openai", model, input_text, started, reason="OPENAI_API_KEY unavailable")
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model.split("/", 1)[-1],
                    "messages": [{"role": "user", "content": input_text}],
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            data = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        output = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens")
        tokens_out = usage.get("completion_tokens")
        return ExecutionResult(
            output=output,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_estimate=estimate_cost("openai", model, tokens_in, tokens_out),
        )
    except httpx.TimeoutException as exc:
        raise ModelExecutionError(f"openai timeout after {timeout_seconds}s") from exc
    except httpx.HTTPError as exc:
        raise ModelExecutionError(f"openai http error: {exc}") from exc


def _mock_result(provider: str, model: str, input_text: str, started: float, reason: str) -> ExecutionResult:
    output = (
        f"[MOCK {provider}/{model}]\n"
        f"Reason: {reason}\n\n"
        f"Input:\n{input_text}\n\n"
        f"Structured mock response generated because live provider execution is unavailable in this environment."
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    tokens_in = estimate_tokens(input_text)
    tokens_out = estimate_tokens(output)
    return ExecutionResult(
        output=output,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_estimate=estimate_cost(provider, model, tokens_in, tokens_out),
    )
