"""Task runners, pre-commit hooks, and CI automation inspection."""

from __future__ import annotations

import json
import re
from pathlib import Path

from mcp_repodna.core.sampler import read_text
from mcp_repodna.extractors.base import BaseExtractor, RepoContext
from mcp_repodna.models.dna import ConfidenceLevel, ToolingProfile

MAKEFILE_TARGET_RE = re.compile(r"^([a-zA-Z0-9_-][a-zA-Z0-9_.-]*):", re.MULTILINE)
JUSTFILE_TARGET_RE = re.compile(r"^([a-zA-Z0-9_-]+):", re.MULTILINE)
PACKAGE_SCRIPT_KEYS = {"test", "lint", "format", "build", "typecheck", "check", "dev", "start"}
PRE_COMMIT_ID_RE = re.compile(r"^\s+-\s+id:\s+(.+)$", re.MULTILINE)
TASKFILE_TASK_RE = re.compile(r"^\s{2}([a-zA-Z0-9_-]+):", re.MULTILINE)

CI_INDICATORS = {
    ".github/workflows": "github-actions",
    ".gitlab-ci.yml": "gitlab-ci",
    "azure-pipelines.yml": "azure-pipelines",
    ".circleci/config.yml": "circleci",
    ".drone.yml": "drone",
    "bitbucket-pipelines.yml": "bitbucket-pipelines",
}


def _makefile_targets(path: Path) -> list[str]:
    text = read_text(path)
    if not text:
        return []
    return [match.group(1) for match in MAKEFILE_TARGET_RE.finditer(text)][:20]


def _package_json_scripts(path: Path) -> list[str]:
    text = read_text(path)
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return []
    return [name for name in scripts if name in PACKAGE_SCRIPT_KEYS]


def _pre_commit_hooks(path: Path) -> list[str]:
    text = read_text(path)
    if not text:
        return []
    return [match.group(1).strip() for match in PRE_COMMIT_ID_RE.finditer(text)]


def _taskfile_tasks(path: Path) -> list[str]:
    text = read_text(path)
    if not text:
        return []
    return [match.group(1) for match in TASKFILE_TASK_RE.finditer(text)][:20]


class ToolingExtractor(BaseExtractor):
    """Inspect Makefile, package.json scripts, Taskfile, and pre-commit config."""

    name = "tooling"

    def extract(self, context: RepoContext) -> ToolingProfile:
        profile = ToolingProfile()

        makefile = context.find_named("Makefile")
        if makefile is not None:
            targets = _makefile_targets(makefile)
            if targets:
                profile.task_runner = "make"
                profile.common_tasks.extend(targets)

        justfile = context.find_named("justfile")
        if justfile is not None and profile.task_runner is None:
            targets = [m.group(1) for m in JUSTFILE_TARGET_RE.finditer(read_text(justfile) or "")]
            if targets:
                profile.task_runner = "just"
                profile.common_tasks.extend(targets[:20])

        taskfile = context.find_named("Taskfile.yml") or context.find_named("Taskfile.yaml")
        if taskfile is not None and profile.task_runner is None:
            tasks = _taskfile_tasks(taskfile)
            if tasks:
                profile.task_runner = "taskfile"
                profile.common_tasks.extend(tasks)

        package_json = context.find_named("package.json")
        if package_json is not None:
            scripts = _package_json_scripts(package_json)
            if scripts:
                if profile.task_runner is None:
                    profile.task_runner = "npm-scripts"
                profile.common_tasks.extend(name for name in scripts if name not in profile.common_tasks)

        pre_commit = context.find_named(".pre-commit-config.yaml")
        if pre_commit is not None:
            profile.pre_commit_hooks = _pre_commit_hooks(pre_commit)

        ci_systems: list[str] = []
        for relative, system in CI_INDICATORS.items():
            if relative.endswith("workflows"):
                if context.exists(relative):
                    ci_systems.append(system)
            elif context.find_named(relative) is not None:
                ci_systems.append(system)
        profile.ci_systems = sorted(set(ci_systems))

        profile.common_tasks = sorted(set(profile.common_tasks))
        if profile.task_runner or profile.pre_commit_hooks or profile.ci_systems:
            profile.confidence = ConfidenceLevel.HIGH
        elif any(context.find_named(name) for name in ("Makefile", "package.json", "Taskfile.yml")):
            profile.confidence = ConfidenceLevel.MEDIUM
        else:
            profile.notes.append("no task runner or CI configuration detected")
            profile.confidence = ConfidenceLevel.LOW
        return profile
