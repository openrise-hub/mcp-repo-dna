"""PR templates, CONTRIBUTING guides, and ADR inspection."""

from __future__ import annotations

import re
from pathlib import Path

from mcp_repodna.extractors.base import BaseExtractor, RepoContext
from mcp_repodna.models.dna import ConfidenceLevel, GovernanceProfile

PR_TEMPLATE_NAMES = {
    "pull_request_template.md",
    "pull_request_template.rst",
    "PULL_REQUEST_TEMPLATE.md",
    "PULL_REQUEST_TEMPLATE.rst",
    "pull_request_template",
    "PULL_REQUEST_TEMPLATE",
}

CONTRIBUTING_NAMES = {
    "contributing.md",
    "CONTRIBUTING.md",
    "contributing.rst",
    "CONTRIBUTING.rst",
}

CONDUCT_NAMES = {
    "code_of_conduct.md",
    "CODE_OF_CONDUCT.md",
}

ADR_DIR_CANDIDATES = (
    "adr",
    "adrs",
    "docs/adr",
    "docs/adrs",
    "docs/architecture/decisions",
    "doc/adr",
    "doc/architecture/adr",
    "decisions",
)

ADR_FILE_RE = re.compile(r"^\d{4}-.+\.md$")

MAX_ISSUE_TEMPLATES = 20


class GovernanceExtractor(BaseExtractor):
    """Inspect PR templates, CONTRIBUTING guides, and ADR directories."""

    name = "governance"

    def extract(self, context: RepoContext) -> GovernanceProfile:
        profile = GovernanceProfile()

        profile.pr_template = self._any_exists(context, PR_TEMPLATE_NAMES)
        profile.contributing_guide = self._any_exists(context, CONTRIBUTING_NAMES)
        profile.code_of_conduct = self._any_exists(context, CONDUCT_NAMES)
        profile.code_owners = bool(
            context.find_named("CODEOWNERS") or any(path.name == "CODEOWNERS" for path in context.sample.files)
        )
        profile.security_policy = bool(context.find_named("SECURITY.md"))

        adr_dir = self._adr_directory(context)
        if adr_dir is not None:
            profile.adr_directory = Path(adr_dir).as_posix()
            profile.adr_count = sum(
                1
                for path in context.sample.files
                if ADR_FILE_RE.match(path.name) and Path(adr_dir) in path.relative_to(context.sample.root).parents
            )

        profile.issue_templates = self._issue_templates(context)

        evidence = sum(
            (
                profile.pr_template,
                profile.contributing_guide,
                bool(profile.adr_directory),
                profile.code_owners,
                profile.security_policy,
                bool(profile.issue_templates),
            )
        )
        if evidence >= 2:
            profile.confidence = ConfidenceLevel.HIGH
        elif evidence == 1:
            profile.confidence = ConfidenceLevel.MEDIUM
        else:
            profile.notes.append("no governance artifacts detected")
            profile.confidence = ConfidenceLevel.LOW
        return profile

    @staticmethod
    def _any_exists(context: RepoContext, names: set[str]) -> bool:
        return any(context.find_named(name) is not None for name in names)

    @staticmethod
    def _adr_directory(context: RepoContext) -> Path | None:
        for candidate in ADR_DIR_CANDIDATES:
            if context.exists(candidate):
                return Path(candidate)
        return None

    @staticmethod
    def _issue_templates(context: RepoContext) -> list[str]:
        if not context.exists(".github/ISSUE_TEMPLATE"):
            return []
        templates: list[str] = []
        for path in context.sample.files:
            if ".github" not in path.parts:
                continue
            idx = path.parts.index(".github")
            if len(path.parts) > idx + 2 and path.parts[idx + 1] == "ISSUE_TEMPLATE":
                templates.append(path.name)
                if len(templates) >= MAX_ISSUE_TEMPLATES:
                    break
        return templates
