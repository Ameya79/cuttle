# Windows Desktop Daemon Invariants

1. **Qt Event Loop Persistence**:
   - For any background worker using PySide6/Qt for system tray and floating dialogs, always explicitly execute:
     ```python
     app = get_or_create_app()
     app.setQuitOnLastWindowClosed(False)
     ```
   - Never rely on the default `quitOnLastWindowClosed=True`, or the process will exit the moment a transient dialog closes.

2. **Explorer View Refresh (`SHChangeNotify`)**:
   - Whenever an output file is committed to disk, notify Windows Explorer using `SHChangeNotify(SHCNE_CREATE, SHCNF_PATHW, path)` so the file appears immediately without requiring an F5 refresh.

3. **Shell Context Menu Process Launch**:
   - When `cuttlectl` auto-starts the worker daemon, explicitly pass `cwd=str(project_root)` and `env["PYTHONPATH"] = str(project_root)` so daemon paths resolve reliably regardless of which folder the user right-clicked in.
