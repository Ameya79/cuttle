# Project Naming: Cuttle

The app is called **Cuttle**. The planning documents use the old working name "Morph" — treat every occurrence of "Morph" in the specs as meaning "Cuttle".

When writing code, documentation, commit messages, CLI names, registry keys, pipe names, config paths, or any user-facing text:
- Use **Cuttle** (capital C) as the product name.
- Use **cuttle** (lowercase) for package names, CLI entry points, file paths, and identifiers.
- Never use "Morph" or "morph" in new code or docs unless quoting the original spec for reference.

Examples:
- Package: `cuttle/` not `morph/`
- CLI command: `cuttle convert --to mp3 file.mp4`
- Config path: `%APPDATA%\Cuttle`
- State path: `%LOCALAPPDATA%\Cuttle`
- Named pipe: `\\.\pipe\cuttle-<username>`
- Temp file suffix: `.cuttle-part` not `.morph-part`
- Registry keys: `...\shell\Cuttle`
- Window title, toasts, tray icon: "Cuttle"
