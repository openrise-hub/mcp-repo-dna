# mcp-repodna

An MCP server and CLI that analyzes a public repository to extract its holistic
engineering culture and compiles it into artifacts for autonomous AI coding
agents:

- `skills.sh`: an executable bash script encoding the repository's conventions
  as runnable checks (commit style, branch naming, lint, format, typecheck, test)
- `rules.md`: a markdown context document summarizing the repository's
  engineering DNA for LLM system prompts

The analyzer inspects six dimensions: git conventions, architecture, linting and
formatting, tooling, test semantics, and governance.

## Installation

Requires Python 3.12+ and git on PATH.

```bash
uv tool install mcp-repodna
# or, from this checkout
uv sync
```

## CLI usage

```bash
# Analyze a repository and print a summary table
mcp-repodna analyze https://github.com/org/repo

# Analyze and emit the full DNA model as JSON
mcp-repodna analyze https://github.com/org/repo --json

# Analyze and write skills.sh plus rules.md into ./repodna
mcp-repodna compile https://github.com/org/repo --output ./repodna

# Adjust how much commit history is fetched (default 100)
mcp-repodna analyze https://github.com/org/repo --history-depth 500

# Print the JSON schema of the DNA model
mcp-repodna schema

# Start the MCP server over stdio
mcp-repodna serve
```

Local paths work too:

```bash
mcp-repodna analyze ../my-project --json
```

## MCP server

The server exposes four tools and two resources over stdio.

Tools:

- `analyze_repository(repo_url, history_depth, output_dir)`: returns the DNA
  model as JSON, optionally writing skills.sh and rules.md
- `generate_skills(repo_url, output_dir, history_depth)`: writes both artifacts
- `analyze_dimension(repo_url, dimension, history_depth)`: returns one dimension
  as JSON
- `list_dimensions()`: lists the six dimension names

Resources:

- `dna://schema`: JSON schema of the RepoDNA model
- `dna://dimensions`: JSON list of dimension names

Example client configuration:

```json
{
  "mcpServers": {
    "repodna": {
      "command": "mcp-repodna",
      "args": ["serve"]
    }
  }
}
```

## DNA dimensions

| Dimension | Detects |
|-----------|---------|
| git | conventional commit ratio, merge strategy, branch prefixes, default branch |
| architecture | src vs flat vs monorepo layout, test placement, typing strictness, dependency manager |
| linters | ruff, eslint, prettier, biome, flake8, editorconfig, line length, import sorting |
| tooling | Makefile targets, npm scripts, Taskfile, pre-commit hooks, CI systems |
| testing | pytest, jest, vitest, mock libraries, assertion grammar, snapshots, coverage |
| governance | PR template, CONTRIBUTING, ADRs, CODEOWNERS, SECURITY, issue templates |

Every dimension carries a confidence level (low, medium, high) and notes when
evidence is missing.

## Generated artifacts

`skills.sh` provides guarded functions:

- `dna:commit <subject>`: validates conventional commit subjects when detected
- `dna:branch <name>`: validates branch prefixes when detected
- `dna:lint`, `dna:format`, `dna:typecheck`, `dna:test`: run the detected tools
- `dna:install-hooks`: installs pre-commit when configured
- `dna:preflight`: runs all checks as a submission gate

`rules.md` renders the same DNA as a rule sheet for system context.

## Development

```bash
uv sync           # install dependencies with Python 3.12
uv run pytest     # run the test suite
uv run ruff check .   # lint
```

The test suite builds a synthetic git repository in a temp directory and
asserts every extractor, the pipeline, the compiler, and the MCP server against
it. No network access is required.

## License

Distributed under the Apache License 2.0. See the LICENSE file. This project
itself follows the conventions it detects: conventional commits, ruff linting,
pytest with pytest-mock, and pre-commit hooks.
