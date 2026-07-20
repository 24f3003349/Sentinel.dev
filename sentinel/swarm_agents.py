"""Structured OpenAI agents with deterministic, target-specific offline plans."""
from __future__ import annotations

import base64
import os
from pathlib import Path

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sentinel.schemas import ChaosPlan, KnowledgeGraph, PatchPlan, SandboxResult

_RETRY = dict(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception), reraise=True)


def _require_live_ai() -> bool:
    return os.getenv("SENTINEL_REQUIRE_LIVE_AI", "").lower() in {"1", "true", "yes"}


def live_provider() -> str:
    provider = os.getenv("SENTINEL_LLM_PROVIDER", "openai").strip().lower()
    if provider not in {"openai", "openrouter"}:
        raise RuntimeError("SENTINEL_LLM_PROVIDER must be 'openai' or 'openrouter'.")
    return provider


def live_model() -> str:
    configured = os.getenv("SENTINEL_LLM_MODEL") or os.getenv("SENTINEL_OPENAI_MODEL")
    if configured:
        return configured
    return "openai/gpt-5.6-sol" if live_provider() == "openrouter" else "gpt-5.6-sol"


def live_api_key() -> str | None:
    return os.getenv("OPENROUTER_API_KEY") if live_provider() == "openrouter" else os.getenv("OPENAI_API_KEY")


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
    return OpenAI(api_key=key, timeout=120.0, max_retries=0)


def _encode(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def decode_code(value: str) -> str:
    return base64.b64decode(value.encode("ascii"), validate=True).decode("utf-8")


def _kind(target: Path) -> str:
    return target.resolve().name


def _context(target: Path, graph: KnowledgeGraph) -> str:
    source = (target / "main.py").read_text(encoding="utf-8")
    return f"Target directory: {target.name}\nTarget source:\n{source}\nGraph:\n{graph.model_dump_json()}"


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
def _openai_chaos(target: Path, graph: KnowledgeGraph, risk_level: int) -> ChaosPlan:
    client = _client()
    response = client.responses.parse(model=live_model(), input=[{"role": "system", "content": "You are Sentinel's defensive chaos engineer. Generate a localhost-only Python HTTP probe for the supplied FastAPI target. No filesystem writes, subprocesses, external network, or secret access. Return executable code only as base64 in attack_code_b64."}, {"role": "user", "content": _context(target, graph) + f"\nDEFCON: {risk_level}"}], text_format=ChaosPlan)
    if response.output_parsed is None:
        raise RuntimeError("No structured chaos plan returned")
    return response.output_parsed.model_copy(update={"generator": live_generator_label()})


def generate_chaos_plan(target: Path, graph: KnowledgeGraph, risk_level: int) -> ChaosPlan:
    if not live_api_key():
        if _require_live_ai():
            raise RuntimeError(f"SENTINEL_REQUIRE_LIVE_AI is set but {live_provider()} API access is missing.")
        return deterministic_chaos_plan(target, risk_level)
    try:
        return _openai_chaos(target, graph, risk_level)
    except Exception:
        if _require_live_ai():
            raise
        return deterministic_chaos_plan(target, risk_level).model_copy(update={"generator": "deterministic-fallback-after-openai-error"})


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


@retry(**_RETRY)
def _openai_patch(target: Path, graph: KnowledgeGraph, result: SandboxResult) -> PatchPlan:
    client = _client()
    response = client.responses.parse(model=live_model(), input=[{"role": "system", "content": "You are a defensive remediation agent. Return a complete safe replacement for main.py only, base64-encoded in patched_source_b64. Preserve the target API and address the observed telemetry/failure."}, {"role": "user", "content": _context(target, graph) + f"\nSandbox result:\n{result.model_dump_json()}"}], text_format=PatchPlan)
    if response.output_parsed is None or response.output_parsed.file_path != "main.py":
        raise RuntimeError("Unsafe or missing patch response")
    return response.output_parsed.model_copy(update={"generator": live_generator_label()})


def generate_patch(target: Path, graph: KnowledgeGraph, result: SandboxResult) -> PatchPlan:
    if not live_api_key():
        if _require_live_ai():
            raise RuntimeError(f"SENTINEL_REQUIRE_LIVE_AI is set but {live_provider()} API access is missing.")
        return deterministic_patch(target)
    try:
        return _openai_patch(target, graph, result)
    except Exception:
        if _require_live_ai():
            raise
        return deterministic_patch(target).model_copy(update={"generator": "deterministic-fallback-after-openai-error"})
