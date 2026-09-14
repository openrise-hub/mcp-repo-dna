"""Test runner, mock strategy, and assertion grammar detection."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from mcp_repodna.core.sampler import read_text
from mcp_repodna.extractors.base import BaseExtractor, RepoContext
from mcp_repodna.models.dna import ConfidenceLevel, TestingProfile

PYTEST_CONFIGS = ("pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml")
JEST_CONFIGS = ("jest.config.js", "jest.config.ts", "jest.config.json")
VITEST_CONFIGS = ("vitest.config.ts", "vitest.config.js", "vitest.config.mts")

MOCK_MARKERS = {
    "unittest.mock": "unittest.mock",
    "from mock import": "mock",
    "pytest-mock": "pytest-mock",
    "mocker.fixture": "pytest-mock",
    "respx": "respx",
    "sinon": "sinon",
    "jest.fn(": "jest.fn",
    "jest.mock(": "jest.mock",
    "vi.fn(": "vitest.fn",
    "vi.mock(": "vitest.mock",
    "msw": "msw",
}

ASSERTION_MARKERS = {
    r"\bassert\s": "pytest-style assert",
    r"\bexpect\(.+\)\.to": "jest-style expect",
    r"\bexpect\(.+\)\.toMatchSnapshot": "snapshot expect",
    r"\bself\.assert": "unittest-style assert",
}

COVERAGE_TOOLS = {
    "pytest-cov": "pytest-cov",
    "coverage": "coverage",
    ".nycrc": "nyc",
    "codecov.yml": "codecov",
    "coveralls.yml": "coveralls",
}

SNAPSHOT_PATTERNS = (".snap", "__snapshots__", "toMatchSnapshot", "toMatchInlineSnapshot")


def _contains(text: str, markers: dict[str, str]) -> list[str]:
    found: list[str] = []
    for marker, label in markers.items():
        if marker in text:
            found.append(label)
    return found


def _pyproject_dev_deps(path: Path) -> str:
    text = read_text(path)
    if not text:
        return ""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return ""
    groups = data.get("dependency-groups", {})
    if isinstance(groups, dict) and isinstance(groups.get("dev"), list):
        return "\n".join(groups["dev"])
    deps = data.get("project", {}).get("optional-dependencies", {})
    if isinstance(deps, dict) and isinstance(deps.get("dev"), list):
        return "\n".join(deps["dev"])
    return ""


class TestingExtractor(BaseExtractor):
    """Detect test runner, mock strategy, and assertion grammar."""

    name = "testing"

    def extract(self, context: RepoContext) -> TestingProfile:
        profile = TestingProfile()
        profile.runner = self._runner(context)

        mock_libraries: list[str] = []
        grammar: list[str] = []
        snapshot = False
        for path in context.sample.files:
            text = read_text(path)
            if not text:
                continue
            if self._is_test_file(path):
                for marker, label in ASSERTION_MARKERS.items():
                    if re.search(marker, text) and label not in grammar:
                        grammar.append(label)
            for marker, label in MOCK_MARKERS.items():
                if marker in text and label not in mock_libraries:
                    mock_libraries.append(label)
            if any(pattern in text for pattern in SNAPSHOT_PATTERNS):
                snapshot = True
            if path.name in ("pyproject.toml", "package.json", "requirements-dev.txt"):
                mock_libraries.extend(self._declared_mocks(path))
        profile.mock_libraries = sorted(set(mock_libraries))
        profile.assertion_grammar = grammar
        profile.snapshot_testing = snapshot
        profile.coverage_tools = self._coverage_tools(context)

        if profile.runner:
            profile.confidence = (
                ConfidenceLevel.HIGH if profile.assertion_grammar else ConfidenceLevel.MEDIUM
            )
        elif grammar:
            profile.confidence = ConfidenceLevel.MEDIUM
        else:
            profile.notes.append("no test runner or test files detected")
            profile.confidence = ConfidenceLevel.LOW
        return profile

    @staticmethod
    def _is_test_file(path: Path) -> bool:
        name = path.name.lower()
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or ".test." in name
            or ".spec." in name
            or name.endswith("_test.go")
            or name.endswith(".spec.ts")
            or name.endswith(".spec.js")
        )

    @staticmethod
    def _runner(context: RepoContext) -> str | None:
        if any(context.find_named(name) for name in VITEST_CONFIGS):
            return "vitest"
        if any(context.find_named(name) for name in JEST_CONFIGS):
            return "jest"
        if context.find_named("package.json") is not None:
            path = context.find_named("package.json")
            text = read_text(path) if path else ""
            if text and ("vitest" in text or "vitest run" in text or "vitest --" in text):
                return "vitest"
            if text and '"jest"' in text:
                return "jest"
        if any(context.find_named(name) for name in PYTEST_CONFIGS):
            return "pytest"
        return None

    @staticmethod
    def _declared_mocks(path: Path) -> list[str]:
        text = read_text(path) or ""
        found = [label for marker, label in MOCK_MARKERS.items() if marker in text]
        if path.name == "pyproject.toml":
            found.extend(_contains(_pyproject_dev_deps(path), MOCK_MARKERS))
        return found

    @staticmethod
    def _coverage_tools(context: RepoContext) -> list[str]:
        tools: list[str] = []
        for name, label in COVERAGE_TOOLS.items():
            if context.find_named(name) is not None:
                tools.append(label)
        pyproject = context.find_named("pyproject.toml")
        if pyproject is not None and "pytest-cov" in _pyproject_dev_deps(pyproject):
            tools.append("pytest-cov")
        package_json = context.find_named("package.json")
        if package_json is not None:
            text = read_text(package_json) or ""
            if "coverage" in text:
                tools.append("coverage")
            if '"c8"' in text:
                tools.append("c8")
            if '"nyc"' in text:
                tools.append("nyc")
        return sorted(set(tools))
