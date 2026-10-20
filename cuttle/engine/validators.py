"""Document and file structure validators for Cuttle.

Per task card P3-04:
- Validates docx, pptx, xlsx, odt as valid zip containers with required component parts.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from cuttle.engine.types import ValidationResult

REQUIRED_PARTS: dict[str, list[str]] = {
    "docx": ["word/document.xml", "[Content_Types].xml"],
    "pptx": ["ppt/presentation.xml", "[Content_Types].xml"],
    "xlsx": ["xl/workbook.xml", "[Content_Types].xml"],
    "odt": ["content.xml", "mimetype"],
}


def validate_office_document(path: Path, expected_fmt: str | None = None) -> ValidationResult:
    """Validate that an Office or OpenDocument file is a well-formed zip with required XML parts."""
    if not path.is_file():
        return ValidationResult(ok=False, reason=f"File not found: {path.name}")

    try:
        if path.stat().st_size == 0:
            return ValidationResult(ok=False, reason=f"File is empty (0 bytes): {path.name}")
    except OSError as exc:
        return ValidationResult(ok=False, reason=f"Could not access file: {exc}")

    if expected_fmt:
        fmt = expected_fmt.lower().lstrip(".")
    else:
        clean_stem = path.name.removesuffix(".cuttle-part")
        fmt = Path(clean_stem).suffix.lower().lstrip(".")

    try:
        with zipfile.ZipFile(path, "r") as z:
            names = set(z.namelist())
            required = REQUIRED_PARTS.get(fmt, [])
            for req in required:
                if req not in names and not any(n.endswith(req) for n in names):
                    return ValidationResult(
                        ok=False,
                        reason=(
                            f"Invalid {fmt.upper()} archive: missing required component '{req}'."
                        ),
                    )
    except zipfile.BadZipFile as exc:
        return ValidationResult(
            ok=False,
            reason=f"Corrupt {fmt.upper()} archive (not a valid zip file): {exc}",
        )
    except Exception as exc:
        return ValidationResult(
            ok=False,
            reason=f"Failed to validate {fmt.upper()} archive: {exc}",
        )

    return ValidationResult(ok=True)
