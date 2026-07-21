"""Structured OpenAI agents with deterministic, target-specific offline plans."""
from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
from pathlib import Path

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from sentinel.schemas import ChaosPlan, KnowledgeGraph, PatchPlan, ProbeSelection, SandboxResult

def _retryable(error: BaseException) -> bool:
    """Retry timeouts/rate limits/server errors, not bad credentials or retired models."""
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return status == 429 or status >= 500
    return type(error).__name__ in {"APITimeoutError", "APIConnectionError", "InternalServerError", "RateLimitError"}


_RETRY = dict(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception(_retryable), reraise=True)


def _progress(message: str) -> None:
    print(f"[LLM] {message}", flush=True)


def _before_retry(retry_state) -> None:
    wait = retry_state.next_action.sleep if retry_state.next_action else 0
    error = retry_state.outcome.exception() if retry_state.outcome else None
    _progress(f"attempt {retry_state.attempt_number} failed ({type(error).__name__ if error else 'unknown'}); retrying in {wait:.0f}s.")


_RETRY["before_sleep"] = _before_retry


def _require_live_ai() -> bool:
    return os.getenv("SENTINEL_REQUIRE_LIVE_AI", "").lower() in {"1", "true", "yes"}


def _force_deterministic() -> bool:
    return os.getenv("SENTINEL_DEMO_MODE", "").lower() == "deterministic"


def live_provider() -> str:
    provider = os.getenv("SENTINEL_LLM_PROVIDER", "openai").strip().lower()
    if provider not in {"openai", "openrouter", "google"}:
        raise RuntimeError("SENTINEL_LLM_PROVIDER must be 'openai', 'openrouter', or 'google'.")
    return provider


def live_model() -> str:
    configured = os.getenv("SENTINEL_LLM_MODEL") or os.getenv("SENTINEL_OPENAI_MODEL")
    if configured:
        return configured
    provider = live_provider()
    if provider == "openrouter":
        return "openai/gpt-5.6-sol"
    if provider == "google":
        return "gemini-3.5-flash"
    return "gpt-5.6-sol"


def live_api_key() -> str | None:
    provider = live_provider()
    if provider == "openrouter":
        return os.getenv("OPENROUTER_API_KEY")
    if provider == "google":
        return os.getenv("GEMINI_API_KEY")
    return os.getenv("OPENAI_API_KEY")


def live_generator_label() -> str:
    return f"{live_provider()}:{live_model()}"


