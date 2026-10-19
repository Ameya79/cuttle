---
name: Conversion Quality Anomaly
about: Report poor quality, layout distortion, or failed rendering on a specific conversion
title: "[QUALITY] "
labels: ["quality", "conversion"]
assignees: ""
---

### Conversion Route
- **Source Format**: [e.g. PDF, DOCX, HEIC, DWG]
- **Target Format**: [e.g. DOCX, PDF, JPEG, PNG]
- **File Size**: [e.g. 5 MB]

### Problem Description
What went wrong with the output?
- [ ] Text missing or misaligned
- [ ] Tables distorted
- [ ] Image blur or color shift
- [ ] Font substituted with fallback
- [ ] Audio/video desync or stutter
- [ ] File completely unreadable by target application

### Sample File Availability
- [ ] Can share a sanitized/non-confidential sample file
- [ ] Confidential file (cannot share, but can provide text/layout description)

### Expected vs Actual Output
- **Expected**: Describe the expected layout or audio/video fidelity.
- **Actual**: Describe the output produced by Cuttle.

### Environment & Tool Versions
Run `cuttle doctor` in PowerShell and paste the output:
```text
(Paste `cuttle doctor` output here)
```
