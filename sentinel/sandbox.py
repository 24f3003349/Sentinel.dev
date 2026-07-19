"""Constrained Docker execution with a ten-second hard deadline and local fallback."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from sentinel.schemas import RunStatus, SandboxResult, TelemetrySample

IMAGE = "python:3.12-slim"
TIMEOUT_SECONDS = 10


def docker_available() -> bool:
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


def _local_run(target: Path, code: str) -> SandboxResult:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="sentinel-") as temp:
        arena = Path(temp)
        shutil.copy2(target / "domain.py", arena / "domain.py")
        attack = arena / "attack.py"
        attack.write_text(code, encoding="utf-8")
        try:
            local_env = {"PYTHONIOENCODING": "utf-8", "PATH": os.environ.get("PATH", "")}
            # asyncio on Windows requires these OS runtime variables; do not
            # forward arbitrary environment values such as API tokens.
            for variable in ("SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "PATHEXT", "TEMP", "TMP"):
                if value := os.environ.get(variable):
                    local_env[variable] = value
            completed = subprocess.run(
                [os.sys.executable, str(attack)],
                cwd=arena,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                env=local_env,
            )
            elapsed = time.monotonic() - started
            failure = "race-condition" if "INVARIANT_VIOLATION" in completed.stderr else None
            return SandboxResult(
                status=RunStatus.failed if completed.returncode else RunStatus.passed,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                telemetry=[TelemetrySample(elapsed_seconds=elapsed)],
                failure_kind=failure,
                runner="local-safe-fallback",
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - started
            return SandboxResult(
                status=RunStatus.timed_out,
                stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
                telemetry=[TelemetrySample(elapsed_seconds=elapsed)],
                failure_kind="denial-of-service/infinite-hang",
                runner="local-safe-fallback",
            )


def _docker_run(target: Path, code: str) -> SandboxResult:
    import docker

    # Bound every daemon API call too: telemetry must never bypass Sentinel's
    # ten-second execution deadline by blocking in Docker's stats endpoint.
    client = docker.from_env(timeout=2)
    with tempfile.TemporaryDirectory(prefix="sentinel-docker-") as temp:
        arena = Path(temp)
        shutil.copy2(target / "domain.py", arena / "domain.py")
        (arena / "attack.py").write_text(code, encoding="utf-8")
        # No bind mount: Docker Desktop file-sharing differs across macOS and
        # Windows. A throwaway image makes the arena portable and immutable.
        (arena / "Dockerfile").write_text(
            """FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir fastapi uvicorn requests aiohttp pytest
COPY domain.py attack.py /app/
USER 65532:65532
CMD [\"python\", \"attack.py\"]
""",
            encoding="utf-8",
        )
        image_tag = f"sentinel-arena:{uuid.uuid4().hex[:12]}"
        container = None
        samples: list[TelemetrySample] = []
        try:
            # python:3.12-slim is multi-architecture. The build context contains
            # only the two approved demo files and is never mounted at runtime.
            client.images.build(path=str(arena), tag=image_tag, rm=True, forcerm=True)
            # Build/setup time is not attack execution time. The hard deadline
            # begins only once the isolated process has actually started.
            started = time.monotonic()
            container = client.containers.run(
                image_tag,
                detach=True,
                network_disabled=True,
                read_only=True,
                mem_limit="256m",
                nano_cpus=1_000_000_000,
                pids_limit=64,
                security_opt=["no-new-privileges:true"],
            )
            while True:
                container.reload()
                if container.status in {"exited", "dead"}:
                    break
                elapsed = time.monotonic() - started
                if elapsed >= TIMEOUT_SECONDS:
                    container.kill()
                    logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                    return SandboxResult(
                        status=RunStatus.timed_out,
                        stdout=logs,
                        telemetry=samples,
                        failure_kind="denial-of-service/infinite-hang",
                        runner="docker",
                    )
                try:
                    stats = container.stats(stream=False)
                    usage = stats.get("memory_stats", {}).get("usage", 0)
                    cpu = 0.0
                    total = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
                    prior = stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
                    system = stats.get("cpu_stats", {}).get("system_cpu_usage", 0)
                    prior_system = stats.get("precpu_stats", {}).get("system_cpu_usage", 0)
                    online = stats.get("cpu_stats", {}).get("online_cpus", 1) or 1
                    if system > prior_system:
                        cpu = ((total - prior) / (system - prior_system)) * online * 100
                    samples.append(TelemetrySample(elapsed_seconds=elapsed, cpu_percent=cpu, memory_bytes=usage))
                except Exception:
                    pass
                time.sleep(0.2)
            result = container.wait(timeout=2)
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            code_value = result.get("StatusCode", 1)
            return SandboxResult(
                status=RunStatus.failed if code_value else RunStatus.passed,
                exit_code=code_value,
                stdout=logs,
                telemetry=samples,
                failure_kind="race-condition" if "INVARIANT_VIOLATION" in logs else None,
                runner="docker",
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            try:
                client.images.remove(image=image_tag, force=True)
            except Exception:
                pass


def run_attack(target: Path, code: str, prefer_docker: bool = True) -> SandboxResult:
    if prefer_docker and docker_available():
        try:
            return _docker_run(target, code)
        except Exception as exc:
            fallback = _local_run(target, code)
            fallback.stderr += f"\nDocker unavailable during run; used safe fallback: {exc}"
            return fallback
    return _local_run(target, code)
