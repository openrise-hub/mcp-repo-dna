"""Linter, formatter, and editorconfig detection and parsing."""

from __future__ import annotations

import configparser
import json
import tomllib
from pathlib import Path

from mcp_repodna.extractors.base import BaseExtractor, RepoContext
from mcp_repodna.models.dna import ConfidenceLevel, EditorConfigSettings, LintFormatProfile

FORMATTER_NAMES = {
    "biome.json": "biome",
    ".prettierrc": "prettier",
    ".prettierrc.json": "prettier",
    ".prettierrc.yaml": "prettier",
    ".prettierrc.yml": "prettier",
    ".prettierrc.toml": "prettier",
    "prettier.config.js": "prettier",
    ".clang-format": "clang-format",
    ".stylelintrc": "stylelint",
    "stylelint.config.js": "stylelint",
}

LINTER_NAMES = {
    ".eslintrc": "eslint",
    ".eslintrc.json": "eslint",
    ".eslintrc.js": "eslint",
    ".eslintrc.yml": "eslint",
    "eslint.config.js": "eslint",
    "eslint.config.mjs": "eslint",
    "ruff.toml": "ruff",
    ".ruff.toml": "ruff",
    ".flake8": "flake8",
    "biome.json": "biome",
    ".hadolint.yaml": "hadolint",
    ".pylintrc": "pylint",
    "mypy.ini": "mypy",
    ".yamllint": "yamllint",
}

IMPORT_SORT_LINTERS = {"ruff", "eslint", "biome"}

MAX_CONFIG_SIZE = 200 * 1024


def _read_config(path: Path) -> str | None:
    if path.stat().st_size > MAX_CONFIG_SIZE:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _parse_editorconfig(path: Path) -> EditorConfigSettings:
    text = _read_config(path)
    settings = EditorConfigSettings()
    if not text:
        return settings
    parser = configparser.ConfigParser()
    try:
        parser.read_string(f"[root]\n{text}")
    except configparser.Error:
        return settings
    root = parser["root"]
    if "indent_style" in root:
        settings.indent_style = root["indent_style"].strip()
    if "indent_size" in root:
        raw = root["indent_size"].strip()
        if raw.isdigit():
            settings.indent_size = int(raw)
    if "end_of_line" in root:
        settings.end_of_line = root["end_of_line"].strip()
    if "charset" in root:
        settings.charset = root["charset"].strip()
    if "max_line_length" in root:
        raw = root["max_line_length"].strip()
        if raw.isdigit():
            settings.max_line_length = int(raw)
    settings.insert_final_newline = root.get("insert_final_newline", "").strip() == "true" or None
    if not settings.insert_final_newline:
        settings.insert_final_newline = None
    settings.trim_trailing_whitespace = root.get("trim_trailing_whitespace", "").strip() == "true" or None
    if not settings.trim_trailing_whitespace:
        settings.trim_trailing_whitespace = None
    return settings


def _parse_flake8(path: Path) -> int | None:
    text = _read_config(path)
    if not text:
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read_string(text)
    except configparser.Error:
        return None
    if not parser.has_section("flake8"):
        return None
    raw = parser["flake8"].get("max-line-length")
    return int(raw) if raw and raw.isdigit() else None


def _parse_ruff(path: Path) -> tuple[int | None, bool | None]:
    text = _read_config(path)
    if not text:
        return None, None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None, None
    ruff = data.get("tool", {}).get("ruff", data.get("lint", {}).get("ruff", {}))
    line_length = ruff.get("line-length")
    if not isinstance(line_length, int):
        line_length = None
    selects = ruff.get("select") or ruff.get("lint", {}).get("select", [])
    import_sorting = None
    if isinstance(selects, list):
        import_sorting = "I" in selects
    return line_length, import_sorting


def _parse_prettier(path: Path) -> tuple[int | None, str | None]:
    text = _read_config(path)
    if not text:
        return None, None
    data: dict | None = None
    if path.name.endswith(".json") or path.name == ".prettierrc":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None, None
    if not isinstance(data, dict):
        return None, None
    width = data.get("printWidth")
    indent = data.get("tabWidth")
    return (int(width) if isinstance(width, int) else None), (
        f"tab-width-{indent}" if isinstance(indent, int) else None
    )


def _parse_biome(path: Path) -> tuple[int | None, bool | None]:
    text = _read_config(path)
    if not text:
        return None, None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, None
    formatter = data.get("formatter", {}) if isinstance(data, dict) else {}
    width = formatter.get("lineWidth") if isinstance(formatter, dict) else None
    return (int(width) if isinstance(width, int) else None), None


class LintFormatExtractor(BaseExtractor):
    """Extract linter, formatter, and editorconfig settings."""

    name = "linters"

    def extract(self, context: RepoContext) -> LintFormatProfile:
        profile = LintFormatProfile()

        formatters: list[str] = []
        linters: list[str] = []
        for filename, tool in FORMATTER_NAMES.items():
            path = context.find_named(filename)
            if path is None:
                continue
            if tool not in formatters:
                formatters.append(tool)
            if filename == ".prettierrc" or filename.endswith(".json"):
                width, _ = _parse_prettier(path)
                if width and profile.line_length is None:
                    profile.line_length = width
            if filename == "biome.json":
                width, _ = _parse_biome(path)
                if width and profile.line_length is None:
                    profile.line_length = width
        for filename, tool in LINTER_NAMES.items():
            if context.find_named(filename) is not None and tool not in linters:
                linters.append(tool)

        editorconfig_path = context.find_named(".editorconfig")
        if editorconfig_path is not None:
            profile.editorconfig = _parse_editorconfig(editorconfig_path)

        ruff_path = context.find_named("ruff.toml") or context.find_named(".ruff.toml")
        if ruff_path is None:
            ruff_path = context.find_named("pyproject.toml")
            ruff_line_length, ruff_import_sorting = _parse_ruff(ruff_path) if ruff_path else (None, None)
        else:
            ruff_line_length, ruff_import_sorting = _parse_ruff(ruff_path)
        if ruff_line_length and profile.line_length is None:
            profile.line_length = ruff_line_length
        if ruff_import_sorting is True:
            profile.import_sorting = True

        flake8_path = context.find_named(".flake8")
        if flake8_path is not None:
            flake8_length = _parse_flake8(flake8_path)
            if flake8_length and profile.line_length is None:
                profile.line_length = flake8_length

        if profile.line_length is None and profile.editorconfig and profile.editorconfig.max_line_length:
            profile.line_length = profile.editorconfig.max_line_length

        if profile.import_sorting is None:
            profile.import_sorting = any(tool in IMPORT_SORT_LINTERS for tool in linters)

        profile.formatters = sorted(formatters)
        profile.linters = sorted(linters)
        found = bool(profile.formatters or profile.linters or profile.editorconfig)
        if found:
            profile.confidence = (
                ConfidenceLevel.HIGH if len(profile.formatters) + len(profile.linters) >= 2 else ConfidenceLevel.MEDIUM
            )
        else:
            profile.notes.append("no linter or formatter configuration detected")
            profile.confidence = ConfidenceLevel.LOW
        return profile
