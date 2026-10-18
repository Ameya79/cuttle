<p align="center">
  <img src="assets/logo.png" alt="Cuttle Logo" width="160" />
</p>

<h1 align="center">Cuttle</h1>

<p align="center">
  <b>Right-click any file in Windows Explorer, pick the format you want, and get a converted copy instantly.</b><br>
  <i>100% Offline • Zero Uploads • Free & Open-Source (GPL-3.0) • No Account Required</i>
</p>

<p align="center">
  <a href="https://github.com/Ameya79/cuttle/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue.svg" alt="License: GPL-3.0"></a>
  <img src="https://img.shields.io/badge/python-3.12-blue.svg" alt="Python 3.12">
  <img src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078d4.svg" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/tests-251%20passing-success.svg" alt="Tests: 251 passing">
  <img src="https://img.shields.io/badge/offline--first-guaranteed-green.svg" alt="Offline Guaranteed">
</p>

---

## 🌟 Highlights

- 🖱️ **Zero App to Open**: Seamlessly integrated into the native Windows File Explorer right-click context menu.
- 🔒 **Sacred Originals**: Your source files are never modified, renamed, moved, or deleted.
- 🛡️ **Never Overwrites**: If `sample.mp3` exists, Cuttle creates `sample (converted).mp3`, then `(2).mp3`, collision-free.
- ⚡ **Sub-20ms Startup**: Lightweight launcher communicates with a persistent background worker via native Windows Named Pipes.
- 📊 **Floating Progress Card**: A frameless dark UI card in the bottom-right corner displays live conversion progress and cancel buttons.
- 🔔 **Interactive Windows Notifications**: One-click **[Open File]** and **[Show in Folder]** action buttons right from the Windows toast banner.
- 🏷️ **Honest Quality Transparency**: Every conversion clearly indicates whether it is **Lossless**, **Lossy**, or **Best Effort**.
- 💬 **Plain-English Feedback**: Never decipher cryptic error codes—get clear messages like *"The file is password-protected"* or *"Disk full"*.

---

## 🔄 Supported Conversions (Phase 1 & Phase 2)

| Input Format | Category | Reachable Conversion Targets | Quality Profile |
|:---|:---:|:---|:---:|
| **MP4 / M4V** | 🎬 Video | `MP3` (audio), `WAV` (audio), `WebM` (video), `GIF` (animation) | Lossless / Lossy |
| **MKV** | 🎬 Video | `MP4`, `WebM`, `MP3`, `WAV` | Lossy / Lossless |
| **MOV** | 🎬 Video | `MP4`, `WebM`, `MP3`, `WAV`, `GIF` | Lossy / Lossless |
| **AVI** | 🎬 Video | `MP4`, `WebM`, `MP3`, `WAV` | Lossy / Lossless |
| **WebM** | 🎬 Video | `MP4`, `MP3`, `WAV`, `GIF` | Lossy / Lossless |
| **PNG** | 🖼️ Image | `JPG`, `WebP`, `BMP`, `TIFF` | Lossless / Lossy |
| **JPG / JPEG** | 🖼️ Image | `PNG`, `WebP`, `BMP`, `TIFF` | Lossy / Lossless |
| **HEIC / HEIF** | 🖼️ Image | `JPG`, `PNG` (iPhone photo conversion) | Lossy / Lossless |
| **WebP** | 🖼️ Image | `PNG`, `JPG`, `BMP` | Lossless / Lossy |
| **BMP** | 🖼️ Image | `PNG`, `JPG` | Lossless / Lossy |
| **TIFF** | 🖼️ Image | `PNG`, `JPG` | Lossless / Lossy |
| **GIF** | 🖼️ Image | `PNG` (first frame extract) | Lossy |
| **WAV** | 🎵 Audio | `MP3` | Lossy |
| **MP3** | 🎵 Audio | `WAV` | Lossless |

---

## 🏛️ System Architecture

```
[Windows File Explorer (Any Folder)]
   │  (Right-click file: "Cuttle ➔ Convert to MP3")
   ▼
[cuttlectl.exe]  (Sub-20ms ultra-fast launcher; zero console flash)
   │  (IPC over Windows Named Pipe \\.\pipe\cuttle-<user>)
   ▼
[cuttle-worker daemon]  (Background Qt engine in System Tray)
   ├── 1. 300ms Debouncer: Bundles rapid multi-select clicks into 1 neat batch
   ├── 2. SQLite Database: Tracks jobs with crash recovery (WAL mode)
   ├── 3. Concurrency Queue: Parallel jobs capped to half CPU cores
   ├── 4. Win32 Job Objects: Guaranteed process-tree kill switch
   ├── 5. Floating Progress Window: Dark frameless live status card
   ├── 6. Windows Notification Toasts: Action buttons [Open File] [Show in Folder]
   ├── 7. Shell Refresh (SHChangeNotify): Instant file appearance in Explorer
   └── 8. System Tray & Settings: Preferences & zero-admin autostart
```

---

## 🚀 Quick Start

### Option A: Install Explorer Context Menus (Development)

```powershell
# 1. Clone repository
git clone https://github.com/Ameya79/cuttle.git
cd cuttle

# 2. Sync dependencies using uv
uv sync

# 3. Fetch tool binaries (FFmpeg & FFprobe)
uv run python scripts/fetch_tools.py

# 4. Register right-click context menus in File Explorer (Zero Admin Required!)
uv run cuttlectl install-shell

# 5. Right-click any file in File Explorer and convert!
```

### Option B: Command Line Interface (CLI)

```powershell
# Convert a video directly to MP3
uv run cuttle convert --to mp3 video.mp4

# Inspect reachable conversion targets for a file
uv run cuttle targets video.mp4

# Inspect all registered formats in registry
uv run cuttle formats

# Verify external tool health and system compatibility
uv run cuttle doctor
```

---

## 🧪 Testing & Code Quality

Cuttle maintains an exhaustive automated test suite covering extreme edge cases, truncated files, concurrency, process killswitches, and UI interactions:

```powershell
# Generate test fixtures
uv run python tests/make_fixtures.py

# Run all 251 automated tests
uv run pytest

# Check code formatting & linting
uv run ruff check .
uv run ruff format --check .

# Static type verification
uv run mypy cuttle/engine
```

---

## 📜 License

Distributed under the **GNU General Public License v3.0 (GPL-3.0)**. See [`LICENSE`](LICENSE) for details.
