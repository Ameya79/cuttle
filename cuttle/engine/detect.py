"""File format detection based on magic bytes and extension fallback.

Per TRD §6.3 and §6.5:
- Magic bytes first, extension second.
- If magic bytes and extension disagree, trust the magic bytes and add a warning.
- Missing files raise E_SRC_MISSING.
- Zero-byte files raise E_SRC_CORRUPT.
- Unrecognized files raise E_UNSUPPORTED.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import filetype
from PIL import Image

from cuttle.engine.errors import CuttleError
from cuttle.engine.registry import Registry, load_registry

# Mapping from common extension/mime/type names to canonical format IDs in formats.toml
CANONICAL_FORMAT_MAP: dict[str, str] = {
    "jpeg": "jpg",
    "jpg": "jpg",
    "png": "png",
    "gif": "gif",
    "webp": "webp",
    "bmp": "bmp",
    "tif": "tiff",
    "tiff": "tiff",
    "heic": "heic",
    "heif": "heic",
    "mp4": "mp4",
    "m4v": "mp4",
    "mkv": "mkv",
    "mov": "mov",
    "qt": "mov",
    "avi": "avi",
    "webm": "webm",
    "mp3": "mp3",
    "wav": "wav",
    "wave": "wav",
}


class DetectedFormat(str):
    """Canonical format identifier string with associated detection warnings."""

    warnings: list[str]

    def __new__(cls, fmt: str, warnings: Sequence[str] | None = None) -> DetectedFormat:
        s = super().__new__(cls, fmt.lower())
        s.warnings = list(warnings or [])
        return s

    @property
    def fmt(self) -> str:
        """Return the canonical format string."""
        return str(self)


def _sniff_raw_magic(header: bytes) -> str | None:
    """Fallback manual magic-bytes inspection for formats or short buffers."""
    if len(header) < 2:
        return None

    # PNG
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"

    # JPEG
    if header.startswith(b"\xff\xd8\xff"):
        return "jpg"

    # GIF
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "gif"

    # BMP
    if header.startswith(b"BM"):
        return "bmp"

    # TIFF
    if header.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"

    # RIFF containers (WAV, AVI, WEBP)
    if header.startswith(b"RIFF") and len(header) >= 12:
        riff_type = header[8:12]
        if riff_type == b"WAVE":
            return "wav"
        if riff_type == b"AVI ":
            return "avi"
        if riff_type == b"WEBP":
            return "webp"

    # MP3 ID3 header or MPEG audio frame sync
    if header.startswith(b"ID3"):
        return "mp3"
    if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return "mp3"

    # Matroska / WebM EBML header
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        # Scan header slice for doctype
        if b"webm" in header[:64]:
            return "webm"
        if b"matroska" in header[:64]:
            return "mkv"
        return "mkv"

    # ISO Base Media File Format (ftyp box)
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand.startswith(b"qt"):
            return "mov"
        if brand in (b"heic", b"heix", b"hevc", b"mif1", b"msf1"):
            return "heic"
        return "mp4"

    return None


def _detect_magic(src: Path) -> str | None:
    """Probe magic bytes from file header using filetype, raw sniffing, and Pillow."""
    try:
        with open(src, "rb") as f:
            header = f.read(8192)
    except OSError:
        return None

    if not header:
        return None

    # 1. filetype library
    guess = filetype.guess(header)
    if guess is not None:
        canonical = CANONICAL_FORMAT_MAP.get(guess.extension.lower())
        if canonical:
            return canonical

    # 2. Raw signature sniffing
    raw_fmt = _sniff_raw_magic(header)
    if raw_fmt:
        return raw_fmt

    # 3. Pillow fallback for image formats
    try:
        with Image.open(src) as img:
            img_format = img.format
            if img_format:
                return CANONICAL_FORMAT_MAP.get(img_format.lower())
    except Exception:
        pass

    return None


def _format_from_extension(ext: str, registry: Registry) -> str | None:
    """Find the format ID matching the given file extension in the registry."""
    clean_ext = ext.lstrip(".").lower()
    for fmt_id, fmt_def in registry.formats.items():
        if clean_ext in fmt_def.ext:
            return fmt_id
    return CANONICAL_FORMAT_MAP.get(clean_ext)


def detect(src: Path, registry: Registry | None = None) -> DetectedFormat:
    """Identify the format of the given source file.

    Parameters:
        src: Path to source file.
        registry: Optional Registry instance. If None, default registry is loaded.

    Returns:
        DetectedFormat with canonical format ID and any warning messages.

    Raises:
        CuttleError("E_SRC_MISSING"): If file does not exist.
        CuttleError("E_SRC_CORRUPT"): If file size is 0 bytes.
        CuttleError("E_UNSUPPORTED"): If format cannot be identified.
    """
    path = src.resolve()
    if not path.is_file():
        raise CuttleError(
            code="E_SRC_MISSING",
            user_message=f"File not found: {src.name}",
            detail=f"Path does not exist or is not a regular file: {path}",
        )

    try:
        size = path.stat().st_size
    except OSError as err:
        raise CuttleError(
            code="E_SRC_LOCKED",
            user_message=f"Could not access file: {src.name}",
            detail=str(err),
        ) from err

    if size == 0:
        raise CuttleError(
            code="E_SRC_CORRUPT",
            user_message=f"Source file is empty (0 bytes): {src.name}",
            detail=f"File size is 0 bytes: {path}",
        )

    reg = registry or load_registry()
    warnings: list[str] = []

    # 1. Magic bytes first
    magic_fmt = _detect_magic(path)

    # 2. Extension second
    ext_str = path.suffix.lstrip(".").lower()
    ext_fmt = _format_from_extension(ext_str, reg) if ext_str else None

    if magic_fmt is not None:
        # Trust magic bytes
        chosen_fmt = magic_fmt
        if ext_fmt is not None and ext_fmt != magic_fmt:
            warnings.append(
                f"File extension .{ext_str} suggests {ext_fmt}, but file content is {magic_fmt}."
            )
        elif ext_str and ext_fmt is None:
            warnings.append(
                f"File extension .{ext_str} does not match detected format {magic_fmt}."
            )
    elif ext_fmt is not None:
        # Fall back to extension
        chosen_fmt = ext_fmt
        warnings.append(
            f"Could not verify format by magic bytes; falling back to extension .{ext_str}."
        )
    else:
        raise CuttleError(
            code="E_UNSUPPORTED",
            user_message=f"Unsupported file type: {src.name}",
            detail=f"Magic bytes undetected and extension '.{ext_str}' not in registry.",
        )

    return DetectedFormat(chosen_fmt, warnings)


# Export alias for engine conversion pipeline
detect_format = detect
