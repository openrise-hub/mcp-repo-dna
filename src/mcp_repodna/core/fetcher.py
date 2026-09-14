"""Shallow git clone into isolated temp directories with graceful fallbacks."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class FetcherError(RuntimeError):
    """Raised when a repository cannot be fetched."""


REMOTE_SCHEMES = ("http", "https", "git", "ssh", "git+ssh", "git+https", "file")


@dataclass
class FetchedRepo:
    """A repository that has been materialized on disk."""

    url: str
    path: Path
    local: bool = False

    def cleanup(self) -> None:
        """Remove the fetched checkout if it exists."""
        shutil.rmtree(self.path, ignore_errors=True)


def git_available() -> bool:
    """Return True when the git executable is on PATH and usable."""
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True


def is_local_source(repo_url: str) -> bool:
    """Return True when the given source looks like a local filesystem path."""
    return urlparse(repo_url).scheme not in REMOTE_SCHEMES


def _run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run a git command and translate failures into FetcherError."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
    except FileNotFoundError as exc:
        raise FetcherError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise FetcherError(f"git {args[0]} timed out after {timeout}s") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise FetcherError(f"git {args[0]} failed: {detail}") from exc


def clone_shallow(
    repo_url: str,
    destination: Path | None = None,
    depth: int = 1,
    timeout: int = 120,
) -> FetchedRepo:
    """Clone a repository at the given depth into an isolated directory.

    Remote sources use a single branch shallow clone. Local paths are cloned
    from disk, which keeps behavior identical while avoiding network access.
    """
    if not git_available():
        raise FetcherError("git executable not found on PATH")
    if depth < 1:
        raise FetcherError(f"clone depth must be >= 1, got {depth}")

    target = destination or Path(tempfile.mkdtemp(prefix="repodna-"))
    target = target.resolve()
    if target.exists() and any(target.iterdir()):
        raise FetcherError(f"destination directory is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)

    if is_local_source(repo_url):
        source = Path(repo_url).expanduser().resolve()
        if not source.exists():
            raise FetcherError(f"local source does not exist: {source}")
        if not (source / ".git").exists():
            raise FetcherError(f"local source is not a git repository: {source}")
        try:
            _run_git(
                ["clone", "--quiet", "--depth", str(depth), str(source), str(target)],
                timeout=timeout,
            )
        except FetcherError:
            fallback = target.parent / f"{target.name}-copy"
            logger.warning("local clone failed, falling back to directory copy")
            shutil.copytree(source, fallback, ignore=shutil.ignore_patterns(".git"))
            return FetchedRepo(url=repo_url, path=fallback, local=True)
        return FetchedRepo(url=repo_url, path=target, local=True)

    _run_git(
        [
            "clone",
            "--quiet",
            "--depth",
            str(depth),
            "--single-branch",
            repo_url,
            str(target),
        ],
        timeout=timeout,
    )
    return FetchedRepo(url=repo_url, path=target, local=False)


def deepen(repo: FetchedRepo, history_depth: int, timeout: int = 120) -> int:
    """Deepen a shallow clone so more commit history becomes available.

    Returns the number of commits reachable from HEAD after deepening.
    """
    if history_depth <= 1:
        return commit_count(repo.path)
    _run_git(
        ["fetch", "--quiet", f"--deepen={history_depth - 1}", "origin"],
        cwd=repo.path,
        timeout=timeout,
    )
    return commit_count(repo.path)


def commit_count(path: Path) -> int:
    """Return the number of commits reachable from HEAD."""
    result = _run_git(["rev-list", "--count", "HEAD"], cwd=path)
    return int(result.stdout.strip() or 0)
