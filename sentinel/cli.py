from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sentinel.gitops import apply_patch_on_branch
from sentinel.graph_memory import build_graph
from sentinel.sandbox import docker_available, run_attack
from sentinel.schemas import RunStatus, SentinelReport
from sentinel.swarm_agents import decode_code, generate_chaos_plan, generate_patch, live_api_key, live_generator_label, live_provider, repair_invalid_patch

app = typer.Typer(help="Sentinel.dev - Graphify-guided chaos testing and verified remediation.", no_args_is_help=True)
console = Console()
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "dummy_targets" / "race_condition"
FOCUS = {"race_condition": "book", "memory_leak": "export", "redos_attack": "validate"}


def _report_path(target_name: str | None = None) -> Path:
    directory = ROOT / "reports"
    directory.mkdir(exist_ok=True)
    return directory / (f"{target_name}.json" if target_name else "latest.json")


def _patch_preflight_error(target: Path, source: str, attack_code: str, expected_signal: str) -> ValueError | None:
    """Reject patches that compile but cannot start the target's real test suite.

    This runs in a disposable copy before any Git branch or commit is made.
    It catches startup failures *and* verifies the candidate against the exact
    Docker probe that produced the finding.  A Python compile check alone is
    not meaningful for SQL semantics.
    """
    try:
        compile(source, "main.py", "exec")
    except SyntaxError as exc:
        return ValueError(f"Python compilation failed at main.py:{exc.lineno}:{exc.offset}: {exc.msg}")
    with tempfile.TemporaryDirectory(prefix="sentinel-patch-preflight-") as temporary:
        candidate = Path(temporary) / target.name
        shutil.copytree(target, candidate, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.db"))
        (candidate / "main.py").write_text(source, encoding="utf-8")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(candidate) + os.pathsep + environment.get("PYTHONPATH", "")
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "test_main.py", "-q"],
            cwd=candidate,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if completed.returncode != 0:
            detail = (completed.stdout + "\n" + completed.stderr).strip()
            return ValueError(f"Clean-room happy-path preflight failed:\n{detail[-3000:]}")
        probe = run_attack(candidate, attack_code, expected_signal, require_signal=False)
    if probe.status != RunStatus.passed:
        detail = (probe.stdout + "\n" + probe.stderr).strip()
        return ValueError(
            "Clean-room Docker invariant preflight failed; the original failure still exists "
            f"({probe.failure_kind or probe.status.value}).\n{detail[-3000:]}"
        )
    return None


def _execute(target: Path, defcon: int, patch: bool) -> SentinelReport:
    target = target.resolve()
    if not (target / "main.py").is_file() or not (target / "requirements.txt").is_file():
        raise typer.BadParameter("A Sentinel target must contain main.py and requirements.txt.")
    console.print(Panel.fit("[bold cyan]SENTINEL DEV[/] | Graphify-guided CI survivability check"))
    console.print("[cyan][MAP][/cyan] phase 0/4: constructing the local Graphify knowledge graph ...")
    graph = build_graph(target, focus=FOCUS.get(target.name, ""), progress=lambda message: console.print(f"[dim][MAP][/dim] {message}"))
    console.print(f"[cyan][MAP][/cyan] Graphify mapped {len(graph.nodes)} nodes and {len(graph.edges)} edges.")
    console.print("[cyan][PROBE][/cyan] phase 1/4: Graphify selected the reviewed, target-bounded Docker probe ...")
    chaos = generate_chaos_plan(target, graph, defcon)
    console.print(f"[magenta][CHAOS][/magenta] {chaos.title}")
    console.print(f"[dim][PROBE][/dim] execution plan: {chaos.generator}")
    console.print("[cyan][ARENA][/cyan] phase 2/4: preparing the isolated Docker arena ...")
    result = run_attack(target, decode_code(chaos.attack_code_b64), chaos.expected_signal, progress=lambda message: console.print(f"[dim][ARENA][/dim] {message}"))
    color = "green" if result.status == RunStatus.passed else "red"
    console.print(f"[{color}][ARENA] {result.status.value.upper()}[/] via {result.runner}")
    if result.stdout.strip():
        console.print(Panel(result.stdout.strip(), title="Sandbox logs", border_style=color))
    if result.policy_violations:
        console.print(Panel("\n".join(result.policy_violations), title="Telemetry policy", border_style="red"))
    report = SentinelReport(run_id=str(uuid.uuid4()), target=str(target), graph=graph, chaos=chaos, sandbox=result, notes=["Graphify is mandatory; Docker executes a complete HTTP target without host volume mounts."])
    if result.failure_kind in {"invalid-agent-probe", "unverified-agent-probe"}:
        console.print("[bold red]AGENT PROBE REJECTED[/bold red] No patch branch was created because the generated probe did not prove the expected invariant.")
    elif result.status in {RunStatus.failed, RunStatus.timed_out} and patch:
        console.print("[bright_green][HEAL][/bright_green] creating a review branch and patch ...")
        console.print(f"[cyan][MODEL][/cyan] phase 3/4: {live_generator_label() if live_api_key() else 'deterministic fixtures'} is selecting a remediation from Graphify + Docker evidence ...")
        remediation = generate_patch(target, graph, result)
        console.print(f"[dim][AGENT][/dim] remediation: {remediation.generator}")
        patched_source = decode_code(remediation.patched_source_b64)
        attack_code = decode_code(chaos.attack_code_b64)
        preflight_error = _patch_preflight_error(target, patched_source, attack_code, chaos.expected_signal)
        if preflight_error and remediation.generator != "deterministic-demo":
            console.print("[yellow][HEAL][/yellow] candidate failed clean-room startup/test preflight; requesting one evidence-guided correction ...")
            remediation = repair_invalid_patch(target, graph, result, remediation, preflight_error)
            patched_source = decode_code(remediation.patched_source_b64)
            preflight_error = _patch_preflight_error(target, patched_source, attack_code, chaos.expected_signal)
        if preflight_error:
            console.print(Text(f"AGENT PATCH REJECTED {preflight_error}", style="bold red"))
            report.patch = remediation
            serialized = report.model_dump_json(indent=2)
            _report_path().write_text(serialized, encoding="utf-8")
            _report_path(target.name).write_text(serialized, encoding="utf-8")
            return report
        git_result = apply_patch_on_branch(ROOT, target, remediation)
        console.print(Panel(git_result.diff, title="Applied remediation diff", border_style="cyan"))
        console.print("[cyan][ARENA][/cyan] phase 4/4: rerunning the identical probe against the patched branch ...")
        verification = run_attack(target, decode_code(chaos.attack_code_b64), chaos.expected_signal, require_signal=False, progress=lambda message: console.print(f"[dim][ARENA][/dim] {message}"))
        report.patch, report.git, report.verification = remediation, git_result, verification
        if verification.status == RunStatus.passed:
            console.print(f"[bright_green]VERIFIED[/bright_green] {git_result.branch} ({git_result.commit[:8]}) survives the same probe.")
        else:
            console.print("[bold red]PATCH UNVERIFIED[/bold red] Review the branch; Sentinel will not claim remediation.")
    serialized = report.model_dump_json(indent=2)
    _report_path().write_text(serialized, encoding="utf-8")
    _report_path(target.name).write_text(serialized, encoding="utf-8")
    return report


