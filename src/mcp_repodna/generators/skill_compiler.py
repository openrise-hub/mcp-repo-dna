"""Renders the DNA model into skills.sh and rules.md via Jinja2 templates."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from mcp_repodna.models.dna import RepoDNA

TEMPLATE_DIR = Path(__file__).parent / "templates"

SKILLS_TEMPLATE = "skills.sh.j2"
RULES_TEMPLATE = "rules.md.j2"


def build_commands(dna: RepoDNA) -> dict[str, list[str]]:
    """Derive executable lint, format, typecheck, and test commands from DNA."""
    linters = set(dna.linters.linters)
    formatters = set(dna.linters.formatters)
    commands: dict[str, list[str]] = {
        "lint": [],
        "format": [],
        "typecheck": [],
        "test": [],
    }

    if "ruff" in linters:
        commands["lint"].append("ruff check .")
    if "eslint" in linters:
        commands["lint"].append("eslint .")
    if "flake8" in linters:
        commands["lint"].append("flake8")
    if "biome" in linters:
        commands["lint"].append("biome check .")

    if "ruff" in formatters:
        commands["format"].append("ruff format --check .")
    if "prettier" in formatters:
        commands["format"].append("prettier --check .")
    if "biome" in formatters:
        commands["format"].append("biome check .")

    if dna.architecture.type_strictness and dna.architecture.type_strictness.startswith("tsconfig"):
        commands["typecheck"].append("npx tsc --noEmit")
    elif dna.architecture.type_strictness and dna.architecture.type_strictness.startswith("mypy"):
        commands["typecheck"].append("mypy .")
    elif dna.architecture.type_strictness and dna.architecture.type_strictness.startswith("pyright"):
        commands["typecheck"].append("pyright")

    if dna.testing.runner == "pytest":
        if dna.testing.coverage_tools and "pytest-cov" in dna.testing.coverage_tools:
            commands["test"].append("pytest --cov")
        else:
            commands["test"].append("pytest")
    elif dna.testing.runner == "vitest":
        commands["test"].append("vitest run")
    elif dna.testing.runner == "jest":
        commands["test"].append("jest")

    return commands


@dataclass
class CompilationResult:
    """Rendered artifacts: an executable skills script and a rules document."""

    skills_script: str
    rules_markdown: str

    def write(self, output_dir: Path) -> list[Path]:
        """Write artifacts to disk and return the created paths."""
        output_dir.mkdir(parents=True, exist_ok=True)
        skills_path = output_dir / "skills.sh"
        rules_path = output_dir / "rules.md"
        skills_path.write_text(self.skills_script, encoding="utf-8", newline="\n")
        rules_path.write_text(self.rules_markdown, encoding="utf-8", newline="\n")
        with suppress(OSError):  # pragma: no cover - Windows does not support chmod modes
            skills_path.chmod(0o755)
        return [skills_path, rules_path]


def compile_dna(dna: RepoDNA) -> CompilationResult:
    """Render both artifacts for a DNA model."""
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    branch_prefixes = [p for p in dna.git.branch_conventions if p != "plain"]
    context = {
        "dna": dna,
        "commands": build_commands(dna),
        "branch_prefixes": branch_prefixes,
    }
    skills = environment.get_template(SKILLS_TEMPLATE).render(context)
    rules = environment.get_template(RULES_TEMPLATE).render(context)
    return CompilationResult(skills_script=skills, rules_markdown=rules)
