Morph: Right-Click File Converter
Working name: Morph (placeholder, rename freely). Status: draft v1. Platform for v1:
Windows 10/11. Open source, offline, free.
Part 0: Read this first (instructions for the AI
coding agent)
This doc is the single source of truth for building Morph. Part 0 is your operating manual.
Part 6 holds the exact interfaces, schemas, commands and one task card per step. If this
doc is silent or unclear, stop and ask the human. Do not guess formats, flags or
dependencies.
Working rules
1. Build one phase at a time, in the order of Part 3. Do not start a phase until the previous
phase's exit test passes.
2. Inside a phase, do the task cards in Part 6 in order. One task card = one small commit.
3. Before writing code for a task, read its card, the interface it touches (Part 6.2), and the
matching TRD section.
4. Do not add a dependency that is not listed in Part 6.1. Ask first.
5. Every task ends with tests written and passing, ruff and mypy clean, and the card
ticked.
6. Engine code never contains OS specific code. Windows code lives only in
morph/platform/windows/ and morph/shell/ .
7. Anything that touches Explorer, the registry, installers or signing must be verified on a
real Windows machine or VM. If you could not verify it, say so plainly. Never claim it
works untested.
8. Prefer small, precise changes. Do not rewrite or reformat files you were not asked to
touch.
Locked decisions (do not change without asking)
Area
Decision
Platform
Windows 10 and 11, x64 only for v1
Language
Python 3.12
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 1 of 34
Hard rules (never break)
Never modify, move or delete a source file. Open sources read only.
Never overwrite an existing file. Always pick a free name.
Never use shell=True . Pass argument lists only.
The engine makes no network calls.
Always pass the output format to FFmpeg explicitly with -f , because output goes to a
temp file with a custom extension.
No global mutable state in the engine. Use logging , never print , outside the CLI
layer.
Every external tool call has a timeout and runs inside a Windows Job Object (Phase 2
on) so child processes die with it.
Formats and conversions come from the registry files, never from if chains in code.
Definition of done
Task: code, tests and docstrings written. uv run pytest , uv run ruff check . , uv
run mypy morph/engine all pass. The task card is ticked.
Phase: every task card ticked, the exit test in Part 3 passes, CI is green, CHANGELOG.md
updated, git tag v0.<phase>.0 created.
Area
Decision
Env and deps
uv and pyproject.toml
Lint, types, tests
ruff , mypy --strict on morph/engine , pytest
CLI
typer
UI (Phase 2 on)
PySide6
Config
TOML in %APPDATA%\Morph
State
SQLite in %LOCALAPPDATA%\Morph
Helper IPC
Windows named pipe, one JSON object per line
Packaging
PyInstaller --onedir , then Inno Setup installer
Video encoding
software only (libx264, libvpx-vp9) in v1
License
GPL-3.0
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 2 of 34
How to start
1. Export this doc as Markdown and commit it as docs/SPEC.md .
2. Create AGENTS.md at the repo root using the block in Part 6.12.
3. Give the agent the kickoff prompt for the current phase from Part 6.11.
Part 1: PRD (Product Requirements)
1. One line
Right-click any file or folder, pick the format you want, and get a converted copy next to
the original. No app to open, no upload, no sign-up.
2. The problem
Everyone needs to convert files sometimes: PDF to Word, MP4 to MP3, HEIC to JPG,
DOCX to PDF, a drawing to PDF. Today people pick one of three bad options:
Upload the file to a random website. This is slow, has size limits, shows ads, and sends
private files (IDs, contracts, drawings) to a stranger's server.
Install a heavy app (Adobe, Wondershare) that is paid and opens a whole interface for a
5 second job.
Google 'free converter' every single time, and hope the result is not corrupted or full of
malware.
The real tools (FFmpeg, Pandoc, LibreOffice, ImageMagick) are free and excellent, but
they are command line tools. Nobody outside developers can use them. Morph is the
missing friendly layer: one right-click menu on top of those engines.
3. Target users
Primary: students and office or admin staff on Windows. Not technical. Want it to just
work.
Secondary: freelancers, content creators (video and audio), engineers and architects
(DWG, CAD files).
Tertiary: developers who want a batch converter without writing ffmpeg commands.
4. Goals and non-goals
Goals:
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 3 of 34
Convert common files in one click from the right-click menu.
Never damage or overwrite the original file.
Work fully offline. Files never leave the machine.
Be honest when a conversion is lossy or best effort.
Be installable by a non-technical person in under a minute.
Non-goals for v1:
Editing files (no cropping, trimming, merging UI).
Cloud features, accounts, or sync.
Mobile apps.
Perfect PDF to Word. This is not solvable in general, so we promise 'best effort' only.
Supporting every format on earth. We support a clear list and grow it.
5. Product principles
1. The original is sacred. Output is always a new file. We never overwrite.
2. Offline by default. No network calls unless the user explicitly asks (for example,
downloading an optional add-on).
3. Honest quality labels. Each conversion is tagged Lossless, Lossy, or Best effort, and the
user sees it.
4. Show only what makes sense. A video shows audio and video targets, never 'to Word'.
5. Never freeze Explorer. All work happens in a separate background process.
6. Fail clearly. When something fails, say what and why in plain words, and keep the log.
6. Feature list by priority
P0 (launch):
Right-click menu on files with a 'Convert to' submenu that lists only valid targets.
Video and audio: mp4, mkv, mov, avi, webm to mp4, mp3, wav, gif, webm. Audio
extraction from video.
Images: png, jpg, webp, heic, bmp, tiff, gif. Convert between them. Resize presets.
Documents: docx, pptx, xlsx, odt to PDF. Markdown, html, docx, txt via Pandoc.
Multi-select: select 10 files, convert all to one target.
Folder support: right-click a folder to convert everything inside (with a type filter).
Progress window and a 'Done' notification with 'Open file' and 'Show in folder'.
Safe output naming: report (converted).pdf , never overwriting.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 4 of 34
Installer plus portable zip.
P1 (soon after launch):
PDF to Word (text based PDFs), PDF to images, images to PDF, merge multiple images
into one PDF.
Windows 11 top-level menu entry (not hidden under 'Show more options').
Presets (for example 'WhatsApp friendly video', 'Email size PDF').
Settings: output folder rule, naming rule, concurrency, quality defaults.
OCR for scanned PDFs.
P2 (later):
DWG to PDF/DXF/SVG (best effort, see TRD).
macOS Quick Actions, Linux file manager integration.
Plugin system so the community can add converters.
Archive conversions (zip, 7z, rar to zip).
7. Key user stories and acceptance criteria
Story A: 'I have a video and I want only the audio.'
Right-click the .mp4, open Convert to, click MP3.
A small progress toast appears within 1 second of the click.
An .mp3 appears next to the video. A notification offers Open and Show in folder.
Acceptance: audio duration matches the video within 1 percent. Original untouched.
Story B: 'I have 30 phone photos in HEIC and my college portal wants JPG.'
Select all 30, right-click, Convert to, JPG.
One combined progress window shows 30 of 30, not 30 popups.
Acceptance: all 30 outputs open correctly. If 2 fail, the summary names those 2 and
why.
Story C: 'I have a Word file and need a PDF.'
Right-click, Convert to PDF. If LibreOffice is not installed, offer a one-time optional
download (clearly shown with size) or use installed Microsoft Word if present.
Acceptance: page count matches. Fonts are embedded. A warning is shown if fonts
were substituted.
Story D: 'The conversion failed.'
The user sees a plain message ('This PDF is password protected. Enter the password to
continue.') and a 'Copy details' button for bug reports.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 5 of 34
Acceptance: no partial or half written output file is ever left behind.
8. UX specification
Right-click menu:
One top level entry: 'Morph' (with icon). Inside: 'Convert to' with a list of valid formats,
then 'More options...' that opens the settings or advanced window.
Max 8 items shown. Most used first. Others under 'More formats'.
Each item shows the quality label in muted text, for example 'DOCX (best effort)'.
Progress:
A small always-on-top window in the bottom right, not a full app window. Shows file
name, percent (or a moving bar if progress is unknown), cancel button.
Multiple jobs stack in the same window.
Result:
Windows toast: 'Converted report.pdf. Open | Show in folder'.
If a warning applies (lossy, fonts missing, tables may shift), the toast has a 'Details' link.
Settings (small, one page):
Output location: next to original (default) or a chosen folder.
Naming: '(converted)' suffix or custom.
Parallel jobs: auto, 1, 2, 4.
Delete original after success: OFF by default and hidden behind an advanced toggle.
Check for updates: ON by default (only contacts GitHub).
First run:
A 3 step screen: what it does, where to find it (animated right-click demo), optional
add-ons.
Accessibility:
Keyboard navigable windows, clear contrast, no color-only status.
9. Success metrics
Time from click to first visible feedback under 1 second.
Conversion success rate above 98 percent on the supported matrix test corpus.
Zero reports of overwritten or deleted originals.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 6 of 34
500 GitHub stars and 1,000 installs in the first 3 months (realistic open source goal,
adjust later).
Crash-free sessions above 99 percent (from opt in local logs and issue reports).
10. Licensing decision
FFmpeg builds with H.264 encoding (libx264) are GPL. Pandoc is GPL. Running them as
separate programs is allowed, but the simplest safe path is to license Morph under
GPL-3.0 and ship the required notices and source links. This is a practical suggestion,
not legal advice. Read each license before release.
ODA File Converter (DWG) cannot be freely redistributed. Do not bundle it. See TRD.
Part 2: TRD (Technical Requirements)
1. Architecture overview
Three layers, kept separate so each can be tested and replaced:
1. Shell layer: the right-click menu. Thin and dumb. It only says 'convert these paths to
this format' and hands off.
2. Core engine (Python): detects file types, decides which tool to use, runs it safely,
validates the result.
3. Tool adapters: wrappers around FFmpeg, Pandoc, LibreOffice, Pillow/ImageMagick,
pdf2docx, Tesseract, LibreDWG.
Flow:
Explorer menu click calls morph.exe convert --to mp3 <paths> .
The launcher sends the job to the background worker (a tray process) over a named
pipe. If the worker is not running, it starts it.
The worker creates jobs, runs them with limited concurrency, streams progress to the
progress window, and writes results.
2. Technology choices
Engine and worker: Python 3.12. Fast for you to build, huge ecosystem. Package with
PyInstaller (onedir mode, not onefile, because onefile unpacks to temp on every launch
and is slow) or Nuitka for faster startup.
Progress UI and settings: PySide6 (Qt) for a small native feeling window. Alternative:
Tauri if you later want a smaller footprint.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 7 of 34
Shell extension: classic registry verbs for Phase 2. A small C# or C++ COM DLL
implementing IExplorerCommand, plus a sparse MSIX package for package identity, for
the Windows 11 top level menu in Phase 4.
Job state: SQLite in %LOCALAPPDATA%\Morph.
Config: TOML in %APPDATA%\Morph.
Toasts: Windows toast via the winrt bindings or a small helper library.
CI: GitHub Actions on windows-latest.
3. Conversion graph
Model formats as nodes and converters as edges in a registry file (TOML or YAML), not
hardcoded if statements.
Each edge has: source format, target format, adapter name, quality label (lossless, lossy,
best effort), estimated cost, and requirements (for example 'needs LibreOffice').
Menu building: for a given input type, list all edges from that node.
Multi hop: allow at most 2 hops (for example docx to pdf to png), and label the result
with the worst quality of the chain.
Adding a format means adding an edge, not touching the engine.
File type detection: read magic bytes (using a library such as filetype or python-magic),
not just the extension. Extensions lie, and a renamed file is a common cause of failures.
4. Adapter contract
Every adapter implements the same four functions:
can_convert(src_type, dst_type) : yes or no, plus the quality label.
plan(src, dst, options) : returns the exact command as an argument list.
run(plan, on_progress, cancel_token) : runs it, reports progress, honors cancel.
validate(output) : checks the output is sane.
Rules:
Never use shell=True . Always pass argument lists. File names can contain spaces,
quotes, and unicode.
Every run has a timeout and is attached to a Windows Job Object so that killing the job
kills the whole process tree (LibreOffice spawns children).
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 8 of 34
5. Safe output pipeline (the 'never corrupt' promise)
We cannot promise perfect conversions. We can promise the following, and must test
each:
1. The source is opened read only. It is never modified.
2. Output is written to a temp file in the same folder, for example report.pdf.morph-
part .
3. After the tool exits successfully, the validator runs (see below).
4. Only if validation passes, the temp file is atomically renamed to the final name.
5. If the final name exists, add a number: report (converted) (2).pdf . Never
overwrite.
6. On failure or cancel, the temp file is deleted. No half files left behind.
7. Disk space is checked before starting (estimate by source size times a factor per
type).
Validators per type:
Audio and video: run ffprobe, confirm it decodes, and duration is within 1 percent of
source (when source has a duration).
Images: fully decode with Pillow, confirm dimensions are non zero.
PDF: open with a PDF library, page count above zero.
DOCX, PPTX, XLSX: valid zip, required XML parts present, loads in a parser.
Text outputs: not empty, valid encoding.
6. Progress reporting
FFmpeg: get total duration from ffprobe, then run with -progress pipe:1 and read
out_time to compute percent.
Images: per file progress (done count).
Pandoc and LibreOffice: no progress output, so show an indeterminate bar plus
elapsed time.
Folder jobs: show 'file 7 of 42' plus current file.
7. Job manager
Queue with concurrency limit defaulting to half the CPU cores (video encoding is
heavy).
Job states: queued, running, validating, done, failed, cancelled.
Jobs and logs are stored in SQLite so a crash does not lose history.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 9 of 34
One LibreOffice job at a time per profile directory. LibreOffice headless breaks if two
instances share a profile, so use a separate profile directory per worker.
8. Windows shell integration in detail
Phase 2 approach (works on Windows 10 and in Windows 11's 'Show more options' menu):
Register verbs under HKCU\Software\Classes\SystemFileAssociations\
<.ext>\shell\Morph for each supported extension. This gives different menus per file
type without writing a COM DLL.
Use HKCU, not HKLM, so install needs no admin rights.
Cascading submenus come from the SubCommands mechanism. Keep entries static
per extension.
Multi select: Explorer launches the verb once per file by default, which would open N
processes. Use the multi-select model that passes all files to one instance (single
instance handling), or better, the IExplorerCommand route. For the registry route, the
launcher must detect rapid repeat calls and merge them into one batch (collect for
about 300 ms, then run as one job).
Phase 4 approach (Windows 11 top level menu):
Implement IExplorerCommand in a small COM DLL. It can look at the selected items
and show only valid targets dynamically.
Windows 11 requires the DLL to be registered via a package with identity. A sparse
MSIX package lets you keep a normal installer while giving the app package identity.
Keep the DLL tiny and crash safe. A crash in a shell extension can affect Explorer. All
real work stays in the separate worker process.
Explorer cold start: starting a Python exe on every click costs around a second. Fix: the
tray worker stays running (low memory, starts with Windows), and the shell launcher is a
tiny native executable that only forwards the request over the named pipe.
9. Tool bundling and sizes
FFmpeg and ffprobe: bundle (tens of MB). Use a build whose license matches your
choice (GPL build if you want libx264).
Pandoc: bundle (large, but it is one binary).
Pillow and pillow-heif: Python packages. HEIC support needs the heif plugin.
LibreOffice: very large (several hundred MB). Make it an optional add-on pack. First
run detects an existing LibreOffice or Microsoft Word installation and uses it.
Otherwise offer a clearly labeled one time download.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 10 of 34
pdf2docx and Tesseract: add-on pack for Phase 5. Check each license before bundling.
Keep tool versions pinned in a lockfile with SHA256 checksums and verify them at
build time.
10. Hard conversions: honest technical notes
PDF to Word:
A PDF stores text at coordinates, with no real paragraphs or tables. Any converter
guesses the structure.
Plan: use pdf2docx for text based PDFs (verify its license, it is copyleft). Detect
scanned PDFs (no text layer) and offer OCR first (OCRmyPDF/Tesseract), then
convert.
Always label as Best effort, and tell the user that tables and multi column layouts may
need touch ups.
DWG:
DWG is Autodesk's proprietary format. LibreDWG (GPL) can read many DWG versions
and export to DXF or SVG, but not every version perfectly.
ODA File Converter works well but its license limits redistribution. So: do not bundle it.
Detect it if the user installed it, and show a link to get it themselves.
Pipeline: DWG to DXF (or SVG) via available tool, then to PDF. Label as Best effort. Treat
as an add-on, never a launch feature.
Video:
Hardware encoders (NVENC, QuickSync) are faster but behave differently. Start with
software encoding for reliability. Add hardware acceleration later as an opt in setting.
Variable frame rate, odd audio layouts, and broken metadata are common sources of
failures. Keep a corpus of nasty sample files.
11. Security
Files can be hostile. FFmpeg, LibreOffice, and Pandoc parse untrusted input and have
had vulnerabilities. Mitigations: keep bundled versions updated, run converters with
no network access where possible, run with a timeout, use a Job Object, disable
LibreOffice macros, and for Pandoc use safe mode flags where available.
Never build command strings. Argument lists only.
Paths: support long paths (above 260 characters, use the \\?\ prefix), unicode, and
network drives. Reject paths that resolve outside what the user selected (symlink and
junction tricks).
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 11 of 34
Releases are code signed, and the update check verifies signatures and checksums.
No telemetry by default. Logs stay local. Crash reports are opt in and show the user the
content before sending.
12. Repository structure
morph/
  engine/        # core: detect, graph, job manager, safe output
  adapters/      # ffmpeg, pandoc, libreoffice, image, pdf, ocr, dwg
  registry/      # formats and edges (TOML)
  worker/        # tray process, named pipe server
  ui/            # progress window, settings
  shell/         # registry installer, later the COM DLL
  installer/     # Inno Setup or WiX scripts
  tests/         # unit, golden files, corrupt files
  docs/          # user docs, contributing, architecture
13. Testing strategy
Golden corpus: 5 to 10 real files per format, including awkward ones (huge, tiny, odd
codecs, password protected, truncated, zero byte, renamed extension).
Corruption tests: feed broken inputs and confirm no half written outputs and a clear
error.
Originals check: hash the source before and after every test. Hash must match, always.
Validators tested against known bad outputs.
Windows matrix in a VM: Windows 10 and Windows 11, with and without Office
installed, with and without admin rights.
Shell tests: manual checklist (right-click on single file, multi select, folder, network
drive, unicode name, long path) run before each release, because shell UI is hard to
automate.
CI runs the engine tests on every push.
Part 3: Phase-wise Build Plan
Timeline assumes roughly 10 to 15 hours a week alongside college. Stretch or squeeze as
needed. Each phase has an exit test. Do not start the next phase until it passes.
For AI agents: each phase below has a matching list of task cards in Part 6 with exact files,
interfaces and tests. Build from those cards.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 12 of 34
Phase 0: Validate and set up (about 1 week)
Install File Converter and 2 online converters. Write down what annoys you.
Ask 10 people (classmates, parents, office folks) what they convert most. Rank the top
10 conversions. This decides your P0 list.
Pick name, license, create the repo, README with the one line pitch.
Exit test: a ranked list of real conversions from real people, and a repo with CI running
an empty test.
Phase 1: Core engine as a command line tool (weeks 1 to 3)
Format detection by magic bytes.
Registry plus conversion graph.
FFmpeg adapter (audio, video) with progress parsing.
Image adapter (including HEIC).
Safe output pipeline (temp file, validate, atomic rename, no overwrite).
Golden corpus and tests.
Exit test: morph convert --to mp3 file.mp4 and image conversions work on the
corpus, originals unchanged by hash, corrupt inputs fail cleanly with no leftovers.
Phase 2: Windows right-click and background worker (weeks 4 to
5)
Registry verbs per extension (HKCU, no admin).
Tray worker plus named pipe, with multi select batching.
Progress window and result toast.
First installer (Inno Setup), including uninstall that removes every registry entry.
Exit test: on a clean Windows 11 VM, install, right-click a video, convert, get a toast.
Uninstall leaves nothing behind. Menu appears under 'Show more options' (accepted
for now).
Phase 3: Documents (weeks 6 to 8)
Pandoc adapter (md, html, docx, txt).
LibreOffice adapter: detect existing install or Word, optional add-on download,
separate profile dir, macros off.
DOCX/PPTX/XLSX to PDF with validator and font substitution warning.
Folder conversion and type filter.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 13 of 34
Exit test: 30 sample office files convert with page counts matching, and warnings
appear when fonts are missing.
Phase 4: Windows 11 top level menu and speed (weeks 9 to 11)
IExplorerCommand COM DLL with sparse MSIX package identity.
Tiny native launcher, so click to feedback is under 1 second.
Settings window.
Exit test: entry appears in the top level Windows 11 menu, shows only valid targets, and
Explorer never hangs even if the worker is dead.
Phase 5: Hard conversions (weeks 12 to 14)
PDF to Word with scanned PDF detection and OCR path.
PDF to images, images to PDF, merge to one PDF.
DWG add-on (LibreDWG, and detect ODA if installed), all clearly labeled Best effort.
Exit test: a public 'quality report' page listing which conversions are solid and which are
best effort, with sample before/after.
Phase 6: Release (weeks 15 to 16)
Code signing (see distribution below), installer, portable zip.
winget, Scoop, and Chocolatey manifests.
Landing page with a demo GIF, a FAQ, and the quality report.
10 to 20 beta testers for 2 weeks. Fix the top issues.
Launch posts: GitHub release, Reddit (r/windows, r/opensource, r/software), Hacker
News Show HN, LinkedIn.
Exit test: 10 non-technical people install and convert a file with no help from you.
Phase 7: After launch
macOS Quick Actions and Linux file manager scripts.
Presets, plugin system, community converters.
Opt-in hardware acceleration.
Translate the UI (Hindi, Marathi) for reach.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 14 of 34
Part 4: Problems You Will Hit and How to Beat
Them
Windows 11 hides third party entries under 'Show more options'. Fix: ship Phase 2 with
the classic menu, then build the IExplorerCommand plus sparse package in Phase 4.
Document the 'Show more options' path in the first run screen meanwhile.
SmartScreen shows 'Windows protected your PC' for unsigned exes, which scares
users away. Fix: code sign. Options include a SignPath Foundation free open source
signing program, Microsoft's Trusted Signing service, or distributing through winget
and the Microsoft Store (check current eligibility, cost and rules for each). Reputation
also builds with download count.
Antivirus false positives, especially for PyInstaller built exes. Fix: use onedir mode,
build from CI so builds are reproducible, sign, submit false positive reports to vendors,
and publish SHA256 hashes. Nuitka builds often get flagged less.
Slow first click because Python starts slowly. Fix: tray worker plus tiny native launcher.
Explorer launches one process per selected file. Fix: batch window merging now,
IExplorerCommand later.
'Corrupted output' complaints. Fix: the safe output pipeline, validators, and honest
quality labels. Add a 'Report bad conversion' button that copies the log.
PDF to Word looks wrong. Fix: set expectations, use OCR for scans, show a fidelity
note, and keep a public list of known limits.
DWG is proprietary. Fix: never promise it at launch, ship as add-on, use only tools
whose license allows your use.
LibreOffice is huge and flaky when run headless. Fix: optional add-on, isolated profile
dir, timeouts, one job at a time, kill the process tree on timeout.
Missing fonts make documents shift. Fix: detect substituted fonts and warn.
Password protected or locked files. Fix: detect and ask for the password, or fail with a
clear message. For files open in another program, retry once and then say 'close the file
and try again'.
Huge files and low disk space. Fix: check free space first, allow cancel at any moment,
clean temp files.
Weird paths (long, unicode, network drives, OneDrive placeholders not yet
downloaded). Fix: long path prefix, unicode tests in the corpus, detect cloud-only files
and ask Windows to download them first.
Licensing traps (GPL, ODA, codecs). Fix: decide the project license early, keep a third
party notices file, never bundle what you cannot redistribute.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 15 of 34
Security of untrusted files. Fix: updated tools, timeouts, Job Objects, no network,
macros off.
Support load once people use it. Fix: a good error message, 'Copy details' button, issue
templates, and a docs FAQ so you answer once.
Scope creep (everyone asks for a new format). Fix: formats are registry entries, so
accept community PRs with a test file, and keep the core tiny.
Part 5: Making It Downloadable
Distribution channels, in order of effort:
1. GitHub Releases: installer exe, portable zip, SHA256 file, release notes. Build and
publish automatically from GitHub Actions on every tag.
2. winget: submit a manifest to the winget-pkgs repository so people can run winget
install Morph . This also gives easy updates.
3. Scoop and Chocolatey: more manifests, a small extra effort, reaches power users.
4. Microsoft Store (MSIX): trusted install and auto updates, signing handled by the Store.
It has rules about full trust apps and shell extensions, so check the current policy
before committing.
5. Your own landing page: big download button, GIF demo, privacy statement ('files never
leave your PC'), and the quality report.
Installer requirements:
Per user install, no admin needed.
Clean uninstall that removes all registry keys, the tray autostart, and temp folders.
Optional add-on packs downloaded on demand with checksum verification.
Updates: winget for package users, plus an in-app check against GitHub Releases that
verifies the signature before applying.
Trust checklist before launch: signed binaries, published hashes, an open source repo
anyone can read, reproducible CI builds, a short privacy page, and a clear statement of
what the app does and does not do.
Final reality check
The conversion engines already exist. Your value is the safe, honest, one-click
experience. Protect that and do not chase every format.
The hardest engineering is not the conversion. It is the Windows shell integration,
packaging, signing and trust. Budget real time for those.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 16 of 34
Ship the boring, reliable P0 first (video, audio, images, office to PDF). A small tool that
never breaks beats a big one people stop trusting.
Part 6: Agent build spec (exact contracts and
task cards)
Everything below is meant to be followed literally. Names, paths and signatures are fixed
so each phase fits the one before it.
6.1 Repo layout and dependencies
morph/
  pyproject.toml
  AGENTS.md
  CHANGELOG.md
  docs/SPEC.md
  scripts/fetch_tools.py        # downloads ffmpeg, ffprobe, pandoc into 
vendor/ and checks SHA256
  vendor/                       # gitignored, filled by fetch_tools.py
  morph/
    __init__.py
    cli.py                      # typer app, the only place that prints
    engine/
      types.py errors.py detect.py registry.py graph.py
      safe_output.py runner.py convert.py
    adapters/
      base.py ffmpeg.py image.py pandoc.py libreoffice.py pdf.py
    registry/
      formats.toml edges.toml
    worker/                     # Phase 2: tray process, job queue, pipe 
server
    ui/                         # Phase 2: progress window, settings
    platform/windows/           # Phase 2: job objects, toasts, paths
    shell/                      # Phase 2: registry installer. Phase 4: COM 
DLL
  tests/
    make_fixtures.py            # generates all test files, no copyrighted 
media
    unit/ integration/ fixtures/
Dependencies by phase (add nothing else without asking):
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 17 of 34
External binaries (in vendor/ , never committed): ffmpeg.exe , ffprobe.exe (Phase 1),
pandoc.exe (Phase 3). LibreOffice is detected on the machine, never vendored.
6.2 Core interfaces (fixed signatures)
# morph/engine/types.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol
class Quality(str, Enum):
    LOSSLESS = 'lossless'
    LOSSY = 'lossy'
    BEST_EFFORT = 'best_effort'
@dataclass(frozen=True)
class Edge:
    src: str                      # format id from formats.toml, e.g. 'mp4'
    dst: str                      # e.g. 'mp3'
    adapter: str                  # e.g. 'ffmpeg'
    quality: Quality
    cost: int                     # 1 cheap .. 10 expensive
    label: str                    # shown in the menu, e.g. 'MP3 (audio)'
    requires: tuple[str, ...] = ()            # e.g. ('libreoffice',)
    options: dict[str, str] = field(default_factory=dict)
@dataclass(frozen=True)
class Plan:
    args: list[str]               # argv. Never a shell string.
Phase
Runtime
Dev
1
typer , filetype , Pillow , pillow-
heif , psutil
pytest , pytest-cov , ruff , mypy ,
hypothesis
2
PySide6 , pywin32 , windows-toasts
(confirm it works on Win 10 and 11, else
ask)
pyinstaller
3
pypdf
none
5
pdf2docx , ocrmypdf (check each
license with the human before adding)
none
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 18 of 34
    duration_s: float | None = None   # total length if known, for progress
@dataclass
class ValidationResult:
    ok: bool
    reason: str = ''
    warnings: list[str] = field(default_factory=list)
class CancelToken:
    def cancel(self) -> None: ...
    @property
    def cancelled(self) -> bool: ...
ProgressCb = Callable[[float | None, str], None]   # (percent 0..100 or None, 
message)
class Adapter(Protocol):
    name: str
    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None: ...
    def plan(self, src: Path, dst_fmt: str, tmp_out: Path, options: dict[str, 
str]) -> Plan: ...
    def run(self, plan: Plan, on_progress: ProgressCb, cancel: CancelToken) -
> None: ...
    def validate(self, src: Path, out: Path) -> ValidationResult: ...
@dataclass
class ConvertResult:
    output: Path
    quality: Quality
    warnings: list[str]
@dataclass(frozen=True)
class Target:
    fmt: str
    label: str
    quality: Quality
    available: bool               # false if a required tool is missing
    missing: str | None = None    # e.g. 'libreoffice'
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 19 of 34
# morph/engine/errors.py
class MorphError(Exception):
    def __init__(self, code: str, user_message: str, detail: str = ''):
        super().__init__(user_message)
        self.code, self.user_message, self.detail = code, user_message, 
detail
# Allowed codes. Add a new one only by editing this list and the tests.
ERROR_CODES = (
    'E_UNSUPPORTED', 'E_SRC_MISSING', 'E_SRC_LOCKED', 'E_SRC_PASSWORD',
    'E_SRC_CORRUPT', 'E_TOOL_MISSING', 'E_TOOL_FAILED', 'E_TIMEOUT',
    'E_VALIDATION', 'E_DISK_SPACE', 'E_CANCELLED',
)
# morph/engine/convert.py  (the public engine API, the only thing the CLI and 
worker call)
def list_targets(src: Path) -> list[Target]: ...
def convert(
    src: Path,
    dst_fmt: str,
    *,
    out_dir: Path | None = None,      # None = next to the source
    options: dict[str, str] | None = None,
    on_progress: ProgressCb | None = None,
    cancel: CancelToken | None = None,
) -> ConvertResult: ...               # raises MorphError
User messages in MorphError.user_message must be plain words a non technical person
understands, for example 'This PDF has a password. Enter it to continue.' Never put stack
traces or tool output there. Put those in detail .
6.3 Registry files (single source of truth for what converts to what)
# morph/registry/formats.toml
[formats.mp4]
kind = 'video'
ext = ['mp4', 'm4v']
magic = 'ftyp'            # matched by detect.py, see tests
[formats.mp3]
kind = 'audio'
ext = ['mp3']
magic = 'id3_or_frame'
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 20 of 34
# morph/registry/edges.toml
[[edge]]
src = 'mp4'
dst = 'mp3'
adapter = 'ffmpeg'
quality = 'lossy'
cost = 3
label = 'MP3 (audio)'
[[edge]]
src = 'docx'
dst = 'pdf'
adapter = 'libreoffice'
quality = 'lossless'
cost = 6
label = 'PDF'
requires = ['libreoffice']
Rules:
registry.py loads both files at startup and fails loudly on unknown adapter names,
unknown format ids or duplicate edges.
graph.py returns direct edges first. Multi hop paths are allowed up to 2 hops, only
when no direct edge exists, and the combined quality is the worst quality in the chain.
Adding a format later means editing these files plus an adapter if needed. It must never
mean editing convert.py .
detect.py identifies files by magic bytes first and falls back to extension. If they
disagree, trust the magic bytes and add a warning.
6.4 FFmpeg command recipes (Phase 1, exact argv)
Use these as the starting point. SRC is the source, TMP is the temp output path (it ends in
.morph-part , so -f is mandatory).
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 21 of 34
BASE = ['ffmpeg', '-hide_banner', '-nostdin', '-y', '-loglevel', 'error']
PROG = ['-progress', 'pipe:1']
mp3  = BASE + ['-i', SRC, '-vn', '-c:a', 'libmp3lame', '-q:a', '2'] + PROG + 
['-f', 'mp3', TMP]
wav  = BASE + ['-i', SRC, '-vn', '-c:a', 'pcm_s16le'] + PROG + ['-f', 'wav', 
TMP]
mp4  = BASE + ['-i', SRC, '-c:v', 'libx264', '-preset', 'medium', '-crf', 
'20',
               '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart'] + 
PROG + ['-f', 'mp4', TMP]
webm = BASE + ['-i', SRC, '-c:v', 'libvpx-vp9', '-crf', '32', '-b:v', '0',
               '-c:a', 'libopus'] + PROG + ['-f', 'webm', TMP]
gif  = BASE + ['-i', SRC, '-vf',
               'fps=12,scale=480:-1:flags=lanczos,split[a][b];
[a]palettegen[p];[b][p]paletteuse',
               '-loop', '0'] + PROG + ['-f', 'gif', TMP]
probe = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 
'json', SRC]
Progress parsing: read stdout lines from -progress pipe:1 . Use the out_time_us=
value (microseconds) divided by the probed duration. If duration is missing, report None
(indeterminate). Stop at the line progress=end .
Validation for audio and video: run ffprobe on the output. It must decode, and its
duration must be within 1 percent of the source duration (skip the check when the source
has no duration). Otherwise return ok=False .
For files with no audio stream, a request for mp3 must fail with E_UNSUPPORTED and the
message 'This video has no audio to extract.' Check with ffprobe before running.
6.5 Safe output algorithm (implement exactly, in
engine/safe_output.py and engine/convert.py )
# convert(src, dst_fmt, out_dir) must do these steps in this order
1. src = src.resolve()
   - missing or not a file                -> E_SRC_MISSING
   - cannot be opened with open(src,'rb') -> E_SRC_LOCKED  (retry once after 
1 second first)
2. fmt = detect(src); edge = graph.pick(fmt, dst_fmt)
   - none                                 -> E_UNSUPPORTED
   - edge.requires tool not found         -> E_TOOL_MISSING (message names 
the tool)
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 22 of 34
3. free space on out_dir's drive must be >= 2 * src.stat().st_size -> else 
E_DISK_SPACE
4. final = free_name(out_dir or src.parent, stem=src.stem, ext=dst_ext)
   - first try  '<stem> (converted).<ext>'
   - then       '<stem> (converted) (2).<ext>', '(3)', ...
