# Windows Desktop Shell & Document Conversion Invariants

## 1. Explorer Context Menu & Subsystem Invariant
- Every executable or script registered under Explorer context menu verbs (`HKCU\Software\Classes\*\shell\*`) MUST be a Windows GUI subsystem application (`/SUBSYSTEM:WINDOWS`).
- Python entrypoints registered in Explorer must use `[project.gui-scripts]` or `pythonw.exe`. Never register `[project.scripts]` console wrappers.
- The C++ native launcher (`cuttlectl.exe`) is the primary context menu target and must always handle `install-shell` and `uninstall-shell` commands cleanly.

## 2. Named Pipe Burst Invocations
- When a user multi-selects $N$ files in Explorer, Windows invokes $N$ launcher instances concurrently.
- All IPC clients communicating over Windows Named Pipes must implement retry loops on `ERROR_PIPE_BUSY` (231) and `ERROR_FILE_NOT_FOUND` (2) with a minimum 5-second timeout.
- The worker Named Pipe server must handle rapid back-to-back connection bursts without connection loss.

## 3. Image Preservation In PDF -> Word
- In PDF to DOCX conversions, distinct images (different xrefs or separate bounding boxes) must retain their individual identity and original resolution.
- Never flatten multiple distinct images on a page into a composite page-region bitmap.

## 4. Microsoft Word COM Automation Performance
- When automating Word via COM, always set `word.Visible = False`, `word.DisplayAlerts = 0`, and `word.ScreenUpdating = False`.
- Suppress all template saves, recent files, and conversion confirmation dialogs.