@app.command()
def analyze(target: Path = typer.Argument(DEFAULT_TARGET)) -> None:
    """Build and print the required Graphify knowledge graph."""
    console.print_json(build_graph(target, focus=FOCUS.get(target.name, "")).model_dump_json(indent=2))


@app.command()
def attack(target: Path = typer.Argument(DEFAULT_TARGET), defcon: int = typer.Option(5, min=1, max=5), no_patch: bool = typer.Option(False, help="Detection-only mode; appropriate for CI.")) -> None:
    """Run a target's HTTP chaos probe. Detection-only failures exit 1 for CI."""
    report = _execute(target, defcon, patch=not no_patch)
    final = report.verification or report.sandbox
    if final.status != RunStatus.passed:
        raise typer.Exit(code=1)


@app.command()
def doctor() -> None:
    """Display required local capabilities."""
    table = Table(title="Sentinel environment")
    table.add_column("Integration")
    table.add_column("Status")
    table.add_row("Docker Desktop", "[green]available[/green]" if docker_available() else "[red]required for HTTP arena[/red]")
    try:
        __import__("graphify")
        graphify = "[green]installed (required)[/green]"
    except ModuleNotFoundError:
        graphify = "[red]missing[/red]"
    table.add_row("Graphify", graphify)
    table.add_row("LLM", f"[green]configured ({live_generator_label()})[/green]" if live_api_key() else "[yellow]not configured[/yellow]")
    console.print(table)


def _run_happy_path_tests(target: Path) -> bool:
    """Prove the seeded service passes ordinary local tests before chaos starts."""
    console.print("[cyan][LOCAL TESTS][/cyan] running the target happy-path suite ...")
    completed = subprocess.run([sys.executable, "-m", "pytest", str(target / "test_main.py"), "-q"], cwd=ROOT, capture_output=True, text=True, check=False)
    if completed.returncode == 0:
        summary = (completed.stdout or "passed").strip().splitlines()[-1]
        console.print(f"[green][LOCAL TESTS] PASS[/green] {summary}")
        return True
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    console.print(Panel(output or "pytest failed without output", title="Local tests failed", border_style="red"))
    return False


def run_demo(mode: str = "live") -> int:
    try:
        if mode not in {"live", "deterministic"}:
            console.print("[bold red]Invalid demo mode.[/] Choose live or deterministic.")
            return 2
        os.environ["SENTINEL_DEMO_MODE"] = mode
        if mode == "deterministic":
            os.environ.pop("SENTINEL_REQUIRE_LIVE_AI", None)
            console.print("[yellow][DEMO MODE] DETERMINISTIC[/yellow] No model call; this is a local rehearsal.")
        else:
            os.environ["SENTINEL_REQUIRE_LIVE_AI"] = "1"
            console.print(f"[bright_cyan][DEMO MODE] LIVE[/bright_cyan] GPT agent: {live_generator_label()}")
        if mode == "live" and not live_api_key():
            key_name = {"openrouter": "OPENROUTER_API_KEY", "google": "GEMINI_API_KEY"}.get(live_provider(), "OPENAI_API_KEY")
            console.print(f"[bold red]LIVE AGENT REQUIRED:[/] Set {key_name}. Sentinel will not substitute the deterministic demo path.")
            return 2
        if not _run_happy_path_tests(DEFAULT_TARGET):
            return 1
        report = _execute(DEFAULT_TARGET, defcon=5, patch=True)
        final = report.verification or report.sandbox
        return 0 if final.status == RunStatus.passed else 1
    except Exception as exc:
        console.print(Text(f"DEMO FAILED: {exc}", style="bold red"))
        return 1


def main() -> None:
    app()


if __name__ == "__main__":
    main()
