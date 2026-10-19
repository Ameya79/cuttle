# Changelog

All notable changes to Cuttle will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.4.0] - Phase 4: Windows 11 Top-Level Context Menu & Native Speed

### Added
- **Native Windowless Launcher (P4-01)**: `cuttle/platform/windows/launcher/main.cpp` compiled into a native C++ executable (`cuttlectl.exe`) with median start-to-pipe latency of 25.98 ms (exceeding the 100 ms requirement).
- **IExplorerCommand COM Server (P4-02)**: `cuttle/platform/windows/shell_extension/` in-process COM DLL (`cuttle_shell.dll`) implementing `IExplorerCommand`, `IEnumExplorerCommand`, and `IClassFactory` with full exception isolation.
- **Dynamic Context Submenu (P4-03)**: Dynamic verb enumeration filtering available targets per file type and `GetFlags` returning `ECF_HASSUBCOMMANDS` for submenus.
- **Sparse Package Manifest & Registration (P4-04)**: `packaging/AppxManifest.xml` declaring the `windows.fileExplorerContextMenus` extension with package identity, plus PowerShell registration (`scripts/register_sparse_package.ps1`) and unregistration scripts.
- **Developer Documentation (P4-04)**: `docs/dev-windows-shell.md` explaining Windows 11 sparse package mechanics, registration, and debugging.
- **Crash Safety & Speed Verification (P4-05 & P4-06)**: `tests/integration/test_windows11_shell_pipeline.py` verifying Explorer never hangs when worker is dead and end-to-end latency is 23.93 ms (< 1 second budget).
- **Phase 4 Exit Gate (P4-07)**: Full test suite passing across all 310 tests, 0 `.cuttle-part` leaks, clean Ruff, Mypy, and Pyright.

## [0.3.0] - Phase 3: Documents & PDFs

### Added
- **Pandoc Adapter (P3-01)**: `cuttle/adapters/pandoc.py` converting text documents (`md`, `html`, `docx`, `txt`) with explicit `-f`/`-t` arguments, `--sandbox` flag detection, standalone HTML documents (`-s`), and DOCX component validation.
- **Office Detection (P3-02)**: `cuttle/platform/windows/office_detect.py` searching Windows App Paths registry (`soffice.exe`), `PATH`, and standard `ProgramFiles` directories.
- **LibreOffice Adapter (P3-03)**: `cuttle/adapters/libreoffice.py` converting Office documents (`docx`, `pptx`, `xlsx`, `odt`) to `pdf` via headless `soffice.exe`, using private isolated profile directories, single-concurrency lock (`_LIBREOFFICE_LOCK`), 120s timeout, and PDF validation.
- **Office Document & PDF Validators (P3-04)**: `cuttle/engine/validators.py` and `cuttle/adapters/pdf.py` verifying valid OpenXML zip structures, component parts, and pypdf page rendering.
- **Font Substitution Warning & Locked PDFs (P3-05)**: `cuttle/adapters/pdf.py` comparing DOCX `fontTable.xml` with PDF `/Resources/Font` to issue `"Some fonts were replaced, layout may shift"`, detecting encrypted PDFs and enforcing passwords (`E_SRC_PASSWORD`).
- **Folder Conversion Engine & CLI (P3-06)**: `cuttle/engine/folder.py` supporting directory conversions with recursive scanning, extension filtering, `(converted)` skipping, and symlink/junction escape guards (`--recursive`, `--filter`).
- **Missing LibreOffice Guidance UI (P3-07)**: `cuttle/ui/missing_tool_dialog.py` displaying clear requirement dialog with official download link and "Re-check" button to automatically refresh context menus upon install.
- **Explorer Menu Missing Tool Routing & Terminal Auto-Close Fix (P3-08)**: `cuttle/shell/registry_installer.py` labeling missing tools as `"Convert to PDF (needs LibreOffice)"` launching guidance dialog, and launching right-click commands via `pythonw.exe` / `cuttlectl.exe` with `CREATE_NO_WINDOW | DETACHED_PROCESS` and stdio redirection to `DEVNULL` to prevent persistent console windows.
- **Document Integration Verification (P3-09)**: `tests/integration/test_document_pipeline.py` and full test suite passing (300 tests) with 0 `.cuttle-part` file leaks, clean ruff linter/formatter, and strict mypy compliance.

## [0.2.0] - Phase 2: Windows Desktop Integration & Background Worker

### Added
- **Windows Job Object process tree termination (P2-01)**: `cuttle/platform/windows/jobobject.py` wrapping Win32 Job Objects with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` to guarantee instantaneous child and grandchild process termination on cancellation or exit.
- **SQLite state database & startup recovery (P2-02)**: `cuttle/worker/db.py` in WAL mode managing `%LOCALAPPDATA%\Cuttle\state.db`, with crash recovery marking orphaned interrupted jobs as failed (`E_TOOL_FAILED`).
- **Job queue & concurrency controller (P2-03)**: `cuttle/worker/queue.py` capping parallel conversions to half of CPU cores, providing isolated failure containment and token-based cancellation.
- **Named pipe IPC server & 300ms multi-select batching (P2-04)**: `cuttle/platform/windows/pipe.py` and `cuttle/worker/pipe_server.py` supporting sub-10ms IPC on `\\.\pipe\cuttle-<username>` and bundling rapid Explorer multi-select clicks into unified batches.
- **Fast launcher cuttlectl (P2-05)**: `cuttle/worker/cuttlectl.py` sub-20ms right-click launcher with auto-start of detached worker daemon and pipe communication.
- **Floating progress window (P2-06)**: `cuttle/ui/progress_window.py` PySide6 dark frameless floating window positioned at bottom-right displaying per-job and batch progress bars with individual and batch cancellation buttons.
- **Native Windows toast notifications (P2-07)**: `cuttle/platform/windows/toast.py` using `windows-toasts` with interactive quick-action buttons ("Open File", "Show in Folder", "Copy Details") and graceful exception fallback.
- **File Explorer registry installer (P2-08)**: `cuttle/shell/registry_installer.py` dynamically registering cascading context menus in `HKCU\Software\Classes` (zero admin rights) with leave-no-trace uninstallation via audit manifest.
- **System tray icon & settings (P2-09)**: `cuttle/worker/tray.py` and `settings.py` providing background tray presence with real-time conversion status, `settings.toml` store, and zero-admin Windows Run autostart.
- **Packaging & Inno Setup installer (P2-10)**: `packaging/cuttle.spec` for standalone PyInstaller freeze of `cuttle.exe`, `cuttlectl.exe` (windowless), and `cuttle-worker.exe` (windowless daemon), plus `packaging/installer.iss` for automated setup and clean uninstallation.
- **Windows integration verification (P2-11)**: `tests/integration/test_windows_pipeline.py` validating end-to-end multi-file debouncing, parallel queue execution, live progress events, and clean registry removal.

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
