"""Core services: fetching and sampling repositories."""

from mcp_repodna.core.fetcher import FetchedRepo, FetcherError, clone_shallow, commit_count, deepen, git_available

__all__ = [
    "FetchedRepo",
    "FetcherError",
    "clone_shallow",
    "commit_count",
    "deepen",
    "git_available",
]
