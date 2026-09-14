"""Shared fixtures for the test suite."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_FILES: dict[str, str] = {
    ".editorconfig": "\n".join(
        (
            "root = true",
            "",
            "[*]",
            "indent_style = space",
            "indent_size = 4",
            "end_of_line = lf",
            "charset = utf-8",
            "max_line_length = 120",
            "insert_final_newline = true",
            "trim_trailing_whitespace = true",
            "",
        )
    ),
    "ruff.toml": "\n".join(
        (
            "line-length = 120",
            "",
            "[lint]",
            'select = ["E", "F", "I"]',
            "",
        )
    ),
    ".prettierrc": '{"printWidth": 100, "tabWidth": 2, "singleQuote": true}\n',
    "Makefile": "\n".join(
        (
            ".PHONY: test lint build",
            "",
            "test:",
            "\tpytest",
            "",
            "lint:",
            "\truff check .",
            "",
            "build:",
            "\tpython -m build",
            "",
        )
    ),
    "package.json": '{"name": "fake-service", "scripts": {"build": "node scripts/build.js", "start": "node server.js"}}\n',
    ".pre-commit-config.yaml": "\n".join(
        (
            "repos:",
            "  - repo: https://github.com/astral-sh/ruff-pre-commit",
            "    rev: v0.9.0",
            "    hooks:",
            "      - id: ruff",
            "      - id: ruff-format",
            "  - repo: https://github.com/pre-commit/pre-commit-hooks",
            "    rev: v5.0.0",
            "    hooks:",
            "      - id: trailing-whitespace",
            "",
        )
    ),
    ".github/workflows/ci.yml": "\n".join(
        (
            "name: CI",
            "on: [push]",
            "jobs:",
            "  test:",
            "    runs-on: ubuntu-latest",
            "    steps:",
            "      - run: pytest",
            "",
        )
    ),
    ".github/pull_request_template.md": "## What changed\n\nDescribe your change.\n",
    ".github/ISSUE_TEMPLATE/bug_report.md": "## Describe the bug\n\nWhat happened?\n",
    "CONTRIBUTING.md": "# Contributing\n\nRead the ADRs first.\n",
    "docs/adr/0001-record-architecture-decisions.md": "# 1. Record architecture decisions\n\nUse ADRs for significant choices.\n",
    "CODEOWNERS": "* @fake-org/core\n",
    "SECURITY.md": "# Security Policy\n\nReport issues privately.\n",
    "CODE_OF_CONDUCT.md": "# Code of Conduct\n\nBe kind.\n",
    "uv.lock": "version = 1\n",
    "pyproject.toml": "\n".join(
        (
            "[project]",
            'name = "fake-service"',
            'version = "0.1.0"',
            'requires-python = ">=3.12"',
            "",
            "[dependency-groups]",
            'dev = ["pytest>=8", "pytest-mock>=3", "pytest-cov>=6"]',
            "",
            "[tool.pytest.ini_options]",
            'testpaths = ["tests"]',
            "",
            "[tool.mypy]",
            "strict = true",
            "",
        )
    ),
    "src/fake_svc/__init__.py": '"""Fake service package."""\n',
    "src/fake_svc/core.py": "\n".join(
        (
            '"""Core logic for the fake service."""',
            "",
            "",
            "def add(left: int, right: int) -> int:",
            "    return left + right",
            "",
        )
    ),
    "tests/test_core.py": "\n".join(
        (
            "from fake_svc.core import add",
            "",
            "",
            "def test_add(mocker):",
            "    mock = mocker.Mock(return_value=3)",
            "    assert mock() == 3",
            "    assert add(1, 2) == 3",
            "",
        )
    ),
}


def git(repo: Path, *args: str) -> str:
    """Run a git command inside a repository checkout."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    """Build a small git repository that exercises every DNA dimension."""
    repo = tmp_path / "fake-repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Test User")
    git(repo, "config", "user.email", "test@example.com")

    for relative, content in REPO_FILES.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "feat: scaffold fake service")
    git(repo, "checkout", "-q", "-b", "feat/extra")
    git(repo, "commit", "-q", "--allow-empty", "-m", "feat(api): add core module")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "--no-ff", "-q", "-m", "Merge branch 'feat/extra'", "feat/extra")
    git(repo, "commit", "-q", "--allow-empty", "-m", "fix: handle empty inputs gracefully")
    git(repo, "commit", "-q", "--allow-empty", "-m", "chore: configure pre-commit hooks")
    git(repo, "commit", "-q", "--allow-empty", "-m", "docs: document governance artifacts")
    return repo
