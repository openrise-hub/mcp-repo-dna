"""Typer CLI for standalone terminal usage."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from mcp_repodna import __version__
from mcp_repodna.core.pipeline import analyze
from mcp_repodna.generators.skill_compiler import compile_dna
from mcp_repodna.models.dna import RepoDNA

app = typer.Typer(
    help="Reverse-engineer a repository's engineering culture into skills.sh and rules.md.",
    no_args_is_help=True,
)
console = Console()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _with_progress(description: str, work: Callable[[], object]) -> object:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description, total=None)
        return work()


def _print_summary(dna: RepoDNA) -> None:
    table = Table(title=f"Repository DNA: {dna.repository}")
    table.add_column("Dimension", style="cyan")
    table.add_column("Key findings")
    table.add_column("Confidence", style="magenta")
    table.add_row("git", dna.git.commit_style or "unknown", dna.git.confidence.value)
    table.add_row("architecture", dna.architecture.layout or "unknown", dna.architecture.confidence.value)
    table.add_row("linters", ", ".join(dna.linters.formatters + dna.linters.linters) or "none", dna.linters.confidence.value)
    table.add_row("tooling", dna.tooling.task_runner or "unknown", dna.tooling.confidence.value)
    table.add_row("testing", dna.testing.runner or "unknown", dna.testing.confidence.value)
    table.add_row("governance", f"adrs={dna.governance.adr_count}", dna.governance.confidence.value)
    console.print(table)


@app.callback()
def callback(
    version: Annotated[bool, typer.Option("--version", help="Show the version and exit.")] = False,
) -> None:
    """mcp-repodna: repository engineering DNA for AI coding agents."""
    if version:
        console.print(f"mcp-repodna {__version__}")
        raise typer.Exit()


@app.command()
def analyze_repo(
    repo_url: Annotated[str, typer.Argument(help="Git URL or local path of the repository.")],
    history_depth: Annotated[
        int, typer.Option("--history-depth", help="Commits to fetch for git history analysis.")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Directory to write skills.sh and rules.md.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print the DNA model as JSON.")] = False,
) -> None:
    """Analyze a repository and print its engineering DNA."""
    depth = history_depth or _env_int("REPODNA_HISTORY_DEPTH", 100)
    dna = _with_progress(f"Analyzing {repo_url}", lambda: analyze(repo_url, history_depth=depth))
    if as_json:
        console.print_json(data=dna.model_dump(mode="json"))
    else:
        _print_summary(dna)
    if output:
        paths = compile_dna(dna).write(output)
        console.print(f"[green]Wrote {paths[0]} and {paths[1]}[/green]")


@app.command()
def compile_repo(
    repo_url: Annotated[str, typer.Argument(help="Git URL or local path of the repository.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Directory to write artifacts into.")] = Path("."),
    history_depth: Annotated[
        int, typer.Option("--history-depth", help="Commits to fetch for git history analysis.")
    ] = None,
) -> None:
    """Analyze a repository and write skills.sh plus rules.md."""
    depth = history_depth or _env_int("REPODNA_HISTORY_DEPTH", 100)
    dna = _with_progress(f"Analyzing {repo_url}", lambda: analyze(repo_url, history_depth=depth))
    paths = compile_dna(dna).write(output)
    console.print(f"[green]Wrote {paths[0]} and {paths[1]}[/green]")


@app.command()
def schema() -> None:
    """Print the JSON schema of the RepoDNA model."""
    console.print_json(data=RepoDNA.model_json_schema())


@app.command()
def serve() -> None:
    """Start the MCP server over stdio."""
    from mcp_repodna.server import mcp

    mcp.run(transport="stdio")


if __name__ == "__main__":
    app()
