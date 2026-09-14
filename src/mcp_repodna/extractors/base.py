"""Extractor base class and repository context."""

from __future__ import annotations

import fnmatch
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from mcp_repodna.core.sampler import Sample, read_text

logger = logging.getLogger(__name__)


@dataclass
class GitCommit:
    """A single commit with the fields relevant for convention analysis."""

    hash: str
    subject: str
    parents: int
    merge: bool = False


@dataclass
class RepoContext:
    """Everything an extractor needs to inspect a repository checkout."""

    repository: str
    path: Path
    sample: Sample
    commits: list[GitCommit] = field(default_factory=list)
    branches: list[str] = field(default_factory=list)
    default_branch: str | None = None

    def read(self, relative: str | Path) -> str | None:
        """Read a file relative to the checkout root, with encoding fallback."""
        return read_text(self.path / relative)

    def exists(self, relative: str | Path) -> bool:
        """Return True when the given relative path exists in the checkout."""
        return (self.path / relative).exists()

    def matching(self, pattern: str) -> list[Path]:
        """Return sampled files matching a fnmatch pattern on name or relative path."""
        return [
            file
            for file in self.sample.files
            if fnmatch.fnmatch(file.name, pattern) or fnmatch.fnmatch(str(file.relative_to(self.sample.root)), pattern)
        ]

    def find_named(self, name: str) -> Path | None:
        """Find a sampled file by name, case-insensitively."""
        lowered = name.lower()
        for file in self.sample.files:
            if file.name.lower() == lowered:
                return file
        return None


class BaseExtractor(ABC):
    """Abstract base for all repository DNA extractors."""

    name: ClassVar[str]

    @abstractmethod
    def extract(self, context: RepoContext) -> BaseModel:
        """Extract one dimension of engineering DNA from the repository context."""

    def run(self, context: RepoContext) -> tuple[BaseModel | None, str | None]:
        """Run extraction with error isolation.

        Returns ``(result, error)``; exactly one is populated on failure.
        """
        try:
            return self.extract(context), None
        except Exception:
            logger.exception("extractor %s failed", self.name)
            return None, f"extractor '{self.name}' failed"
