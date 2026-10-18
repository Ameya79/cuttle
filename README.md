# Cuttle

**Right-click any file, pick the format you want, get a converted copy next to the original.**
No app to open, no upload, no sign-up. Offline, open-source, free.

## Status

Phase 1 — building the core conversion engine as a CLI tool (video, audio, images).

## What it does

Cuttle wraps free, battle-tested tools (FFmpeg, Pandoc, Pillow, and later LibreOffice)
behind a simple Windows right-click menu. Your files never leave your computer.

- **Original is sacred** — never modified, moved, or deleted
- **Never overwrites** — if the name exists, it adds a number
- **Honest quality labels** — every conversion is tagged Lossless, Lossy, or Best effort
- **Shows only what makes sense** — a video shows audio/video targets, never "to Word"
- **Plain-English errors** — "This PDF has a password", never `Error 0x8007`

## Quick start (Phase 1 — CLI only)

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- FFmpeg + ffprobe in `vendor/` (run `uv run python scripts/fetch_tools.py`)

### Install

```bash
uv sync
```

### Usage

```bash
# Convert a video to MP3
uv run cuttle convert --to mp3 video.mp4

# See what formats a file can be converted to
uv run cuttle targets video.mp4

# List all known formats and conversions
uv run cuttle formats

# Check which tools are available
uv run cuttle doctor
```

### Run tests

```bash
# Generate test fixtures first
uv run python tests/make_fixtures.py

# Run all tests
uv run pytest

# Lint and type-check
uv run ruff check .
uv run mypy cuttle/engine
```

## License

GPL-3.0 — see [LICENSE](LICENSE).
