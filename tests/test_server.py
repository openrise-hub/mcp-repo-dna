"""Tests for the MCP server tools and resources."""

from __future__ import annotations

import json
from pathlib import Path

import anyio

from mcp_repodna.models.dna import RepoDNA
from mcp_repodna.server import mcp


def test_server_exposes_all_tools() -> None:
    names = {tool.name for tool in anyio.run(mcp.list_tools)}
    assert {
        "analyze_repository",
        "generate_skills",
        "analyze_dimension",
        "list_dimensions",
    } <= names


def test_server_exposes_resources() -> None:
    uris = {str(resource.uri) for resource in anyio.run(mcp.list_resources)}
    assert {"dna://schema", "dna://dimensions"} <= uris


def test_list_dimensions_tool() -> None:
    result = anyio.run(mcp.call_tool, "list_dimensions", {})
    assert result.structured_content["result"] == [
        "git",
        "architecture",
        "linters",
        "tooling",
        "testing",
        "governance",
    ]


def test_dna_schema_resource() -> None:
    result = anyio.run(mcp.read_resource, "dna://schema")
    schema = json.loads(result[0].content)
    assert schema["title"] == "RepoDNA"
    assert {"git", "architecture", "linters", "tooling", "testing", "governance"} <= set(schema["properties"])


def test_dimensions_resource() -> None:
    result = anyio.run(mcp.read_resource, "dna://dimensions")
    names = json.loads(result[0].content)
    assert len(names) == 6


def test_analyze_repository_tool(fake_repo: Path) -> None:
    result = anyio.run(
        mcp.call_tool,
        "analyze_repository",
        {"repo_url": str(fake_repo), "history_depth": 100},
    )
    dna = RepoDNA.model_validate_json(result.structured_content["result"])
    assert dna.git.commit_style == "conventional"
    assert dna.architecture.layout == "src"
    assert dna.testing.runner == "pytest"


def test_generate_skills_tool(fake_repo: Path, tmp_path: Path) -> None:
    output = tmp_path / "artifacts"
    result = anyio.run(
        mcp.call_tool,
        "generate_skills",
        {"repo_url": str(fake_repo), "output_dir": str(output), "history_depth": 100},
    )
    written = json.loads(result.structured_content["result"])["written"]
    assert len(written) == 2
    assert (output / "skills.sh").exists()
    assert (output / "rules.md").exists()


def test_analyze_dimension_tool(fake_repo: Path) -> None:
    result = anyio.run(
        mcp.call_tool,
        "analyze_dimension",
        {"repo_url": str(fake_repo), "dimension": "governance", "history_depth": 100},
    )
    data = json.loads(result.structured_content["result"])
    assert data["pr_template"] is True