def _client():
    from openai import OpenAI

    provider = live_provider()
    key = live_api_key()
    if not key:
        raise RuntimeError(f"{provider} API key is missing.")
    if provider == "openrouter":
        return OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": os.getenv("SENTINEL_APP_URL", "https://github.com/24f3003349/Sentinel.dev"),
                "X-OpenRouter-Title": "Sentinel.dev",
            },
            timeout=120.0,
            max_retries=0,
        )
    if provider == "google":
        return OpenAI(api_key=key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/", timeout=120.0, max_retries=0)
    return OpenAI(api_key=key, timeout=120.0, max_retries=0)


def _encode(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def decode_code(value: str) -> str:
    """Decode standard Base64, accepting omitted trailing padding from providers.

    Values containing non-Base64 characters still fail validation; they never
    reach the Docker arena as executable code.
    """
    compact = value.strip()
    if not compact or not re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", compact):
        raise ValueError("Code payload is not standard Base64.")
    padded = compact.rstrip("=") + ("=" * (-len(compact.rstrip("=")) % 4))
    try:
        return base64.b64decode(padded.encode("ascii"), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"Code payload is not valid UTF-8 Base64: {exc}") from exc


def _kind(target: Path) -> str:
    return target.resolve().name


def _context(target: Path, graph: KnowledgeGraph) -> str:
    source = (target / "main.py").read_text(encoding="utf-8")
    return f"Target directory: {target.name}\nTarget source:\n{source}\nGraph:\n{graph.model_dump_json()}"


def _parse_json_object(raw: str, schema: type[ChaosPlan] | type[PatchPlan] | type[ProbeSelection]):
    """Accept JSON-object responses even when a compatible provider adds code fences."""
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start, end = candidate.find("{"), candidate.rfind("}")
    if start < 0 or end < start:
        preview = candidate[:160].replace("\n", " ") or "<empty response>"
        raise RuntimeError(f"Model returned no JSON object. Response preview: {preview}")
    try:
        return schema.model_validate(json.loads(candidate[start : end + 1]))
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Model returned invalid JSON for {schema.__name__}: {exc}") from exc


def _compatible_json(system: str, user: str, schema: type[ChaosPlan] | type[PatchPlan] | type[ProbeSelection]):
    """Use provider-native structured output with a visible request heartbeat."""
    started = time.monotonic()
    done = threading.Event()

    def heartbeat() -> None:
        while not done.wait(5):
            _progress(f"waiting for {live_generator_label()} response ({time.monotonic() - started:.0f}s elapsed; request still active).")

    _progress(f"sending structured {schema.__name__} request to {live_generator_label()} (attempt may take up to 120s).")
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        messages = [
            {"role": "system", "content": f"{system} Reply with exactly one JSON object and nothing else."},
            {"role": "user", "content": user},
        ]
        if live_provider() == "google":
            # Google's compatibility docs explicitly support this Pydantic parse path.
            response = _client().beta.chat.completions.parse(
                model=live_model(), messages=messages, response_format=schema
            )
        else:
            request = {
                "model": live_model(), "messages": messages,
                "response_format": {"type": "json_object"}, "temperature": 0,
                "max_completion_tokens": 4096,
            }
            response = _client().chat.completions.create(**request)
    finally:
        done.set()
        thread.join(timeout=0.1)
    _progress(f"provider responded after {time.monotonic() - started:.1f}s; validating JSON contract.")
    if not response.choices:
        raise RuntimeError(f"{live_provider()} returned no completion choices.")
    choice = response.choices[0]
    if live_provider() == "google":
        parsed = choice.message.parsed
        if parsed is None:
            preview = (choice.message.content or "").replace("\n", " ")[:160] or "<empty response>"
            raise RuntimeError(f"Google returned no schema-valid {schema.__name__}. Response preview: {preview}")
        return parsed
    content = choice.message.content or ""
    if not content.strip():
        reasoning = getattr(choice.message, "reasoning", None)
        reasoning_hint = f", reasoning_chars={len(str(reasoning))}" if reasoning else ""
        raise RuntimeError(
            f"{live_provider()} returned an empty completion "
            f"(finish_reason={choice.finish_reason or 'unknown'}{reasoning_hint}). "
            "The model/provider produced no final JSON. Retry later or choose a different model."
        )
    return _parse_json_object(content, schema)


def deterministic_chaos_plan(target: Path, risk_level: int) -> ChaosPlan:
    kind = _kind(target)
    if kind == "race_condition":
        code, signal, title = '''import asyncio
import aiohttp

async def main() -> None:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        replies = await asyncio.gather(*[session.post("http://127.0.0.1:8000/book") for _ in range(50)], return_exceptions=True)
        successes = sum(1 for reply in replies if not isinstance(reply, Exception) and reply.status == 200)
        print(f"booking_successes={successes}")
        if successes > 1:
            raise SystemExit("RACE_INVARIANT_VIOLATION: more than one customer booked one ticket")

asyncio.run(main())
''', "RACE_INVARIANT_VIOLATION", "Concurrent SQLite booking probe"
    elif kind == "memory_leak":
        code, signal, title = '''import asyncio
import aiohttp

async def main() -> None:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6)) as session:
            response = await session.get("http://127.0.0.1:8000/export?size_mb=384")
            print(f"export_status={response.status}")
            if response.status != 200:
                raise SystemExit("MEMORY_PRESSURE_VIOLATION: export failed under constrained memory")
    except Exception as exc:
        raise SystemExit(f"MEMORY_PRESSURE_VIOLATION: {type(exc).__name__}")

asyncio.run(main())
''', "MEMORY_PRESSURE_VIOLATION", "Constrained-memory export probe"
    elif kind == "redos_attack":
        code, signal, title = '''import asyncio
import aiohttp

async def main() -> None:
    payload = {"text": "a" * 30 + "!"}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
            response = await session.post("http://127.0.0.1:8000/validate", json=payload)
            print(f"validation_status={response.status}")
    except Exception as exc:
        raise SystemExit(f"REDOS_TIMEOUT_VIOLATION: {type(exc).__name__}")

asyncio.run(main())
''', "REDOS_TIMEOUT_VIOLATION", "Catastrophic-regex timeout probe"
    else:
        raise ValueError(f"Unsupported Sentinel target: {target}")
    return ChaosPlan(title=title, rationale="A concurrent or constrained production-shaped request exposes a happy-path blind spot.", attack_code_b64=_encode(code), expected_signal=signal, risk_level=risk_level, generator="deterministic-demo")


@retry(**_RETRY)
def _openai_probe_selection(target: Path, graph: KnowledgeGraph, risk_level: int) -> ProbeSelection:
    system = "You are Sentinel's defensive chaos strategist. Inspect the Graphify graph and choose the one approved probe that best tests the supplied target. You do not write or return executable code. probe_id MUST exactly equal the target directory name. Explain the Graphify evidence for the selection concisely."
    user = _context(target, graph) + f"\nDEFCON: {risk_level}\nApproved probe IDs: {target.name}"
    if live_provider() in {"openrouter", "google"}:
        return _compatible_json(system, user, ProbeSelection)
    client = _client()
    response = client.responses.parse(model=live_model(), input=[{"role": "system", "content": system}, {"role": "user", "content": user}], text_format=ProbeSelection)
    if response.output_parsed is None:
        raise RuntimeError("No structured probe selection returned")
    return response.output_parsed


def generate_chaos_plan(target: Path, graph: KnowledgeGraph, risk_level: int) -> ChaosPlan:
    # Executable probes are a deliberately small, reviewed capability set.
    # Graphify chooses the target context; an LLM must never be a prerequisite
    # for producing syntactically valid code that enters the Docker arena.
    # The live model is used for evidence interpretation and remediation.
    if _force_deterministic():
        return deterministic_chaos_plan(target, risk_level)
    if not live_api_key():
        if _require_live_ai():
            raise RuntimeError(f"SENTINEL_REQUIRE_LIVE_AI is set but {live_provider()} API access is missing.")
        return deterministic_chaos_plan(target, risk_level).model_copy(update={"generator": "graphify-approved-probe"})
    selection = _openai_probe_selection(target, graph, risk_level)
    if selection.probe_id != target.name:
        raise RuntimeError(f"Model selected unsupported probe '{selection.probe_id}'; expected '{target.name}'.")
    approved = deterministic_chaos_plan(target, selection.risk_level)
    return approved.model_copy(update={"title": selection.title, "rationale": selection.rationale, "generator": live_generator_label()})


def _fixed_source(kind: str) -> str:
    if kind == "race_condition":
        return '''import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException

DB_FILE = Path(os.getenv("SENTINEL_DB_PATH", "/tmp/tickets.db"))


def init_db() -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY, stock INTEGER NOT NULL)")
        connection.execute("INSERT OR REPLACE INTO inventory (id, stock) VALUES (1, 1)")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sentinel race-condition target", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/book")
async def book_ticket() -> dict[str, int | str]:
    with sqlite3.connect(DB_FILE, timeout=1) as connection:
        cursor = connection.execute(
            "UPDATE inventory SET stock = stock - 1 WHERE id = 1 AND stock > 0"
        )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=400, detail="Sold out")
        remaining = connection.execute("SELECT stock FROM inventory WHERE id = 1").fetchone()[0]
        return {"status": "success", "remaining_stock": remaining}
'''
    if kind == "memory_leak":
        return '''from fastapi import FastAPI
from fastapi.responses import StreamingResponse
app = FastAPI(title="Sentinel memory-pressure target")
@app.get("/health")
async def health() -> dict[str, str]: return {"status": "ready"}
@app.get("/export")
async def export_data(size_mb: int = 1):
    async def stream():
        for _ in range(size_mb): yield b"x" * (1024 * 1024)
    return StreamingResponse(stream(), media_type="application/octet-stream")
'''
    return '''import re
from fastapi import FastAPI, HTTPException
app = FastAPI(title="Sentinel ReDoS target")
SAFE_INPUT = re.compile(r"^[A-Za-z0-9 ]+$")
@app.get("/health")
async def health() -> dict[str, str]: return {"status": "ready"}
@app.post("/validate")
async def validate_input(payload: dict[str, str]) -> dict[str, str]:
    if not SAFE_INPUT.fullmatch(payload.get("text", "")): raise HTTPException(status_code=400, detail="Invalid format")
    return {"status": "valid"}
'''


def deterministic_patch(target: Path) -> PatchPlan:
    kind = _kind(target)
    return PatchPlan(title=f"Remediate {kind.replace('_', ' ')}", rationale="Replace the unsafe operation with a bounded or atomic implementation.", patched_source_b64=_encode(_fixed_source(kind)), verification_note="Sentinel reruns the same Docker chaos probe after this commit.", generator="deterministic-demo")


def _validate_patch(plan: PatchPlan) -> None:
    try:
        source = decode_code(plan.patched_source_b64)
        compile(source, "main.py", "exec")
    except Exception as exc:
        raise ValueError(f"Generated main.py is not valid Python: {exc}") from exc


@retry(**_RETRY)
def _openai_patch(target: Path, graph: KnowledgeGraph, result: SandboxResult) -> PatchPlan:
    system = "You are a defensive remediation agent. Return a complete safe replacement for main.py only, base64-encoded in patched_source_b64. Preserve the target API and address the observed telemetry/failure. Before returning, ensure decoded patched_source_b64 compiles with Python compile(source, 'main.py', 'exec'). Do not use Markdown, backticks, pseudocode, or incomplete blocks."
    user = _context(target, graph) + f"\nSandbox result:\n{result.model_dump_json()}"
    if live_provider() in {"openrouter", "google"}:
        plan = _compatible_json(system, user, PatchPlan)
        if plan.file_path != "main.py":
            raise RuntimeError(f"{live_provider()} remediation attempted to modify a file other than main.py.")
        return plan.model_copy(update={"generator": live_generator_label()})
    client = _client()
    response = client.responses.parse(model=live_model(), input=[{"role": "system", "content": system}, {"role": "user", "content": user}], text_format=PatchPlan)
    if response.output_parsed is None or response.output_parsed.file_path != "main.py":
        raise RuntimeError("Unsafe or missing patch response")
    return response.output_parsed.model_copy(update={"generator": live_generator_label()})


@retry(**_RETRY)
def repair_invalid_patch(target: Path, graph: KnowledgeGraph, result: SandboxResult, invalid: PatchPlan, error: ValueError) -> PatchPlan:
    system = "You are repairing a rejected FastAPI patch. Return a complete safe replacement for main.py only, base64-encoded in patched_source_b64. It MUST compile and it MUST start successfully with the target's existing pytest happy-path suite. The reported rejection may be a runtime error such as invalid SQL, not only a Python syntax error. Do not use Markdown or backticks. Preserve the FastAPI /book and /health API and fix the observed race."
    try:
        invalid_source = decode_code(invalid.patched_source_b64)
    except ValueError:
        invalid_source = "<unavailable: patched_source_b64 was malformed; do not repeat it>"
    user = _context(target, graph) + f"\nSandbox result:\n{result.model_dump_json()}\nInvalid candidate source:\n{invalid_source}\nCompiler error: {error}"
    if live_provider() in {"openrouter", "google"}:
        return _compatible_json(system, user, PatchPlan).model_copy(update={"generator": live_generator_label()})
    client = _client()
    response = client.responses.parse(model=live_model(), input=[{"role": "system", "content": system}, {"role": "user", "content": user}], text_format=PatchPlan)
    if response.output_parsed is None:
        raise RuntimeError("No corrected patch returned")
    return response.output_parsed.model_copy(update={"generator": live_generator_label()})


def generate_patch(target: Path, graph: KnowledgeGraph, result: SandboxResult) -> PatchPlan:
    if _force_deterministic():
        return deterministic_patch(target)
    if not live_api_key():
        if _require_live_ai():
            raise RuntimeError(f"SENTINEL_REQUIRE_LIVE_AI is set but {live_provider()} API access is missing.")
        return deterministic_patch(target)
    try:
        plan = _openai_patch(target, graph, result)
        try:
            _validate_patch(plan)
        except ValueError as error:
            _progress("generated patch failed Python validation; requesting one live compiler-guided correction.")
            plan = repair_invalid_patch(target, graph, result, plan, error)
            _validate_patch(plan)
        return plan
    except Exception:
        if _require_live_ai():
            raise
        return deterministic_patch(target).model_copy(update={"generator": "deterministic-fallback-after-openai-error"})
