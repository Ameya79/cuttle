# Cuttle Beta Test Script (v1.0.0-rc)

Welcome to the Cuttle Beta Program! This script guides you through verifying Cuttle's core workflows on real Windows 10 and Windows 11 hardware.

---

## Prerequisites
- **OS**: Windows 10 (Version 2004 or later) or Windows 11.
- **Hardware**: Any x64 Intel/AMD PC (ARM64 supported via emulation).
- **Download**: Grab `cuttle-setup-x64.exe` or `cuttle-portable-x64.zip` from [Releases](https://github.com/Ameya79/cuttle/releases).

---

## Test Scenarios

### Scenario 1: Setup & Windows 11 Shell Integration
1. Run `cuttle-setup-x64.exe` and complete installation.
2. Open Windows File Explorer.
3. Right-click any file (e.g., a `.png` or `.pdf` file).
4. **Verification**:
   - On **Windows 11**: Does `"Convert with Cuttle"` appear directly on the main top-level context menu? (No need to click "Show more options").
   - On **Windows 10**: Does `"Convert with Cuttle"` appear on the standard context menu?

### Scenario 2: Single-File Conversion
1. Right-click an image file (e.g. `photo.png`).
2. Hover over `"Convert with Cuttle"` and select `WEBP`.
3. **Verification**:
   - A floating progress indicator briefly appears.
   - A native Windows toast notification announces `photo.webp is ready!`.
   - Clicking `"Open File"` launches the image in your default viewer.
   - Clicking `"Show in Folder"` highlights the newly created file in Explorer.
   - The original `photo.png` is completely untouched.

### Scenario 3: Batch Conversion
1. Select 5 or more photos (JPEG/PNG/HEIC).
2. Right-click the group and choose `Convert with Cuttle` ➔ `WEBP`.
3. **Verification**:
   - The multi-file progress window displays individual progress bars.
   - Conversions process concurrently without UI freezing.
   - No leftover `.cuttle-part` temporary files exist in the folder when finished.

### Scenario 4: PDF to Word & Layout Fidelity
1. Right-click a digital PDF report (with text and tables).
2. Choose `Convert with Cuttle` ➔ `DOCX`.
3. **Verification**:
   - The output Word document opens cleanly in Microsoft Word or LibreOffice Writer.
   - Paragraphs, bold/italic text, and tables are editable.

### Scenario 5: Scanned PDF & OCR Handling
1. Right-click an image-only scanned PDF.
2. Attempt conversion to `DOCX`.
3. **Verification**:
   - If Tesseract is not installed, Cuttle cleanly alerts you that the document is scanned and suggests installing OCRmyPDF / Tesseract.
   - Does not crash or output corrupt empty documents.

### Scenario 6: In-Flight Job Cancellation
1. Start converting a large video file (e.g. `.mov` or `.mp4` to `.gif`).
2. While processing, click the `Cancel` (✕) button on the floating progress card.
3. **Verification**:
   - The worker process stops immediately.
   - Any temporary `.cuttle-part` file is deleted automatically.

### Scenario 7: Background Daemon & Tray Management
1. Locate the Cuttle squid icon (`🦑`) in the Windows System Tray (near the clock).
2. Right-click the tray icon.
3. Choose `"Settings..."` or check `"Open Queue"`.
4. Choose `"Exit"`. The daemon terminates cleanly without orphaned processes.

---

## Submitting Feedback
If you encounter any bug, unexpected behavior, or conversion quality anomaly:
1. Click **"Copy Details"** on any error toast or window.
2. Open a new issue at: [https://github.com/Ameya79/cuttle/issues](https://github.com/Ameya79/cuttle/issues)
3. Select the appropriate template:
   - **Bug Report** for crashes or shell menu issues.
   - **Conversion Quality Anomaly** for formatting or visual flaws.
   - **Format Request** for missing formats.
