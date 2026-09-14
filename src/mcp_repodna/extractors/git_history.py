"""Commit log styles, merge strategies, and branch conventions."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from mcp_repodna.extractors.base import BaseExtractor, GitCommit, RepoContext
from mcp_repodna.models.dna import ConfidenceLevel, GitConventions

CONVENTIONAL_TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)

CONVENTIONAL_RE = re.compile(r"^(?P<type>" + "|".join(CONVENTIONAL_TYPES) + r")(\((?P<scope>[^)]+)\))?!?: .+")

BRANCH_PREFIX_RE = re.compile(r"^(?P<prefix>[a-z]+)/")

MAX_COMMITS = 200


def collect_commits(path: Path, max_commits: int = MAX_COMMITS) -> list[GitCommit]:
    """Read commit log metadata from a checkout using git."""
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"-n{max_commits}",
                "--pretty=format:%H%x09%P%x09%s",
            ],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return []
    commits: list[GitCommit] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        commit_hash, parents, subject = parts
        parent_hashes = [p for p in parents.split() if p]
        commits.append(
            GitCommit(
                hash=commit_hash,
                subject=subject,
                parents=len(parent_hashes),
                merge=len(parent_hashes) > 1,
            )
        )
    return commits


def collect_branches(path: Path) -> list[str]:
    """Return branch short names, e.g. origin/main, origin/feat/thing.

    Falls back to local branch heads when no remote refs exist.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "for-each-ref",
                "--format=%(refname:short)",
                "refs/remotes",
                "refs/heads",
            ],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return []
    return [line for line in result.stdout.splitlines() if line]


def default_branch(path: Path) -> str | None:
    """Resolve the default branch name from origin/HEAD, falling back to HEAD."""
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        result = None
    if result and result.stdout.strip():
        name = result.stdout.strip()
        return name.removeprefix("origin/") if name.startswith("origin/") else name
    try:
        fallback = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return fallback.stdout.strip() or None


class GitHistoryExtractor(BaseExtractor):
    """Extract commit style, merge strategy, and branch conventions."""

    name = "git"

    def extract(self, context: RepoContext) -> GitConventions:
        commits = context.commits or collect_commits(context.path)
        profile = GitConventions()

        if commits:
            profile.max_subject_length = max(len(c.subject) for c in commits)
            profile.example_commits = [c.subject for c in commits[:5]]
            conventional = sum(1 for c in commits if CONVENTIONAL_RE.match(c.subject))
            profile.conventional_commit_ratio = conventional / len(commits)
            if profile.conventional_commit_ratio >= 0.6:
                profile.commit_style = "conventional"
            else:
                profile.commit_style = "freeform"

            merges = sum(1 for c in commits if c.merge)
            if merges and merges / len(commits) >= 0.05:
                profile.merge_strategy = "merge"
            else:
                profile.merge_strategy = "squash-or-rebase"
                profile.notes.append("no merge commits observed; strategy is likely squash or rebase")

            if len(commits) >= 20:
                profile.confidence = ConfidenceLevel.HIGH
            else:
                profile.confidence = ConfidenceLevel.MEDIUM
        else:
            profile.notes.append("no commit history available; shallow clone too shallow")
            profile.confidence = ConfidenceLevel.LOW

        branches = context.branches or collect_branches(context.path)
        prefixes: set[str] = set()
        for branch in branches:
            short = branch.removeprefix("origin/")
            match = BRANCH_PREFIX_RE.match(short)
            if match:
                prefixes.add(match.group("prefix"))
            elif short not in {"HEAD"}:
                prefixes.add("plain")
        profile.branch_conventions = sorted(prefixes)
        profile.default_branch = context.default_branch or default_branch(context.path)

        if not profile.branch_conventions and not branches:
            profile.notes.append("branch conventions unavailable from a single-branch clone")
        return profile
