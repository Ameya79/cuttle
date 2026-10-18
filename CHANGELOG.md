# Changelog

All notable changes to Cuttle will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - Phase 1: Core Engine & CLI

### Added
- **Project skeleton (P1-01)**: Package structure, pyproject.toml, CI workflow with ruff and mypy.
- **Tool fetcher (P1-02)**: SHA-256 verified tool downloader (`scripts/fetch_tools.py`, `scripts/tools.lock.toml`).
- **Engine types & errors (P1-03)**: Core dataclasses (`Plan`, `Target`, `Edge`, `ConvertResult`), quality enums, and structured error codes (`CuttleError`).
- **Format registry & conversion graph (P1-04)**: TOML format registry (`formats.toml`, `edges.toml`) with direct edge priority, 2-hop quality aggregation, and 3-hop exclusion.
- **Format detection (P1-05)**: Magic-bytes detection first with extension fallback, disagreement warnings, and corrupt file detection (`detect.py`).
- **Synthetic test fixtures (P1-06)**: Automated fixture generator (`tests/make_fixtures.py`) creating golden media files and hostile edge cases (zero byte, truncated, Unicode, symbols, long path, locked).
- **Safe output pipeline (P1-07)**: Safe collision naming (`(converted)`, `(2)`), pre-flight disk space checking (2x source), atomic commit, and `.cuttle-part` cleanup on exit.
- **Process execution runner (P1-08)**: Threaded non-blocking streaming process runner with timeouts, cancellation, and recursive process-tree termination via psutil.
- **FFmpeg adapter (P1-09)**: Audio/video conversion recipes (MP3, WAV, MP4, WebM, GIF) with monotonic progress streaming and duration validation.
- **Image adapter (P1-10)**: Pillow + `pillow-heif` conversion (PNG, JPG, WebP, BMP, TIFF, HEIC, GIF) with EXIF orientation preservation, alpha flattening to white for JPG/BMP, and full decode validation.
- **Engine conversion pipeline (P1-11)**: End-to-end 9-step conversion coordinator (`convert.py`) with source immutability verification and target listing.
- **Typer CLI (P1-12)**: Command-line interface with `convert`, `targets`, `formats`, and `doctor`, exit codes 0/1/2/3, and `--json` NDJSON streaming.
- **Extreme edge-case test suite (P1-13)**: 170 unit and integration tests passing with 0 `.cuttle-part` leaks and verified source immutability.
