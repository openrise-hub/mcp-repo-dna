"""Selective file sampling that excludes artifacts, vendors, and lockfiles."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    ".tox",
    "node_modules",
    "bower_components",
    "dist",
    "build",
    "target",
    "out",
    "coverage",
    "htmlcov",
    "vendor",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
    ".nuxt",
    ".cache",
    ".idea",
    ".vscode",
    "tmp",
    "temp",
}

LOCK_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lock",
    "bun.lockb",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "Gemfile.lock",
    "composer.lock",
    "mix.lock",
    "deno.lock",
}

BINARY_EXTENSIONS = {
    ".7z",
    ".bin",
    ".class",
    ".db",
    ".dll",
    ".eot",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".otf",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".sqlite",
    ".tar",
    ".tgz",
    ".ttf",
    ".wasm",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
}

DEFAULT_MAX_FILE_SIZE = 1 * 1024 * 1024


@dataclass
class Sample:
    """The set of files selected from a repository checkout."""

    root: Path
    files: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def relative_files(self) -> list[Path]:
        """Return sampled files as paths relative to the root."""
        return [path.relative_to(self.root) for path in self.files]


def is_binary(path: Path) -> bool:
    """Detect binary files by extension, with a null byte sniff as fallback."""
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with path.open("rb") as handle:
            chunk = handle.read(1024)
    except OSError:
        return True
    return b"\x00" in chunk


def sample_files(root: Path, max_file_size: int = DEFAULT_MAX_FILE_SIZE) -> Sample:
    """Walk a repository and select text files worth analyzing.

    Excluded: ignored directories, lockfiles, binaries, oversized files, and
    symlinks. Dotfiles such as .editorconfig and .github metadata are kept.
    """
    sample = Sample(root=root)
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = sorted(name for name in dirnames if name not in IGNORED_DIRS)
        current = Path(dirpath)
        for filename in sorted(filenames):
            path = current / filename
            if filename in LOCK_FILES:
                continue
            if path.is_symlink():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > max_file_size:
                sample.skipped.append(str(path.relative_to(root)))
                continue
            if is_binary(path):
                continue
            sample.files.append(path)
    return sample


def read_text(path: Path) -> str | None:
    """Read a sampled file as text with encoding fallbacks."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return path.read_text(encoding="latin-1")
    except OSError:
        return None
