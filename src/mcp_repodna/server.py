"""MCP server exposing repository DNA analysis tools and resources."""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path

import anyio
from mcp.server.mcpserver import MCPServer

from mcp_repodna.core import pipeline
from mcp_repodna.generators.skill_compiler import compile_dna
from mcp_repodna.models.dna import RepoDNA

mcp = MCPServer(
    "mcp-repodna",
    instructions=(
        "Analyzes public repositories and compiles their engineering culture "
        "into actionable skills.sh and rules.md artifacts for coding agents."
    ),
)


def _dump(dna: RepoDNA) -> str:
    return dna.model_dump_json(indent=2)


@mcp.tool()
async def analyze_repository(
    repo_url: str,
    history_depth: int = 100,
    output_dir: str | None = None,
) -> str:
    """Analyze a repository and return its engineering DNA as JSON.

    Args:
        repo_url: Git URL or local path of the repository to analyze.
        history_depth: Number of commits to fetch for git history analysis.
        output_dir: Optional directory to also write skills.sh and rules.md into.
    """
    dna = await anyio.to_thread.run_sync(partial(pipeline.analyze, repo_url, history_depth=history_depth))
    if output_dir:
        paths = compile_dna(dna).write(Path(output_dir))
        dna.notes.append(f"artifacts written to {[str(p) for p in paths]}")
    return _dump(dna)


@mcp.tool()
async def generate_skills(
    repo_url: str,
    output_dir: str,
    history_depth: int = 100,
) -> str:
    """Generate skills.sh and rules.md for a repository into a directory.

    Args:
        repo_url: Git URL or local path of the repository to analyze.
        output_dir: Directory to write skills.sh and rules.md into.
        history_depth: Number of commits to fetch for git history analysis.
    """
    dna = await anyio.to_thread.run_sync(partial(pipeline.analyze, repo_url, history_depth=history_depth))
    paths = await anyio.to_thread.run_sync(partial(compile_dna(dna).write, Path(output_dir)))
    return json.dumps({"written": [str(p) for p in paths]})


@mcp.tool()
async def analyze_dimension(
    repo_url: str,
    dimension: str,
    history_depth: int = 100,
) -> str:
    """Analyze a single DNA dimension of a repository and return it as JSON.

    Args:
        repo_url: Git URL or local path of the repository to analyze.
        dimension: One of the dimensions from the list_dimensions tool.
        history_depth: Number of commits to fetch for git history analysis.
    """
    result = await anyio.to_thread.run_sync(
        partial(pipeline.analyze_dimension, repo_url, dimension, history_depth=history_depth)
    )
    return result.model_dump_json(indent=2)


@mcp.tool()
def list_dimensions() -> list[str]:
    """List the DNA dimensions available for analysis."""
    return pipeline.dimension_names()


@mcp.resource("dna://schema")
def dna_schema() -> str:
    """JSON schema of the RepoDNA model produced by analysis."""
    return json.dumps(RepoDNA.model_json_schema(), indent=2)


@mcp.resource("dna://dimensions")
def dna_dimensions() -> str:
    """JSON list of extractable DNA dimension names."""
    return json.dumps(pipeline.dimension_names(), indent=2)


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
