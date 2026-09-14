"""Repository dimension extractors."""

from mcp_repodna.extractors.architecture import ArchitectureExtractor
from mcp_repodna.extractors.base import BaseExtractor, GitCommit, RepoContext
from mcp_repodna.extractors.git_history import GitHistoryExtractor
from mcp_repodna.extractors.governance import GovernanceExtractor
from mcp_repodna.extractors.linters_format import LintFormatExtractor
from mcp_repodna.extractors.testing import TestingExtractor
from mcp_repodna.extractors.tooling import ToolingExtractor

__all__ = [
    "ArchitectureExtractor",
    "BaseExtractor",
    "GitCommit",
    "GitHistoryExtractor",
    "GovernanceExtractor",
    "LintFormatExtractor",
    "RepoContext",
    "TestingExtractor",
    "ToolingExtractor",
]

EXTRACTORS: dict[str, type[BaseExtractor]] = {
    extractor.name: extractor
    for extractor in (
        GitHistoryExtractor,
        LintFormatExtractor,
        ArchitectureExtractor,
        ToolingExtractor,
        TestingExtractor,
        GovernanceExtractor,
    )
}
