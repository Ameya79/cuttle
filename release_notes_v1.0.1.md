# Cuttle v1.0.1 — High-Fidelity Document Layout & PDF/Word Overhaul

Cuttle v1.0.1 is a targeted fidelity update focusing on **pixel-perfect document conversions between Microsoft Word (DOCX) and PDF**, eliminating layout reflow, phantom page splits, and font metric substitution.

---

### What's New in v1.0.1

#### 1. Native Microsoft Word COM Automation (`DOCX -> PDF`)
- **100% Exact Rendering**: When Microsoft Word is installed on Windows, Cuttle now invokes Word's native rendering engine (`doc.SaveAs2(FileFormat=17)`) via COM `DispatchEx`.
- **Zero Font Substitution**: Retains proprietary Microsoft typography (Calibri, Aptos, Arial), kerning, margins, headers, footers, and complex table positioning without shifting even a single pixel.
- **Graceful Fallback**: Automatically falls back to LibreOffice headless conversion when Microsoft Word is not installed on the system.

#### 2. High-Fidelity Geometry-Aware Engine (`PDF -> DOCX`)
- **Geometry Probing**: Inspects actual page text bounding boxes with PyMuPDF (`fitz`) to dynamically adapt section margins, avoiding early line wraps.
- **Tuned Heuristics**: Optimized line-break ratios (`0.08`), line overlap thresholds (`0.85`), and paragraph space ratios (`0.92`) to maintain continuous sentence flow and prevent false paragraph breaks.
- **Table Reconstruction**: Automatically detects both bordered lattice tables and borderless stream tables (financials, specs, receipts) into native Word tables.
- **Automatic Hyphen Rejoining**: Rejoins hyphenated words cleanly across line breaks.
- **OpenXML Spacing Normalization**: Normalizes paragraph bottom spacing (`w:spacing w:after`) within the output DOCX package to prevent artificial vertical page expansion.

---

### Downloads & Verification

| Asset | Description | Size |
| :--- | :--- | :--- |
| **`Cuttle-Setup-x64.exe`** | Official Windows Inno Setup installer (replaces existing v1.0.0 seamlessly) | ~350 MB |
| **`cuttle-portable-x64.zip`** | Standalone portable distribution (no installation required) | ~450 MB |
| **`SHA256SUMS.txt`** | Authenticity checksums for all release binaries | < 1 KB |

---

### How to Upgrade
- **Installed Version**: Download and run `Cuttle-Setup-x64.exe`. Inno Setup automatically detects your existing installation in `%LOCALAPPDATA%\Programs\Cuttle`, updates all files in-place, and restarts the background service. No uninstall is needed.
- **Portable Version**: Extract `cuttle-portable-x64.zip` to your chosen directory and run `cuttlectl.exe install-shell`.
