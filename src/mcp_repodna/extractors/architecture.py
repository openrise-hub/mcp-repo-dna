"""Source layout, test placement, and typing posture analysis."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from mcp_repodna.core.sampler import read_text
from mcp_repodna.extractors.base import BaseExtractor, RepoContext
from mcp_repodna.models.dna import ArchitectureProfile, ConfidenceLevel

MANIFEST_NAMES = {
    "package.json": "npm",
    "pyproject.toml": "python",
    "go.mod": "go",
    "Cargo.toml": "cargo",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "pom.xml": "maven",
}

DEPENDENCY_MANAGER_LOCKFILES = {
    "uv.lock": "uv",
    "poetry.lock": "poetry",
    "package-lock.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "Cargo.lock": "cargo",
    "go.sum": "go",
}

TYPE_CHECK_NAMES = {
    "mypy.ini": "mypy",
    "pyrightconfig.json": "pyright",
    "tsconfig.json": "tsconfig",
}

TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec", "specs", "e2e"}

CO_LOCATED_RE = re.compile(r"\.(test|spec)\.[a-z0-9]+$|_(test|spec)\.[a-z0-9]+$", re.IGNORECASE)

ANNOTATED_DEF_RE = re.compile(r"(async\s+def|def)\s+\w+\([^)]*(?::[^)=]+|=)[^)]*\)\s*(->[^:]+)?:")

MAX_TYPE_SAMPLE_FILES = 100


def _load_json(path: Path) -> dict:
    text = read_text(path)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _load_toml(path: Path) -> dict:
    text = read_text(path)
    if not text:
        return {}
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {}


class ArchitectureExtractor(BaseExtractor):
    """Analyze co-location versus centralized tests, folder layout, and typing."""

    name = "architecture"

    def extract(self, context: RepoContext) -> ArchitectureProfile:
        profile = ArchitectureProfile()

        manifest_dirs: dict[str, set[Path]] = {name: set() for name in MANIFEST_NAMES}
        for name in MANIFEST_NAMES:
            for path in self._manifest_paths(context, name):
                manifest_dirs[name].add(path.parent)
        monorepo = any(len(dirs) > 1 for dirs in manifest_dirs.values())
        if monorepo:
            profile.layout = "monorepo"
        elif context.exists("src"):
            profile.layout = "src"
        else:
            profile.layout = "flat"

        profile.test_layout = self._test_layout(context)
        profile.typed, profile.type_strictness = self._typing(context)
        profile.dependency_manager = self._dependency_manager(context)

        evidence = int(profile.layout is not None) + int(profile.test_layout is not None)
        profile.confidence = ConfidenceLevel.HIGH if evidence == 2 else ConfidenceLevel.MEDIUM
        return profile

    @staticmethod
    def _manifest_paths(context: RepoContext, name: str) -> list[Path]:
        return [path for path in context.sample.files if path.name == name]

    @staticmethod
    def _test_layout(context: RepoContext) -> str | None:
        centralized: set[Path] = set()
        co_located = 0
        for path in context.sample.files:
            parts = path.parts
            root_index = parts.index(context.sample.root.name) + 1 if context.sample.root.name in parts else 0
            if root_index:
                parts = parts[root_index:]
            if parts and (
                (parts[0] in TEST_DIR_NAMES and path.name.startswith("test_"))
                or any(part in TEST_DIR_NAMES for part in parts)
            ):
                centralized.add(parts[0])
            if CO_LOCATED_RE.search(path.name):
                co_located += 1
        central = len(centralized)
        if central == 0 and co_located == 0:
            return None
        if central > 0 and co_located == 0:
            return "centralized"
        if central == 0 and co_located > 0:
            return "co-located"
        return "mixed"

    @staticmethod
    def _typing(context: RepoContext) -> tuple[bool | None, str | None]:
        strictness: str | None = None
        for name, tool in TYPE_CHECK_NAMES.items():
            path = context.find_named(name)
            if path is None:
                continue
            if tool == "tsconfig":
                data = _load_json(path)
                compiler = data.get("compilerOptions", {})
                if isinstance(compiler, dict) and compiler.get("strict") is True:
                    strictness = "tsconfig-strict"
                return True, strictness
            return True, f"{tool}-configured"

        pyprojects = [p for p in context.sample.files if p.name == "pyproject.toml"]
        annotated = 0
        checked = 0
        for path in context.sample.files:
            if path.suffix != ".py" or not path.is_file():
                continue
            if checked >= MAX_TYPE_SAMPLE_FILES:
                break
            checked += 1
            text = read_text(path)
            if not text:
                continue
            if ANNOTATED_DEF_RE.search(text):
                annotated += 1
        if checked == 0:
            if pyprojects:
                return True, None
            return None, None
        typed = annotated / checked >= 0.3

        for pyproject in pyprojects:
            data = _load_toml(pyproject)
            tools = data.get("tool", {})
            mypy = tools.get("mypy", {})
            if isinstance(mypy, dict) and mypy.get("strict") is True:
                strictness = "mypy-strict"
            if strictness is None and isinstance(mypy, dict) and mypy:
                strictness = "mypy-basic"
            pyright = tools.get("pyright", {})
            if strictness is None and isinstance(pyright, dict):
                strictness = "pyright-" + str(pyright.get("typeCheckingMode", "basic"))
        return typed, strictness

    @staticmethod
    def _dependency_manager(context: RepoContext) -> str | None:
        for name, manager in DEPENDENCY_MANAGER_LOCKFILES.items():
            if context.exists(name):
                return manager
        if context.exists("requirements.txt"):
            return "pip"
        if context.exists("pyproject.toml"):
            return "pyproject"
        if context.exists("package.json"):
            return "npm"
        return None
