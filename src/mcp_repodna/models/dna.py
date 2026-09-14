"""Pydantic V2 schemas for the repository engineering DNA model."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ConfidenceLevel(StrEnum):
    """How much evidence backs a given extracted dimension."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GitConventions(BaseModel):
    """Commit style, merge strategy, and branch naming conventions."""

    commit_style: str | None = Field(
        default=None, description="Dominant commit message style, e.g. conventional, imperative, freeform"
    )
    conventional_commit_ratio: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Share of sampled commits matching conventional style"
    )
    merge_strategy: str | None = Field(default=None, description="Detected merge strategy: squash, merge, or rebase")
    branch_conventions: list[str] = Field(default_factory=list, description="Observed branch naming patterns")
    default_branch: str | None = Field(default=None, description="Default branch name")
    max_subject_length: int | None = Field(default=None, description="Longest commit subject observed")
    example_commits: list[str] = Field(default_factory=list, max_length=5, description="Representative commit subjects")
    notes: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.LOW


class EditorConfigSettings(BaseModel):
    """Parsed values from an .editorconfig file."""

    indent_style: str | None = None
    indent_size: int | None = None
    end_of_line: str | None = None
    charset: str | None = None
    max_line_length: int | None = None
    insert_final_newline: bool | None = None
    trim_trailing_whitespace: bool | None = None


class LintFormatProfile(BaseModel):
    """Linters, formatters, and style configuration."""

    formatters: list[str] = Field(default_factory=list, description="Detected formatters, e.g. prettier, ruff format")
    linters: list[str] = Field(default_factory=list, description="Detected linters, e.g. eslint, ruff")
    editorconfig: EditorConfigSettings | None = None
    line_length: int | None = Field(default=None, description="Configured max line length if found")
    import_sorting: bool | None = Field(default=None, description="Whether import sorting is enforced")
    notes: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.LOW


class ArchitectureProfile(BaseModel):
    """Source layout, test placement, and typing posture."""

    layout: str | None = Field(default=None, description="Detected layout: src, flat, or monorepo")
    test_layout: str | None = Field(default=None, description="Where tests live: co-located, centralized, or mixed")
    typed: bool | None = Field(default=None, description="Whether the codebase uses static type hints")
    type_strictness: str | None = Field(
        default=None, description="Strictness configuration, e.g. mypy strict, pyright basic, tsconfig strict"
    )
    dependency_manager: str | None = Field(
        default=None, description="Dependency manager, e.g. uv, poetry, npm, pnpm, cargo"
    )
    package_manager: str | None = None
    notes: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.LOW


class ToolingProfile(BaseModel):
    """Task runners, hooks, and CI automation."""

    task_runner: str | None = Field(default=None, description="Detected task runner: make, just, taskfile, npm scripts")
    common_tasks: list[str] = Field(default_factory=list, description="Observed task names, e.g. test, lint, build")
    pre_commit_hooks: list[str] = Field(default_factory=list, description="Configured pre-commit hook ids")
    ci_systems: list[str] = Field(default_factory=list, description="CI providers, e.g. github-actions, gitlab-ci")
    notes: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.LOW


class TestingProfile(BaseModel):
    """Test runner, mock strategy, and assertion grammar."""

    runner: str | None = Field(default=None, description="Test runner, e.g. pytest, jest, vitest")
    mock_libraries: list[str] = Field(
        default_factory=list,
        description="Mocking libraries, e.g. pytest-mock, unittest.mock, msw",
    )
    assertion_grammar: list[str] = Field(
        default_factory=list,
        description="Assertion styles observed, e.g. assert, expect(...), snapshot",
    )
    snapshot_testing: bool | None = Field(default=None, description="Whether snapshot tests are used")
    coverage_tools: list[str] = Field(default_factory=list, description="Coverage tooling, e.g. pytest-cov, coverage")
    notes: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.LOW


class GovernanceProfile(BaseModel):
    """Contribution process, templates, and decision records."""

    pr_template: bool = Field(default=False, description="Whether a pull request template exists")
    contributing_guide: bool = Field(default=False, description="Whether CONTRIBUTING.md exists")
    adr_directory: str | None = Field(default=None, description="Path of the ADR directory if present")
    adr_count: int = Field(default=0, description="Number of ADR documents found")
    issue_templates: list[str] = Field(default_factory=list, description="Issue template names found")
    code_owners: bool = Field(default=False, description="Whether CODEOWNERS exists")
    security_policy: bool = Field(default=False, description="Whether SECURITY.md exists")
    code_of_conduct: bool = Field(default=False, description="Whether a code of conduct document exists")
    notes: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.LOW


DIMENSIONS: dict[str, type[BaseModel]] = {
    "git": GitConventions,
    "architecture": ArchitectureProfile,
    "linters": LintFormatProfile,
    "tooling": ToolingProfile,
    "testing": TestingProfile,
    "governance": GovernanceProfile,
}


class RepoDNA(BaseModel):
    """Root model aggregating all extracted dimensions of a repository."""

    repository: str = Field(description="Source URL or path of the analyzed repository")
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    git: GitConventions = Field(default_factory=GitConventions)
    architecture: ArchitectureProfile = Field(default_factory=ArchitectureProfile)
    linters: LintFormatProfile = Field(default_factory=LintFormatProfile)
    tooling: ToolingProfile = Field(default_factory=ToolingProfile)
    testing: TestingProfile = Field(default_factory=TestingProfile)
    governance: GovernanceProfile = Field(default_factory=GovernanceProfile)
    notes: list[str] = Field(default_factory=list, description="Pipeline level warnings and observations")
    confidence: ConfidenceLevel = ConfidenceLevel.LOW

    def dimension(self, name: str) -> BaseModel:
        """Return the sub-model for a named dimension."""
        try:
            return getattr(self, name)
        except AttributeError as exc:  # pragma: no cover - guarded by callers
            raise KeyError(f"unknown dimension: {name}") from exc

    def generate_json_schema(self) -> dict[str, Any]:
        """Return the JSON schema for this model."""
        return self.model_json_schema()
