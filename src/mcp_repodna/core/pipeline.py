"""Orchestrates fetching, sampling, and extraction into the final DNA model."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from pydantic import BaseModel

from mcp_repodna.core.fetcher import FetchedRepo, FetcherError, clone_shallow, deepen
from mcp_repodna.core.sampler import sample_files
from mcp_repodna.extractors import EXTRACTORS
from mcp_repodna.extractors.base import RepoContext
from mcp_repodna.extractors.git_history import collect_branches, collect_commits, default_branch
from mcp_repodna.models.dna import ConfidenceLevel, DIMENSIONS, RepoDNA

logger = logging.getLogger(__name__)


@contextmanager
def _checkout(
    repo_url: str,
    *,
    clone_depth: int,
    timeout: int,
    keep: bool,
) -> Iterator[FetchedRepo]:
    repo = clone_shallow(repo_url, depth=clone_depth, timeout=timeout)
    try:
        yield repo
    finally:
        if not keep:
            repo.cleanup()


def analyze(
    repo_url: str,
    *,
    history_depth: int = 100,
    clone_depth: int = 1,
    timeout: int = 120,
    keep_checkout: bool = False,
) -> RepoDNA:
    """Analyze a repository and return its aggregated engineering DNA."""
    dna = RepoDNA(repository=repo_url)

    with _checkout(repo_url, clone_depth=clone_depth, timeout=timeout, keep=keep_checkout) as repo:
        if history_depth > clone_depth:
            try:
                deepen(repo, history_depth, timeout=timeout)
            except FetcherError as exc:
                dna.notes.append(f"could not deepen history: {exc}")

        context = RepoContext(
            repository=repo_url,
            path=repo.path,
            sample=sample_files(repo.path),
            commits=collect_commits(repo.path),
            branches=collect_branches(repo.path),
            default_branch=default_branch(repo.path),
        )

        high = 0
        for name, extractor_cls in EXTRACTORS.items():
            result, error = extractor_cls().run(context)
            if result is None:
                dna.notes.append(error or f"extractor '{name}' failed")
                continue
            setattr(dna, name, result)
            if result.confidence is ConfidenceLevel.HIGH:
                high += 1

        if not context.sample.files:
            dna.notes.append("no files sampled; the repository may be empty")

    total = len(EXTRACTORS)
    if high == total:
        dna.confidence = ConfidenceLevel.HIGH
    elif high >= max(1, total // 2):
        dna.confidence = ConfidenceLevel.MEDIUM
    else:
        dna.confidence = ConfidenceLevel.LOW
    return dna


def analyze_dimension(
    repo_url: str,
    dimension: str,
    *,
    history_depth: int = 100,
    timeout: int = 120,
) -> BaseModel:
    """Analyze a single named dimension of a repository."""
    if dimension not in EXTRACTORS:
        raise KeyError(f"unknown dimension '{dimension}'; expected one of {sorted(EXTRACTORS)}")
    dna = analyze(repo_url, history_depth=history_depth, timeout=timeout)
    return dna.dimension(dimension)


def dimension_names() -> list[str]:
    """Return the names of all extractable dimensions."""
    return list(DIMENSIONS)
