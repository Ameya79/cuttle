# Document Layout Fidelity Invariants

## 1. Word to PDF (`DOCX -> PDF`)
- On Windows systems with Microsoft Office installed, always prioritize native Word automation (`winword.exe` via COM) for DOCX to PDF export.
- Native Word uses Microsoft's exact font rendering engine, TrueType/OpenType font tables (Calibri, Aptos, Arial), and OpenXML pagination layout, producing 100% pixel-perfect "ditto" output with zero line wrapping or page-spilling.
- LibreOffice is a fallback for headless Linux/server environments or systems lacking Microsoft Office.
- Never substitute fonts without issuing clear user warnings.

## 2. PDF to Word (`PDF -> DOCX`)
- Query exact page dimensions (`rect.width`, `rect.height`) and text bounding boxes from PyMuPDF (`fitz`) before conversion.
- Configure `pdf2docx` with tuned layout heuristics:
  - `delete_end_line_hyphen = True`: Reconnects hyphenated line-endings.
  - `line_break_width_ratio = 0.08`: Prevents premature line breaks within paragraphs.
  - `line_overlap_threshold = 0.85`: Ensures multi-line text stays in a single cohesive paragraph block.
  - `new_paragraph_free_space_ratio = 0.92`: Distinguishes genuine paragraph spacing from standard line leading.
  - `lines_left_aligned_threshold = 1.5`: Tighter alignment clustering for clean indentations.
  - `parse_lattice_table = True` and `parse_stream_table = True`: Accurately preserves table boundaries without border collapse.
- Normalize OpenXML paragraph spacing (`w:spacing`) to avoid accidental double-spacing and premature page spilling.
