# AGENTS.md

Project: Cuttle, a Windows right-click file converter (offline, GPL-3.0).
Source of truth: docs/SPEC.md. Read Part 0 and Part 6 before any change.

## Commands
- Install:    uv sync
- Tests:      uv run pytest
- Lint:       uv run ruff check . && uv run ruff format --check .
- Types:      uv run mypy cuttle/engine
- Fixtures:   uv run python tests/make_fixtures.py
- Tools:      uv run python scripts/fetch_tools.py
- Doctor:     uv run cuttle doctor

## Rules
- Work on one task card at a time. Commit message: 'P1-03: short description'.
- Never overwrite or modify source files. Never shell=True. Engine makes no network calls.
- Conversions come from cuttle/registry/*.toml, not if-chains.
- Engine has no OS specific code. Windows code only in cuttle/platform/windows and cuttle/shell.
- No new dependencies without asking. Stdlib and the list in SPEC 6.1 only.
- If the spec is unclear, ask. Mark anything not verified on real Windows as UNVERIFIED.
- Keep changes minimal. Do not reformat or rewrite files you were not asked to change.

## Done means
Tests pass, ruff and mypy clean, no .cuttle-part files left by tests, source hashes unchanged.
