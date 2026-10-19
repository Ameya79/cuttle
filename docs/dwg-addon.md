# DWG Conversion Add-On Guide

Cuttle supports converting AutoCAD DWG files to PDF and DXF completely offline.
Because AutoCAD file specifications are proprietary and DWG libraries carry specialized licensing, conversion tools are not bundled directly inside Cuttle. Instead, Cuttle detects either **LibreDWG** or **ODA File Converter** installed on your computer.

---

## Supported Add-Ons

### Option 1: LibreDWG (Free & Open Source, Recommended)
LibreDWG provides command-line utilities (`dwg2dxf`, `dwg2svg`) for converting DWG drawings.

1. Download the Windows binary release of LibreDWG from:
   https://github.com/LibreDWG/libredwg/releases
2. Extract the archive (e.g. to `C:\Tools\LibreDWG` or `%LOCALAPPDATA%\Programs\LibreDWG`).
3. Add the extracted folder containing `dwg2dxf.exe` to your Windows `PATH` environment variable.
4. Restart Cuttle or File Explorer. Cuttle will automatically detect `dwg2dxf`.

### Option 2: ODA File Converter (Open Design Alliance)
ODA File Converter is a widely used free desktop utility that batch-converts DWG and DXF files.

1. Download the Windows installer from the official Open Design Alliance site:
   https://www.opendesign.com/guestfiles/oda_file_converter
2. Run the installer (typically installs to `C:\Program Files\ODA\ODAFileConverter <version>\`).
3. Cuttle automatically searches the standard Program Files directory for `ODAFileConverter.exe`.

---

## Rendering Pipeline

Once an add-on is installed:
1. Cuttle invokes the add-on to convert the DWG file to DXF format.
2. If converting to PDF, Cuttle uses **LibreOffice Draw** in headless mode to render the DXF vector drawing into a high-resolution PDF.
3. Quality is labeled **Best Effort**. Hatches, custom XREFs, SHX font shapes, and 3D wireframes may vary depending on CAD versions.
