# Conversion Hardening and Stress Testing Invariants

1. **Adversarial Input Validation**:
   - Every conversion adapter must be validated against hostile, adversarial, and edge-case inputs:
     - **Geometries**: Non-standard video dimensions (odd width/height that break video codecs like H.264).
     - **Color Spaces**: CMYK, RGBA with partial opacity, 1-bit monochrome, and indexed palette images.
     - **Document Layouts**: Multi-column text, lattice tables, stream tables, and non-ASCII Unicode (Devanagari, CJK, Emoji).
     - **Hostile Inputs**: Truncated payloads, 0-byte files, and password-protected archives.

2. **Quality Tier Transparency & Layout Sanitization**:
   - Formats that undergo optical or heuristic reverse-engineering (e.g. PDF -> DOCX) must always be designated as `Quality.BEST_EFFORT` and carry clear warnings regarding complex layout touch-ups.
   - Heuristic adapters must enable paragraph reflow sanitization (such as `delete_end_line_hyphen=True`) to prevent broken text blocks.

3. **Concurrency and Cancellation Cleanliness**:
   - Under rapid mid-flight cancellation bursts, adapters must never orphan subprocesses, leave `.cuttle-part` temporary files, or leave database records in corrupt states.
   - Source files must remain immutable and locked files must cleanly trigger `E_SRC_LOCKED`.
