"""Ephemeral, HTTP-level Docker arena for the approved Sentinel demo targets."""
from __future__ import annotations

import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Callable

from sentinel.schemas import RunStatus, SandboxResult, TelemetrySample

IMAGE_MEMORY_BYTES = 256 * 1024 * 1024
TIMEOUT_SECONDS = 10
MARKERS = {
    "RACE_INVARIANT_VIOLATION": "race-condition",
    "MEMORY_PRESSURE_VIOLATION": "memory-pressure",
    "REDOS_TIMEOUT_VIOLATION": "redos/cpu-exhaustion",
}


def docker_available() -> bool:
    try:
        import docker
        docker.from_env(timeout=2).ping()
        return True
    except Exception:
        return False


def _failure_from_logs(logs: str, samples: list[TelemetrySample], target_name: str = "") -> tuple[str | None, list[str]]:
    for marker, failure in MARKERS.items():
        if marker in logs:
            return failure, []
    violations: list[str] = []
    if any(sample.memory_bytes >= int(IMAGE_MEMORY_BYTES * 0.80) for sample in samples):
        violations.append("memory threshold exceeded (80% of 256 MiB arena)")
    # Docker's first CPU delta can be noisy; only the ReDoS scenario uses a
    # sustained CPU policy, and it needs two high samples to be credible.
    if target_name == "redos_attack" and sum(sample.cpu_percent >= 95 for sample in samples) >= 2:
        violations.append("sustained CPU threshold exceeded (95%)")
    return ("resource-exhaustion" if violations else None), violations


def _copy_context(target: Path, arena: Path, attack_code: str) -> None:
    ignored = shutil.ignore_patterns("__pycache__", ".pytest_cache", "graphify-out", "*.pyc")
    shutil.copytree(target, arena, dirs_exist_ok=True, ignore=ignored)
    (arena / "attack.py").write_text(attack_code, encoding="utf-8")
    (arena / "Dockerfile").write_text(
        """FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt requests aiohttp pytest
COPY . /app/
RUN useradd --uid 10001 --create-home sentinel
USER sentinel
CMD ["sh", "-c", "uvicorn main:app --host 127.0.0.1 --port 8000 & server=$!; trap 'kill $server 2>/dev/null; wait $server 2>/dev/null' EXIT; sleep 1; python attack.py"]
""",
        encoding="utf-8",
    )


def _sample(container, started: float) -> TelemetrySample | None:
    try:
        stats = container.stats(stream=False)
        cpu = stats.get("cpu_stats", {})
        previous = stats.get("precpu_stats", {})
        total = cpu.get("cpu_usage", {}).get("total_usage", 0)
        prior_total = previous.get("cpu_usage", {}).get("total_usage", 0)
        system = cpu.get("system_cpu_usage", 0)
        prior_system = previous.get("system_cpu_usage", 0)
        cores = cpu.get("online_cpus", 1) or 1
        percent = ((total - prior_total) / (system - prior_system)) * cores * 100 if system > prior_system else 0.0
        return TelemetrySample(elapsed_seconds=time.monotonic() - started, cpu_percent=percent, memory_bytes=stats.get("memory_stats", {}).get("usage", 0))
    except Exception:
        return None


def _python_syntax_error(source: str, filename: str) -> str | None:
    try:
        compile(source, filename, "exec")
    except SyntaxError as exc:
        return f"{filename}:{exc.lineno}:{exc.offset}: {exc.msg}"
    return None


def run_attack(target: Path, attack_code: str, expected_signal: str, require_signal: bool = True, prefer_docker: bool = True, progress: Callable[[str], None] | None = None) -> SandboxResult:
    notify = progress or (lambda _: None)
    syntax_error = _python_syntax_error(attack_code, "attack.py")
    if syntax_error:
        notify(f"rejected generated probe before Docker: {syntax_error}")
        return SandboxResult(status=RunStatus.failed, stderr=syntax_error, failure_kind="invalid-agent-probe", runner="validation")
    if not prefer_docker or not docker_available():
        notify("Docker Desktop is unavailable; arena was not started.")
        return SandboxResult(status=RunStatus.unavailable, stderr="Docker Desktop is required for the full HTTP sandbox.", failure_kind="docker-unavailable", runner="none")
    import docker

    target = target.resolve()
    client = docker.from_env(timeout=2)
    with tempfile.TemporaryDirectory(prefix="sentinel-arena-") as temp:
        arena = Path(temp)
        _copy_context(target, arena, attack_code)
        image = f"sentinel-arena:{uuid.uuid4().hex[:12]}"
        container = None
        samples: list[TelemetrySample] = []
        try:
            notify("staging isolated build context (no host volume mounts).")
            notify("building python:3.12-slim arena image; first build can take longer while packages download.")
            client.images.build(path=str(arena), tag=image, rm=True, forcerm=True)
            notify("image built; launching restricted HTTP arena (256 MiB / 1 CPU / 10 second hard limit).")
            started = time.monotonic()
            container = client.containers.run(image, detach=True, network_disabled=True, read_only=True, mem_limit="256m", nano_cpus=1_000_000_000, pids_limit=64, tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"}, security_opt=["no-new-privileges:true"])
            last_notice = 0
            while True:
                container.reload()
                if container.status in {"exited", "dead"}:
                    break
                if time.monotonic() - started >= TIMEOUT_SECONDS:
                    notify("hard timeout reached; killing the container and collecting telemetry.")
                    container.kill()
                    logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                    return SandboxResult(status=RunStatus.timed_out, stdout=logs, telemetry=samples, failure_kind="denial-of-service/infinite-hang", runner="docker")
                if sample := _sample(container, started):
                    samples.append(sample)
                elapsed = time.monotonic() - started
                if elapsed - last_notice >= 2:
                    notify(f"container running ({elapsed:.1f}s / {TIMEOUT_SECONDS}s hard limit; {len(samples)} telemetry samples).")
                    last_notice = elapsed
                time.sleep(0.20)
            result = container.wait(timeout=2)
            notify("container exited; collecting logs and evaluating the invariant.")
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            if any(marker in logs for marker in ("SyntaxError", "IndentationError", "Traceback (most recent call last)")):
                return SandboxResult(status=RunStatus.failed, exit_code=result.get("StatusCode", 1), stdout=logs, telemetry=samples, failure_kind="invalid-agent-probe", runner="docker")
            if require_signal and expected_signal not in logs:
                return SandboxResult(status=RunStatus.failed, exit_code=result.get("StatusCode", 1), stdout=logs, telemetry=samples, failure_kind="unverified-agent-probe", runner="docker")
            failure, policy = _failure_from_logs(logs, samples, target.name)
            code = result.get("StatusCode", 1)
            failed = bool(code) or bool(failure)
            return SandboxResult(status=RunStatus.failed if failed else RunStatus.passed, exit_code=code, stdout=logs, telemetry=samples, failure_kind=failure, policy_violations=policy, runner="docker")
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            try:
                client.images.remove(image=image, force=True)
            except Exception:
                pass
