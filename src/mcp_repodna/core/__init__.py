"""Core services: fetching, sampling, and analysis orchestration."""

from mcp_repodna.core.fetcher import FetchedRepo, FetcherError, clone_shallow, commit_count, deepen, git_available
from mcp_repodna.core.pipeline import analyze, analyze_dimension, dimension_names
from mcp_repodna.core.sampler import Sample, read_text, sample_files

__all__ = [
    "FetchedRepo",
    "FetcherError",
    "Sample",
    "analyze",
    "analyze_dimension",
    "clone_shallow",
    "commit_count",
    "deepen",
    "dimension_names",
    "git_available",
    "read_text",
    "sample_files",
]
