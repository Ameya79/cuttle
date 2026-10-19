# Cuttle Conversion Quality Report

Cuttle is built on a simple promise: **honest offline conversion with zero file uploads**.
Not all file conversions are equal. This report documents every supported conversion pair, its exact quality level, and known technical boundaries.

## Quality Levels

- **Lossless**: Bit-perfect or mathematically complete data preservation.
- **Lossy**: Audio/video recompression or image quantization within perceptual limits.
- **Best Effort**: Complex document, CAD, or OCR layout reconstruction where structural or styling shifts may occur.

## Supported Conversions Matrix

| Source | Target | Adapter | Quality | Cost | Notes & Known Limits |
|:-------|:-------|:--------|:--------|:----:|:---------------------|
| `AVI` | `GIF` | `ffmpeg` | **Lossy** | 5/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `AVI` | `MP3` | `ffmpeg` | **Lossy** | 3/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `AVI` | `MP4` | `ffmpeg` | **Lossy** | 4/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `AVI` | `WAV` | `ffmpeg` | **Lossless** | 2/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `AVI` | `WEBM` | `ffmpeg` | **Lossy** | 5/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `BMP` | `JPG` | `image` | **Lossy** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `BMP` | `PDF` | `image_pdf` | **Lossless** | 2/10 | Direct bitmap encapsulation into PDF pages or high-resolution page rasterization. Original image pixel resolution is preserved. |
| `BMP` | `PNG` | `image` | **Lossless** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `BMP` | `TIFF` | `image` | **Lossless** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `BMP` | `WEBP` | `image` | **Lossy** | 3/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `DOCX` | `HTML` | `pandoc` | **Lossy** | 3/10 | Converts document structure and standard formatting. Complex Office macros, equations, and embedded vector graphics may be simplified. |
| `DOCX` | `MD` | `pandoc` | **Lossy** | 3/10 | Converts document structure and standard formatting. Complex Office macros, equations, and embedded vector graphics may be simplified. |
| `DOCX` | `PDF` | `libreoffice` | **Lossless** | 4/10 | Exact visual layout fidelity. If host lacks proprietary source fonts, automatic font substitution warning is emitted. |
| `DOCX` | `TXT` | `pandoc` | **Lossy** | 2/10 | Converts document structure and standard formatting. Complex Office macros, equations, and embedded vector graphics may be simplified. |
| `DWG` | `DXF` | `dwg` | **Best effort** | 5/10 | CAD drawing conversion is best-effort. Requires LibreDWG or ODA add-on. |
| `DWG` | `PDF` | `dwg` | **Best effort** | 8/10 | CAD drawing conversion is best-effort. Requires LibreDWG or ODA add-on. |
| `DXF` | `PDF` | `dwg` | **Best effort** | 5/10 | CAD drawing conversion is best-effort. Requires LibreDWG or ODA add-on. |
| `GIF` | `JPG` | `image` | **Lossy** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `GIF` | `PNG` | `image` | **Lossless** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `GIF` | `WEBP` | `image` | **Lossy** | 3/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `HEIC` | `BMP` | `image` | **Lossless** | 1/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `HEIC` | `JPG` | `image` | **Lossy** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `HEIC` | `PNG` | `image` | **Lossless** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `HEIC` | `TIFF` | `image` | **Lossless** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `HEIC` | `WEBP` | `image` | **Lossy** | 3/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `HTML` | `DOCX` | `pandoc` | **Lossless** | 3/10 | Converts document structure and standard formatting. Complex Office macros, equations, and embedded vector graphics may be simplified. |
| `HTML` | `MD` | `pandoc` | **Lossless** | 2/10 | Converts document structure and standard formatting. Complex Office macros, equations, and embedded vector graphics may be simplified. |
| `JPG` | `BMP` | `image` | **Lossless** | 1/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `JPG` | `PDF` | `image_pdf` | **Lossy** | 2/10 | Direct bitmap encapsulation into PDF pages or high-resolution page rasterization. Original image pixel resolution is preserved. |
| `JPG` | `PNG` | `image` | **Lossless** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `JPG` | `TIFF` | `image` | **Lossless** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `JPG` | `WEBP` | `image` | **Lossy** | 3/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `MD` | `DOCX` | `pandoc` | **Lossless** | 3/10 | Converts document structure and standard formatting. Complex Office macros, equations, and embedded vector graphics may be simplified. |
| `MD` | `HTML` | `pandoc` | **Lossless** | 2/10 | Converts document structure and standard formatting. Complex Office macros, equations, and embedded vector graphics may be simplified. |
| `MD` | `TXT` | `pandoc` | **Lossless** | 1/10 | Converts document structure and standard formatting. Complex Office macros, equations, and embedded vector graphics may be simplified. |
| `MKV` | `GIF` | `ffmpeg` | **Lossy** | 5/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MKV` | `MP3` | `ffmpeg` | **Lossy** | 3/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MKV` | `MP4` | `ffmpeg` | **Lossy** | 4/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MKV` | `WAV` | `ffmpeg` | **Lossless** | 2/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MKV` | `WEBM` | `ffmpeg` | **Lossy** | 5/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MOV` | `GIF` | `ffmpeg` | **Lossy** | 5/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MOV` | `MP3` | `ffmpeg` | **Lossy** | 3/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MOV` | `MP4` | `ffmpeg` | **Lossy** | 4/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MOV` | `WAV` | `ffmpeg` | **Lossless** | 2/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MOV` | `WEBM` | `ffmpeg` | **Lossy** | 5/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MP3` | `WAV` | `ffmpeg` | **Lossless** | 2/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MP4` | `GIF` | `ffmpeg` | **Lossy** | 5/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MP4` | `MP3` | `ffmpeg` | **Lossy** | 3/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MP4` | `WAV` | `ffmpeg` | **Lossless** | 2/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `MP4` | `WEBM` | `ffmpeg` | **Lossy** | 5/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `ODT` | `PDF` | `libreoffice` | **Lossless** | 4/10 | Exact visual layout fidelity. If host lacks proprietary source fonts, automatic font substitution warning is emitted. |
| `PDF` | `DOCX` | `pdf2docx` | **Best effort** | 6/10 | Tables and complex layouts may need touch ups. Scanned PDFs require OCR. |
| `PDF` | `JPG` | `image_pdf` | **Lossy** | 3/10 | Direct bitmap encapsulation into PDF pages or high-resolution page rasterization. Original image pixel resolution is preserved. |
| `PDF` | `PNG` | `image_pdf` | **Lossless** | 3/10 | Direct bitmap encapsulation into PDF pages or high-resolution page rasterization. Original image pixel resolution is preserved. |
| `PNG` | `BMP` | `image` | **Lossless** | 1/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `PNG` | `JPG` | `image` | **Lossy** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `PNG` | `PDF` | `image_pdf` | **Lossless** | 2/10 | Direct bitmap encapsulation into PDF pages or high-resolution page rasterization. Original image pixel resolution is preserved. |
| `PNG` | `TIFF` | `image` | **Lossless** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `PNG` | `WEBP` | `image` | **Lossy** | 3/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `PPTX` | `PDF` | `libreoffice` | **Lossless** | 4/10 | Exact visual layout fidelity. If host lacks proprietary source fonts, automatic font substitution warning is emitted. |
| `TIFF` | `BMP` | `image` | **Lossless** | 1/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `TIFF` | `JPG` | `image` | **Lossy** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `TIFF` | `PDF` | `image_pdf` | **Lossless** | 2/10 | Direct bitmap encapsulation into PDF pages or high-resolution page rasterization. Original image pixel resolution is preserved. |
| `TIFF` | `PNG` | `image` | **Lossless** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `TIFF` | `WEBP` | `image` | **Lossy** | 3/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `TXT` | `DOCX` | `pandoc` | **Lossless** | 2/10 | Converts document structure and standard formatting. Complex Office macros, equations, and embedded vector graphics may be simplified. |
| `TXT` | `HTML` | `pandoc` | **Lossless** | 2/10 | Converts document structure and standard formatting. Complex Office macros, equations, and embedded vector graphics may be simplified. |
| `TXT` | `MD` | `pandoc` | **Lossless** | 1/10 | Converts document structure and standard formatting. Complex Office macros, equations, and embedded vector graphics may be simplified. |
| `WAV` | `MP3` | `ffmpeg` | **Lossy** | 3/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `WEBM` | `GIF` | `ffmpeg` | **Lossy** | 5/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `WEBM` | `MP3` | `ffmpeg` | **Lossy** | 3/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `WEBM` | `MP4` | `ffmpeg` | **Lossy** | 4/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `WEBM` | `WAV` | `ffmpeg` | **Lossless** | 2/10 | Video transcode is lossy (CPU-optimized h264/vp9). Audio to WAV is lossless PCM. Animation (GIF) palette quantizes to 256 colors. |
| `WEBP` | `BMP` | `image` | **Lossless** | 1/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `WEBP` | `JPG` | `image` | **Lossy** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `WEBP` | `PDF` | `image_pdf` | **Lossy** | 2/10 | Direct bitmap encapsulation into PDF pages or high-resolution page rasterization. Original image pixel resolution is preserved. |
| `WEBP` | `PNG` | `image` | **Lossless** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `WEBP` | `TIFF` | `image` | **Lossless** | 2/10 | Lossless across PNG, TIFF, BMP. Formats without alpha (JPG, BMP) flatten transparency onto white background. EXIF orientation is preserved. |
| `XLSX` | `PDF` | `libreoffice` | **Lossless** | 4/10 | Exact visual layout fidelity. If host lacks proprietary source fonts, automatic font substitution warning is emitted. |

## Offline & Privacy Guarantees

- **Zero Network Activity**: Cuttle's conversion engine has zero network permissions. Files never leave your local machine.
- **Safe File Operations**: Cuttle never overwrites source files, writes to temporary `.cuttle-part` files during processing, and atomically replaces only on validation success.
- **Clean Subprocess Isolation**: External engine processes run inside Windows Job Objects and automatically terminate on cancel or exit.

---
*Report automatically generated by `scripts/make_quality_report.py`.*