5. tmp = final.with_name(final.name + '.morph-part')
6. plan = adapter.plan(src, dst_fmt, tmp, options)
   adapter.run(plan, on_progress, cancel)
   - any failure or cancel: delete tmp, raise MorphError
7. vr = adapter.validate(src, tmp)
   - not vr.ok: delete tmp, raise E_VALIDATION
8. os.rename(tmp, final)
   - on Windows this raises FileExistsError if final appeared meanwhile.
     Catch it, pick the next free name, retry. NEVER use os.replace (it 
overwrites).
9. return ConvertResult(final, edge.quality, vr.warnings)
Extra rules:
A try/finally must guarantee no .morph-part file is left behind after any exit path,
including exceptions and cancel.
Tests hash the source file with SHA256 before and after every conversion. The hashes
must match.
The worker (Phase 2) deletes stale *.morph-part files older than 24 hours in folders it
has worked in.
6.6 CLI contract ( morph/cli.py , entry point morph )
morph convert --to <fmt> [--out-dir DIR] [--option KEY=VALUE ...] [--json] 
PATH [PATH ...]
morph targets [--json] PATH          # lists valid target formats for one 
file
morph formats [--json]               # lists every format and edge in the 
registry
morph doctor                         # reports which tools are found: ffmpeg, 
ffprobe, pandoc, libreoffice, word
Exit codes: 0 all succeeded, 1 at least one file failed, 2 bad usage, 3 a required tool
is missing.
Without --json : one human readable line per file, for example OK holiday.mp4 ->
holiday (converted).mp3 [lossy] or FAIL notes.pdf (E_SRC_PASSWORD) This PDF
has a password.
With --json : one JSON object per line on stdout, nothing else. Events:
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 23 of 34
{"event":"start","file":"C:\\a\\holiday.mp4","to":"mp3"}
{"event":"progress","file":"C:\\a\\holiday.mp4","pct":42.5}
{"event":"done","file":"C:\\a\\holiday.mp4","output":"C:\\a\\holiday 
(converted).mp3","quality":"lossy","warnings":[]}
{"event":"error","file":"C:\\a\\notes.pdf","code":"E_SRC_PASSWORD","message":
"This PDF has a password."}
Logging goes to stderr and to a rotating file in %LOCALAPPDATA%\Morph\logs . Stdout
stays clean in --json mode.
6.7 SQLite schema (Phase 2, %LOCALAPPDATA%\Morph\state.db )
CREATE TABLE jobs (
  id          TEXT PRIMARY KEY,          -- uuid4
  batch_id    TEXT NOT NULL,             -- groups files from one right-click
  src_path    TEXT NOT NULL,
  dst_fmt     TEXT NOT NULL,
  state       TEXT NOT NULL CHECK (state IN
              ('queued','running','validating','done','failed','cancelled')),
  output_path TEXT,
  quality     TEXT,
  error_code  TEXT,
  error_msg   TEXT,
  warnings    TEXT,                      -- JSON array
  created_at  TEXT NOT NULL,             -- ISO 8601 UTC
  started_at  TEXT,
  finished_at TEXT
);
CREATE INDEX jobs_batch ON jobs(batch_id);
CREATE INDEX jobs_state ON jobs(state);
On worker start, any job left in running or validating is set to failed with
error_code = 'E_TOOL_FAILED' and a note that the app was closed.
6.8 Helper pipe protocol (Phase 2)
Pipe name: \\.\pipe\morph-<windows username> . One JSON object per line, UTF-8.
Protocol version field v is 1 .
The tiny launcher ( morphctl.exe ) sends one request, reads events until batch_done ,
then exits. If the pipe does not exist, it starts the worker and retries for up to 3
seconds.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 24 of 34
{"v":1,"op":"submit","to":"mp3","paths":["C:\\a\\holiday.mp4"]}
{"v":1,"event":"accepted","batch_id":"b1","count":1}
{"v":1,"event":"progress","batch_id":"b1","job_id":"j1","pct":42.5}
{"v":1,"event":"job_done","batch_id":"b1","job_id":"j1","output":"C:\\a\\holi
day (converted).mp3"}
{"v":1,"event":"batch_done","batch_id":"b1","ok":1,"failed":0}
{"v":1,"op":"cancel","batch_id":"b1"}
Batching: when several submit requests with the same to arrive within 300 ms, the
worker merges them into one batch (this is how Explorer multi select works with
registry verbs).
Reject any path that is not an absolute local or UNC path to an existing file or folder.
Ignore unknown fields. Reject unknown op values with an error event.
6.9 Windows registry layout (Phase 2, per user, no admin)
For each supported extension .ext the installer writes (all under
HKCU\Software\Classes ):
SystemFileAssociations\.mp4\shell\Morph
    MUIVerb               = Morph
    Icon                  = <install dir>\morph.ico
    ExtendedSubCommandsKey = Morph.menu.mp4
Morph.menu.mp4\shell\01_mp3
    MUIVerb = MP3 (audio)
Morph.menu.mp4\shell\01_mp3\command
    (default) = "<install dir>\morphctl.exe" submit --to mp3 "%1"
The menu items for each extension are generated from the registry edges, never typed
by hand. Item order follows edge cost , then label.
The uninstaller removes every key it created. Keep a manifest of created keys in
%LOCALAPPDATA%\Morph\installed_keys.json so removal is exact.
VERIFY ON A REAL MACHINE: how Explorer passes several selected files to a registry
verb (it may start one process per file). The 300 ms batching in 6.8 exists for this. Write
a manual test and record the result in docs/windows-notes.md . Do not assume.
6.10 Test fixtures ( tests/make_fixtures.py , run by CI, nothing
copyrighted)
Generate everything with FFmpeg's built in sources and Pillow:
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 25 of 34
video_av.mp4      # ffmpeg -f lavfi -i 
testsrc=duration=3:size=320x240:rate=24 -f lavfi -i 
sine=frequency=440:duration=3 -c:v libx264 -c:a aac -shortest
video_silent.mp4  # same without the audio input
audio.wav         # sine=frequency=440:duration=3
img.png, img.jpg, img.bmp, img.webp, img.tiff, img.gif, img.heic   # Pillow 
(+ pillow-heif for heic)
Nasty inputs that every phase must survive without leaving files behind:
zero_byte.mp4 (empty file)
truncated.mp4 (first 30 percent of video_av.mp4 )
png_named_jpg.jpg (PNG bytes with a .jpg name)
वीडियो नमूना.mp4 (non English name with spaces)
a & b (final) v2.mp4 (symbols that break shell quoting)
a copy of video_av.mp4 inside a folder path longer than 260 characters
a file locked open by another process (use msvcrt or open with exclusive access in
the test)
Phase 3: locked.pdf (encrypted with pypdf ), fonts_missing.docx
Each integration test asserts: expected output exists and passes its validator, source
hash unchanged, no .morph-part left, and the error code is exactly the expected one for
bad inputs.
6.11 Prompts to give your AI agent
Kickoff prompt (paste at the start of each phase, change the phase line):
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 26 of 34
You are building Morph by following docs/SPEC.md. It is the source of truth.
Current phase: <N> (<name>).
1. Read Part 0 and Part 6 fully, then the Phase <N> section of Part 3 and the
   Phase <N> task cards in 6.13.
2. Reply with the ordered task list in 5 lines or fewer. Do not write code 
yet.
3. After I say go, do ONLY the next unticked task card. Write the tests the 
card
   lists, make them pass, then run: uv run pytest, uv run ruff check ., uv 
run mypy morph/engine.
4. Show a short summary of what changed and the test output. Stop and wait.
If the spec is silent or conflicts with itself, ask me. Do not invent 
formats,
flags or dependencies. Do not touch files outside the card's file list.
Anything that needs real Windows verification must be marked UNVERIFIED until 
I confirm.
Phase lines to use:
Phase 1: 'core engine and CLI. No UI, no installer, no registry code, no Windows specific
code.'
Phase 2: 'Windows right-click, helper process, progress UI, installer.'
Phase 3: 'documents: Pandoc, LibreOffice or Word detection, office to PDF, folder
conversion.'
Phase 4: 'Windows 11 top level menu and speed.'
Phase 5: 'hard conversions: PDF to Word, OCR, DWG add-on.'
Phase 6: 'release: signing, winget, landing page, beta.'
Helper prompts:
Next task: 'Go. Do task P1-04 only.'
Self review: 'Review your last commit against the Hard rules in Part 0 and the algorithm
in 6.5. List any violation. Fix only those.'
Failing test: 'Test X fails with this output: <paste>. Find the root cause first, explain it in
3 lines, then fix it with the smallest change.'
Phase gate: 'Run the exit test for Phase <N> from Part 3 and report each criterion as
pass or fail with evidence.'
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 27 of 34
6.12 AGENTS.md block (put at the repo root; works for Claude
Code, Cursor, Copilot, Codex and similar tools)
# AGENTS.md
Project: Morph, a Windows right-click file converter (offline, GPL-3.0).
Source of truth: docs/SPEC.md. Read Part 0 and Part 6 before any change.
## Commands
- Install:    uv sync
- Tests:      uv run pytest
- Lint:       uv run ruff check . && uv run ruff format --check .
- Types:      uv run mypy morph/engine
- Fixtures:   uv run python tests/make_fixtures.py
- Tools:      uv run python scripts/fetch_tools.py
- Doctor:     uv run morph doctor
## Rules
- Work on one task card at a time. Commit message: 'P1-03: short 
description'.
- Never overwrite or modify source files. Never shell=True. Engine makes no 
network calls.
- Conversions come from morph/registry/*.toml, not if-chains.
- Engine has no OS specific code. Windows code only in morph/platform/windows 
and morph/shell.
- No new dependencies without asking. Stdlib and the list in SPEC 6.1 only.
- If the spec is unclear, ask. Mark anything not verified on real Windows as 
UNVERIFIED.
- Keep changes minimal. Do not reformat or rewrite files you were not asked 
to change.
## Done means
Tests pass, ruff and mypy clean, no .morph-part files left by tests, source 
hashes unchanged.
6.13 Task cards (tick as you go)
Format of each card: ID, goal, files, what to do, tests that must pass. Do them in order. One
card, one commit.
Phase 0 (human tasks, not for the agent)
P0-01 Pick the project name, create the GitHub repo, add GPL-3.0 LICENSE , commit
this doc as docs/SPEC.md .
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 28 of 34
Phase 1: core engine and CLI
P0-02 Ask 10 people which conversions they do most. Write the ranked list in
docs/research.md . Adjust the P0 format list in the PRD if the list surprises you.
P0-03 Decide the tool download URLs and SHA256 hashes for FFmpeg and Pandoc and
put them in scripts/tools.lock.toml . The agent must not invent URLs or hashes.
P1-01 Skeleton. Files: pyproject.toml , .gitignore (ignore vendor/ , .venv/ ,
dist/ ), package folders from 6.1, .github/workflows/ci.yml on windows-latest
running ruff, mypy and pytest. Entry point morph = morph.cli:app . Test: one
placeholder test passes in CI.
P1-02 Tool fetcher. Files: scripts/fetch_tools.py ,
tests/unit/test_fetch_tools.py . Reads scripts/tools.lock.toml , downloads
each tool into vendor/ , verifies SHA256, refuses on mismatch. Test: hash verification
passes for a good temp file and raises for a bad one (no real downloads in tests).
P1-03 Types and errors. Files: engine/types.py , engine/errors.py exactly as in 6.2.
Tests: error codes are unique, MorphError keeps code , user_message , detail .
P1-04 Registry and graph. Files: engine/registry.py , engine/graph.py ,
registry/formats.toml , registry/edges.toml . Phase 1 formats: mp4, mkv, mov, avi,
webm, mp3, wav, gif, png, jpg, webp, bmp, tiff, heic. Tests: loads cleanly; unknown
adapter, unknown format and duplicate edge each fail loudly; direct edge beats multi
hop; 2 hop path gets the worst quality; 3 hop is never returned.
P1-05 Detection. Files: engine/detect.py . Magic bytes first, extension second,
disagreement adds a warning. Tests: every fixture is detected correctly;
png_named_jpg.jpg is detected as png with a warning; zero_byte.mp4 raises
E_SRC_CORRUPT .
P1-06 Fixtures. Files: tests/make_fixtures.py , tests/conftest.py . Generates
everything in 6.10 into tests/fixtures/ (gitignored). Test: a fixture check that all
expected files exist and are non empty (except zero_byte.mp4 ).
P1-07 Safe output helpers. Files: engine/safe_output.py . Functions: free_name ,
check_free_space , commit_output (the rename loop from 6.5 step 8), and a context
manager that always deletes the temp file. Tests: name collisions produce
(converted) , (2) , (3) ; a simulated FileExistsError race picks the next name; the
temp file is removed on exception and on cancel; os.replace is never called (grep test
or mock).
P1-08 Runner. Files: engine/runner.py . Runs an argv list with a timeout, streams
stdout lines to a callback, honors CancelToken , kills the whole process tree with
psutil on timeout or cancel. Tests: a sleeping child is killed on timeout (raises
E_TIMEOUT ); cancel kills a child that spawned a grandchild.
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 29 of 34
Phase 2: Windows right-click, helper and installer
P1-09 FFmpeg adapter. Files: adapters/base.py , adapters/ffmpeg.py . Implements
the recipes in 6.4, progress parsing, validation. Tests: argv builder unit tests for every
recipe (no FFmpeg needed); integration: video_av.mp4 to mp3, wav, gif, webm all
validate; progress values never decrease; video_silent.mp4 to mp3 raises
E_UNSUPPORTED with the message from 6.4; truncated.mp4 raises E_SRC_CORRUPT or
E_TOOL_FAILED and leaves no temp file.
P1-10 Image adapter. Files: adapters/image.py . Pillow and pillow-heif. Rules: apply
EXIF orientation; flatten transparency onto white when the target has no alpha (jpg,
bmp); validation fully decodes the output and checks non zero size. Tests: every image
fixture converts to every valid target and validates; transparent PNG to JPG has a
white background; HEIC to JPG works.
P1-11 Engine wiring. Files: engine/convert.py . Implements list_targets and
convert following 6.5 exactly. Tests: end to end over all fixtures; source SHA256
unchanged after success and after failure; no .morph-part anywhere afterwards;
every nasty fixture gives its expected error code.
P1-12 CLI. Files: cli.py . Implements convert , targets , formats , doctor per 6.6,
including --json . Tests with Typer's CliRunner : exit codes 0, 1, 2, 3; JSON mode
prints only valid JSON lines with the documented keys; doctor reports missing tools
clearly.
P1-13 Phase gate. Run the Phase 1 exit test in Part 3. Update CHANGELOG.md , tag
v0.1.0 .
P2-01 Job Object. Files: platform/windows/jobobject.py , update
engine/runner.py to use it on Windows (keep psutil as fallback). Test: killing the job
kills a child and its grandchild.
P2-02 State DB. Files: worker/db.py . Schema from 6.7, plus the startup recovery rule.
Tests: create, update state, recovery marks stuck jobs failed.
P2-03 Job queue. Files: worker/queue.py . Concurrency defaults to max(1,
cpu_count // 2) , supports cancel per batch, emits events. Tests with a fake adapter:
ordering, concurrency cap, cancel mid run, failure does not stop other jobs.
P2-04 Pipe server. Files: worker/pipe_server.py . Protocol from 6.8 with the 300 ms
batching. Tests: a real named pipe client submits 3 requests within 300 ms and gets
one batch; invalid paths and unknown ops get an error event.
P2-05 Launcher. Files: worker/morphctl.py . morphctl submit --to FMT PATH...
connects to the pipe, starts the worker if missing and retries for up to 3 seconds, prints
nothing, exits fast. Test: starts the worker when absent (use a temporary pipe name).
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 30 of 34
Phase 3: documents
P2-06 Progress window. Files: ui/progress_window.py . PySide6. Small always on top
window, bottom right, one row per job, percent or indeterminate bar, cancel button,
one combined window for a batch. No engine logic inside. Manual checklist in
docs/windows-notes.md .
P2-07 Toasts. Files: platform/windows/toast.py . Done toast with Open and Show in
folder, error toast with Copy details. Manual check on Windows 10 and 11.
P2-08 Registry installer. Files: shell/registry_installer.py . Implements 6.9 from
the registry edges, writes the key manifest, supports exact uninstall. Tests use a
throwaway root key ( HKCU\Software\MorphTest ), never the real classes root.
P2-09 Tray, autostart, settings. Files: worker/tray.py , worker/settings.py . Tray
icon with Quit and Settings. Autostart via the HKCU Run key. Settings TOML for output
location, naming suffix, parallel jobs. Tests for settings load, save, defaults and invalid
values.
P2-10 Packaging. Files: packaging/morph.spec (PyInstaller onedir for worker and
morphctl), packaging/installer.iss (Inno Setup, per user, no admin, bundles
vendor/ ). Uninstall must run the exact key removal from P2-08.
P2-11 Windows verification. Fill docs/windows-notes.md by hand on a clean Windows
11 VM and a Windows 10 VM: install, right-click a video, convert, see progress and toast,
multi select 5 files (record how Explorer launches the verb), uninstall, export the
registry before and after and confirm no Morph keys remain.
P2-12 Phase gate. Run the Phase 2 exit test in Part 3. Update CHANGELOG.md , tag
v0.2.0 .
P3-01 Pandoc adapter. Files: adapters/pandoc.py , edges for md, html, docx, txt.
Always pass -f and -t explicitly (output goes to a .morph-part temp file). Add --
sandbox when the bundled Pandoc supports it (check pandoc --version ). Tests: argv
builders; round trips md to docx to md keep headings; empty input fails cleanly.
P3-02 Office detection. Files: platform/windows/office_detect.py . Find
soffice.exe (Program Files, App Paths registry key). Report the version. Tests use
fake directory trees. Microsoft Word through COM is out of scope unless the human
asks for it.
P3-03 LibreOffice adapter. Files: adapters/libreoffice.py . Run soffice --
headless --norestore --nolockcheck -env:UserInstallation=file:///<private
profile dir> --convert-to pdf --outdir <private temp dir> SRC , then move the
produced file to the .morph-part path (LibreOffice picks its own output name). One
LibreOffice job at a time (file lock), 120 second timeout, kill the process tree on
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 31 of 34
Phase 4: Windows 11 top level menu and speed
Ask the human which language to use for native code before starting (Rust, C++ or C#).
Read Microsoft's current documentation for packaged context menu extensions and cite
the pages you used in docs/windows-notes.md . Do not guess manifest details from
memory.
timeout. Do not enable macros. Tests: docx, pptx, xlsx and odt fixtures convert to PDFs
that open with pypdf and have at least 1 page; two parallel requests run one after the
other; a hung process is killed.
P3-04 Office validators and font warning. Files: adapters/pdf.py (validator),
engine/validators.py . Validate docx, pptx, xlsx as valid zip files with the required
parts. For docx to PDF, compare the font names in the docx font table with the fonts
embedded in the PDF and add a warning 'Some fonts were replaced, layout may shift'
when they differ. Test with fonts_missing.docx .
P3-05 Password and locked PDFs. pypdf detects encryption. Without a password
raise E_SRC_PASSWORD . Accept --option password=... in the CLI, and add a
password prompt to the progress window. Test with locked.pdf .
P3-06 Folder conversion. Files: engine/folder.py , CLI support for passing a folder.
Options: recursive on or off, type filter. Skip files already named (converted) . Never
follow symlinks or junctions out of the selected folder. Tests: nested folders, filters,
symlink escape attempt, 200 small files complete with one summary.
P3-07 Missing LibreOffice flow. When an edge requires libreoffice and it is not
found, the menu item shows 'PDF (needs LibreOffice)'. Clicking it opens a small dialog
with the official download page link and a Re-check button. Do not auto download or
auto install LibreOffice in v1.
P3-08 Menu and installer update. Regenerate registry menus from the new edges,
update the installer script, repeat the P2-11 verification for documents.
P3-09 Phase gate. Run the Phase 3 exit test in Part 3. Tag v0.3.0 .
P4-01 Native launcher. Replace the Python morphctl with a tiny native executable
that only connects to the pipe and forwards the request. Test: median time from start
to pipe write is under 100 ms on the Windows VM.
P4-02 IExplorerCommand DLL. Implements the top level entry with a submenu. It
must not do any conversion work and must never throw into Explorer: catch
everything, log to a file, return a safe result.
P4-03 Dynamic menu. GetState hides the entry when no selected item has a valid
target. The target list comes from the same registry edges (export them to a small
JSON file at install time, the DLL reads that).
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 32 of 34
Phase 5: hard conversions
Before starting, ask the human to approve the licenses of pdf2docx and ocrmypdf for a
GPL-3.0 project, and to choose the DXF or SVG to PDF method for DWG (options:
LibreOffice Draw, Inkscape). Do not decide these silently.
P4-04 Sparse package. Create the sparse MSIX manifest and the dev signing steps
with a test certificate. Document in docs/dev-windows-shell.md how to register,
unregister and debug.
P4-05 Crash safety test. Kill the worker while Explorer is open and right-click. Explorer
must stay responsive and the entry must fail gracefully with a toast.
P4-06 Speed budget. From click to the first visible progress window: under 1 second on
the VM. Record the measurement.
P4-07 Phase gate. Run the Phase 4 exit test. Tag v0.4.0 .
P5-01 Scanned PDF detection. Files: adapters/pdf.py . A PDF is 'scanned' when text
extraction of the first 3 pages returns almost nothing. Tests with a generated text PDF
and an image only PDF.
P5-02 PDF to Word. Files: adapters/pdf2docx_adapter.py . Quality is always
best_effort . Add the warning 'Tables and complex layouts may need touch ups.'
Tests: text PDF converts to a docx that opens; scanned PDF without OCR raises
E_UNSUPPORTED with a message that offers OCR.
P5-03 OCR path. Files: adapters/ocr.py . Detect Tesseract and OCRmyPDF as add-
ons, run OCR first, then P5-02. Missing tools give a clear E_TOOL_MISSING message.
P5-04 PDF and image extras. PDF to images, images to PDF, and merge several
selected images into one PDF (Pillow or pypdf , no new dependency). Tests for page
counts and order.
P5-05 DWG add-on. Files: adapters/dwg.py . Detect ODA File Converter or LibreDWG
tools on the machine. Never bundle them. Pipeline: DWG to DXF or SVG, then to PDF
using the method the human chose. Quality best_effort . If no tool is found, the menu
item shows 'DWG (needs add-on)' and links to a docs page explaining the options.
P5-06 Quality report. Files: docs/quality.md , scripts/make_quality_report.py .
Generated from the test results: each conversion pair, its quality label, known limits,
and a before and after sample. This page is linked from the app and the website.
P5-07 Phase gate. Run the Phase 5 exit test. Tag v0.5.0 .
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 33 of 34
Phase 6: release
Ask the human which signing route to use (SignPath Foundation, Microsoft's signing
service, or Microsoft Store) before P6-02. Never commit secrets. Use GitHub Actions
secrets.
6.14 Questions the agent must ask the human (do not decide alone)
Tool download URLs and SHA256 hashes for FFmpeg and Pandoc (before P1-02).
Whether to support Microsoft Word through COM as a fallback for Office to PDF
(before P3-02).
Native language for the launcher and the shell DLL: Rust, C++ or C# (before Phase 4).
License approval for pdf2docx and ocrmypdf (before Phase 5).
The DXF or SVG to PDF method for DWG (before P5-05).
The code signing route (before P6-02).
Any new dependency, any new error code, any change to the registry schema, pipe
protocol or SQLite schema.
P6-01 Release workflow. .github/workflows/release.yml : on tag, build with
PyInstaller, build the Inno Setup installer and a portable zip, write SHA256SUMS.txt ,
create a draft GitHub Release.
P6-02 Signing step. Add a signing step for the exe files and the installer, using the
route the human chose. Verify the signature in CI after signing.
P6-03 Package manifests. winget manifest, Scoop manifest, Chocolatey nuspec in
packaging/ . Test each locally before submitting.
P6-04 Third party notices. THIRD_PARTY_NOTICES.md generated by a script: every
bundled tool and library, its version, license and source link. Include the source offer
text that the GPL builds require.
P6-05 Landing page. Simple static page in site/ : download button, 20 second demo
GIF, the sentence 'Your files never leave your PC', the quality report link, the SHA256 of
the latest release.
P6-06 Update check. In app check against the GitHub Releases API, verify the SHA256
and signature before applying, a setting to turn it off. This is the only network call in the
whole app, and it lives in the worker, never in the engine.
P6-07 Beta kit. Issue templates (bug, bad conversion, new format), a 'Copy details'
button that gathers the last log lines and the error code, and a one page test script for
10 beta testers.
P6-08 Phase gate. Run the Phase 6 exit test. Tag v1.0.0 .
Morph: Right-Click File Converter (PRD, TRD, Build Plan)
Page 34 of 34
