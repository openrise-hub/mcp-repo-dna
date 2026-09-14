"""Tests for skill_compiler template rendering."""

from __future__ import annotations

from mcp_repodna.generators.skill_compiler import build_commands, compile_dna
from mcp_repodna.models import dna as dna_models
from mcp_repodna.models.dna import ConfidenceLevel, RepoDNA


def make_dna(**overrides: object) -> RepoDNA:
    dna = RepoDNA(repository="https://example.com/fake.git")
    dna.git.commit_style = "conventional"
    dna.git.conventional_commit_ratio = 0.9
    dna.git.branch_conventions = ["feat", "fix"]
    dna.linters.linters = ["ruff"]
    dna.linters.formatters = ["prettier"]
    dna.testing.runner = "pytest"
    dna.testing.coverage_tools = ["pytest-cov"]
    dna.architecture.type_strictness = "mypy-strict"
    dna.tooling.pre_commit_hooks = ["ruff", "trailing-whitespace"]
    for key, value in overrides.items():
        setattr(dna, key, value)
    return dna


def test_build_commands_derives_expected_commands() -> None:
    commands = build_commands(make_dna())
    assert commands["lint"] == ["ruff check ."]
    assert commands["format"] == ["prettier --check ."]
    assert commands["typecheck"] == ["mypy ."]
    assert commands["test"] == ["pytest --cov"]


def test_build_commands_vitest() -> None:
    dna = make_dna()
    dna.testing = dna_models.TestingProfile(runner="vitest")
    commands = build_commands(dna)
    assert commands["test"] == ["vitest run"]


def test_skills_script_has_guards_and_functions() -> None:
    result = compile_dna(make_dna())
    assert result.skills_script.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in result.skills_script
    assert "dna:lint()" in result.skills_script
    assert "ruff check ." in result.skills_script
    assert "dna:test()" in result.skills_script
    assert "pytest --cov" in result.skills_script
    assert "dna:typecheck()" in result.skills_script
    assert "mypy ." in result.skills_script
    assert "dna:branch()" in result.skills_script
    assert "^(feat|fix)/" in result.skills_script
    assert "dna:commit()" in result.skills_script
    assert "conventional commits" in result.skills_script
    assert "dna:install-hooks()" in result.skills_script
    assert "dna:preflight()" in result.skills_script
    assert "BASH_SOURCE" in result.skills_script


def test_rules_markdown_has_all_sections() -> None:
    result = compile_dna(make_dna())
    for section in (
        "## Git conventions",
        "## Architecture",
        "## Linting and formatting",
        "## Tooling",
        "## Testing",
        "## Governance",
        "## Caveats",
    ):
        assert section in result.rules_markdown
    assert "commit_style" not in result.rules_markdown
    assert "- Commit style: conventional" in result.rules_markdown
    assert "- Test runner: pytest" in result.rules_markdown


def test_compile_empty_dna_degrades_gracefully() -> None:
    dna = RepoDNA(repository="empty")
    result = compile_dna(dna)
    assert result.skills_script.startswith("#!/usr/bin/env bash")
    assert "no linter detected" in result.skills_script
    assert "no test runner detected" in result.skills_script
    assert "## Governance" in result.rules_markdown


def test_write_outputs(tmp_path) -> None:
    result = compile_dna(make_dna())
    paths = result.write(tmp_path)
    assert (tmp_path / "skills.sh").exists()
    assert (tmp_path / "rules.md").exists()
    assert len(paths) == 2
    assert (tmp_path / "skills.sh").read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")


def test_aggregate_confidence_is_exposed() -> None:
    dna = make_dna()
    assert dna.confidence is ConfidenceLevel.LOW
