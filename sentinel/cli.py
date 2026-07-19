from __future__ import annotations

import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sentinel.gitops import apply_patch_on_branch
from sentinel.graph_memory import build_graph
from sentinel.sandbox import docker_available, run_attack
from sentinel.schemas import RunStatus, SentinelReport
from sentinel.swarm_agents import decode_code, generate_chaos_plan, generate_patch

app = typer.Typer(help="Sentinel.dev - Graphify-guided chaos testing and verified remediation.", no_args_is_help=True)
console = Console()
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "dummy_targets" / "race_condition"
FOCUS = {"race_condition": "book", "memory_leak": "export", "redos_attack": "validate"}


def _report_path() -> Path:
    directory = ROOT / "reports"
    directory.mkdir(exist_ok=True)
    return directory / "latest.json"


def _execute(target: Path, defcon: int, patch: bool) -> SentinelReport:
    target = target.resolve()
    if not (target / "main.py").is_file() or not (target / "requirements.txt").is_file():
        raise typer.BadParameter("A Sentinel target must contain main.py and requirements.txt.")
    console.print(Panel.fit("[bold cyan]SENTINEL DEV[/] | Graphify-guided CI survivability check"))
    graph = build_graph(target, focus=FOCUS.get(target.name, ""))
    console.print(f"[cyan][MAP][/cyan] Graphify mapped {len(graph.nodes)} nodes and {len(graph.edges)} edges.")
    chaos = generate_chaos_plan(target, graph, defcon)
    console.print(f"[magenta][CHAOS][/magenta] {chaos.title}")
    result = run_attack(target, decode_code(chaos.attack_code_b64))
    color = "green" if result.status == RunStatus.passed else "red"
    console.print(f"[{color}][ARENA] {result.status.value.upper()}[/] via {result.runner}")
    if result.stdout.strip():
        console.print(Panel(result.stdout.strip(), title="Sandbox logs", border_style=color))
    if result.policy_violations:
        console.print(Panel("\n".join(result.policy_violations), title="Telemetry policy", border_style="red"))
    report = SentinelReport(run_id=str(uuid.uuid4()), target=str(target), graph=graph, chaos=chaos, sandbox=result, notes=["Graphify is mandatory; Docker executes a complete HTTP target without host volume mounts."])
    if result.status in {RunStatus.failed, RunStatus.timed_out} and patch:
        console.print("[bright_green][HEAL][/bright_green] creating a review branch and patch ...")
        remediation = generate_patch(target, graph, result)
        git_result = apply_patch_on_branch(ROOT, target, remediation)
        verification = run_attack(target, decode_code(chaos.attack_code_b64))
        report.patch, report.git, report.verification = remediation, git_result, verification
        if verification.status == RunStatus.passed:
            console.print(f"[bright_green]VERIFIED[/bright_green] {git_result.branch} ({git_result.commit[:8]}) survives the same probe.")
        else:
            console.print("[bold red]PATCH UNVERIFIED[/bold red] Review the branch; Sentinel will not claim remediation.")
    _report_path().write_text(report.model_dump_json(indent=2), encoding="utf-8")
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
    table.add_row("OpenAI", "[green]configured[/green]" if __import__("os").getenv("OPENAI_API_KEY") else "[yellow]target-specific deterministic mode[/yellow]")
    console.print(table)


def run_demo() -> int:
    try:
        report = _execute(DEFAULT_TARGET, defcon=5, patch=True)
        final = report.verification or report.sandbox
        return 0 if final.status == RunStatus.passed else 1
    except Exception as exc:
        console.print(f"[bold red]DEMO FAILED:[/] {exc}")
        return 1


def main() -> None:
    app()


if __name__ == "__main__":
    main()
