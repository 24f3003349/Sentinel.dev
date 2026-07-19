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

app = typer.Typer(help="Sentinel.dev - scoped chaos testing with guarded remediation.", no_args_is_help=True)
console = Console()
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = ROOT / "dummy_target"


def _report_path() -> Path:
    directory = ROOT / "reports"
    directory.mkdir(exist_ok=True)
    return directory / "latest.json"


def _execute(target: Path, risk_level: int, prefer_docker: bool, patch: bool) -> SentinelReport:
    target = target.resolve()
    console.print(Panel.fit("[bold cyan]SENTINEL DEV[/]  |  adversarial CI survivability check"))
    console.print("[cyan][MAP][/cyan] building focused dependency graph ...")
    graph = build_graph(target)
    console.print(f"[green]OK[/green] {len(graph.nodes)} nodes, {len(graph.edges)} edges, provider: Graphify")
    console.print("[magenta][CHAOS][/magenta] synthesizing bounded concurrent invariant probe ...")
    chaos = generate_chaos_plan(graph, risk_level)
    console.print(f"[green]OK[/green] {chaos.title}")
    console.print("[yellow][ARENA][/yellow] executing with 10-second hard timeout ...")
    result = run_attack(target, decode_code(chaos.attack_code_b64), prefer_docker=prefer_docker)
    status_color = "green" if result.status == RunStatus.passed else "red"
    console.print(f"[{status_color}]{result.status.value.upper()}[/] via {result.runner}")
    if result.stdout.strip():
        console.print(Panel(result.stdout.strip(), title="Sandbox stdout", border_style=status_color))
    if result.stderr.strip():
        console.print(Panel(result.stderr.strip(), title="Sandbox stderr", border_style=status_color))
    report = SentinelReport(
        run_id=str(uuid.uuid4()), target=str(target), graph=graph, chaos=chaos, sandbox=result,
        notes=["Docker used when available; local restricted fallback keeps the demo runnable without Docker."],
    )
    if result.status in {RunStatus.failed, RunStatus.timed_out} and patch:
        console.print("[bright_green][HEAL][/bright_green] preparing branch-scoped remediation ...")
        remediation = generate_patch(graph, result, target)
        git_result = apply_patch_on_branch(ROOT, target, remediation)
        report.patch, report.git = remediation, git_result
        console.print(f"[bright_green]OK[/bright_green] commit {git_result.commit[:8]} on {git_result.branch}")
        console.print("[dim]No default-branch file was overwritten. Review the local commit or push it to open a GitHub PR.[/dim]")
    _report_path().write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report


@app.command()
def analyze(target: Path = typer.Argument(DEFAULT_TARGET)) -> None:
    """Print the Graphify-compatible dependency map and blast radius."""
    console.print_json(build_graph(target).model_dump_json(indent=2))


@app.command()
def attack(
    target: Path = typer.Argument(DEFAULT_TARGET),
    defcon: int = typer.Option(5, min=1, max=5),
    no_docker: bool = typer.Option(False, help="Use the controlled local fallback."),
    no_patch: bool = typer.Option(False, help="Detect only; do not create a branch commit."),
) -> None:
    """Attack an approved local demo target, then create a reviewable patch branch."""
    _execute(target, defcon, prefer_docker=not no_docker, patch=not no_patch)


@app.command()
def doctor() -> None:
    """Check optional integrations without contacting any remote service."""
    table = Table(title="Sentinel environment")
    table.add_column("Integration")
    table.add_column("Status")
    table.add_row("Docker Desktop", "[green]available[/green]" if docker_available() else "[yellow]not running - safe fallback enabled[/yellow]")
    table.add_row("OpenAI", "[green]configured[/green]" if __import__("os").getenv("OPENAI_API_KEY") else "[yellow]offline fixture enabled[/yellow]")
    try:
        __import__("graphify")
        graphify_status = "[green]installed (required)[/green]"
    except ModuleNotFoundError:
        graphify_status = "[red]missing - run pip install -e .[/red]"
    table.add_row("Graphify", graphify_status)
    console.print(table)


def run_demo() -> int:
    """Called by the root one-click script; returns a conventional process code."""
    try:
        report = _execute(DEFAULT_TARGET, risk_level=5, prefer_docker=True, patch=True)
        if report.git:
            console.print("[bold green]DEMO COMPLETE:[/] race found and a reviewable remediation commit created.")
        return 0
    except Exception as exc:
        console.print(f"[bold red]DEMO FAILED:[/] {exc}")
        return 1


def main() -> None:
    app()


if __name__ == "__main__":
    main()
