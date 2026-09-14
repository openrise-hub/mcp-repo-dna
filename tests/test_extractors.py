"""Tests for the extractor suite and the analysis pipeline."""

from __future__ import annotations

from pathlib import Path

from mcp_repodna.core.pipeline import analyze, analyze_dimension
from mcp_repodna.core.sampler import sample_files
from mcp_repodna.extractors import EXTRACTORS
from mcp_repodna.extractors.base import RepoContext
from mcp_repodna.extractors.git_history import collect_branches, collect_commits, default_branch
from mcp_repodna.models.dna import ConfidenceLevel, GitConventions


def build_context(repo: Path) -> RepoContext:
    return RepoContext(
        repository=str(repo),
        path=repo,
        sample=sample_files(repo),
        commits=collect_commits(repo),
        branches=collect_branches(repo),
        default_branch=default_branch(repo),
    )


def test_git_history_extractor(fake_repo: Path) -> None:
    context = build_context(fake_repo)
    result = EXTRACTORS["git"]().extract(context)
    assert isinstance(result, GitConventions)
    assert result.commit_style == "conventional"
    assert result.merge_strategy == "merge"
    assert result.default_branch == "main"
    assert "feat" in result.branch_conventions
    assert result.max_subject_length and result.max_subject_length > 0
    assert result.conventional_commit_ratio >= 0.5


def test_linters_extractor(fake_repo: Path) -> None:
    result = EXTRACTORS["linters"]().extract(build_context(fake_repo))
    assert "ruff" in result.linters
    assert "prettier" in result.formatters
    assert result.line_length == 100
    assert result.import_sorting is True
    assert result.editorconfig is not None
    assert result.editorconfig.indent_size == 4
    assert result.confidence is ConfidenceLevel.HIGH


def test_architecture_extractor(fake_repo: Path) -> None:
    result = EXTRACTORS["architecture"]().extract(build_context(fake_repo))
    assert result.layout == "src"
    assert result.test_layout == "centralized"
    assert result.typed is True
    assert result.type_strictness == "mypy-strict"
    assert result.dependency_manager == "uv"


def test_tooling_extractor(fake_repo: Path) -> None:
    result = EXTRACTORS["tooling"]().extract(build_context(fake_repo))
    assert result.task_runner == "make"
    assert {"test", "lint", "build"} <= set(result.common_tasks)
    assert "ruff" in result.pre_commit_hooks
    assert "github-actions" in result.ci_systems


def test_testing_extractor(fake_repo: Path) -> None:
    result = EXTRACTORS["testing"]().extract(build_context(fake_repo))
    assert result.runner == "pytest"
    assert "pytest-mock" in result.mock_libraries
    assert "pytest-style assert" in result.assertion_grammar
    assert "pytest-cov" in result.coverage_tools
    assert result.snapshot_testing is False


def test_governance_extractor(fake_repo: Path) -> None:
    result = EXTRACTORS["governance"]().extract(build_context(fake_repo))
    assert result.pr_template is True
    assert result.contributing_guide is True
    assert result.adr_directory == "docs/adr"
    assert result.adr_count == 1
    assert result.issue_templates == ["bug_report.md"]
    assert result.code_owners is True
    assert result.security_policy is True


def test_pipeline_end_to_end(fake_repo: Path) -> None:
    dna = analyze(str(fake_repo), history_depth=100)
    assert dna.repository == str(fake_repo)
    assert dna.git.commit_style == "conventional"
    assert dna.architecture.layout == "src"
    assert dna.testing.runner == "pytest"
    assert dna.governance.adr_count == 1
    assert dna.confidence is not ConfidenceLevel.LOW
    assert not dna.notes


def test_analyze_dimension(fake_repo: Path) -> None:
    result = analyze_dimension(str(fake_repo), "governance")
    assert result.pr_template is True


def test_analyze_unknown_dimension(fake_repo: Path) -> None:
    try:
        analyze_dimension(str(fake_repo), "nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError for unknown dimension")
