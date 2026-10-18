"""Pillow and pillow-heif adapter for image conversions.

Per TRD §6.10, §6.4, and task card P1-10:
- Converts between image formats (PNG, JPG, WebP, BMP, TIFF, HEIC, GIF).
- EXIF orientation is preserved and baked into pixel data via ImageOps.exif_transpose.
- Transparency is flattened onto a solid white background when destination format
  does not support alpha (e.g. JPG, BMP).
- Validation fully decodes the output image (im.load()) and verifies dimensions > 0.
- Respects CancelToken before, during, and after processing.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps
import pillow_heif

from cuttle.adapters.base import BaseAdapter
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import (
    CancelToken,
    Plan,
    ProgressCb,
    Quality,
    ValidationResult,
)

# Register HEIF opener with Pillow so Image.open handles HEIC/HEIF files
pillow_heif.register_heif_opener()

SUPPORTED_SOURCES = frozenset(
    {"png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "heic", "heif", "gif"}
)
SUPPORTED_TARGETS = frozenset({"png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"})

PIL_FORMAT_MAP: dict[str, str] = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tiff": "TIFF",
    "tif": "TIFF",
}

FORMATS_WITHOUT_ALPHA = frozenset({"jpg", "jpeg", "bmp"})


class ImageAdapter(BaseAdapter):
    """Image conversion adapter using Pillow and pillow-heif."""

    name = "image"

    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """Check if image adapter can perform the conversion."""
        src = src_fmt.lower()
        dst = dst_fmt.lower()

        if src not in SUPPORTED_SOURCES or dst not in SUPPORTED_TARGETS:
            return None

        if dst in {"jpg", "jpeg", "webp"}:
            return Quality.LOSSY

        return Quality.LOSSLESS

    def plan(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str],
    ) -> Plan:
        """Build Plan representing the image conversion job."""
        target = dst_fmt.lower()
        if target not in SUPPORTED_TARGETS:
            raise CuttleError(
                code="E_UNSUPPORTED",
                user_message=f"Unsupported image target format: {target}",
                detail=f"Target '{target}' is not in supported image targets.",
            )

        if not src.is_file():
            raise CuttleError(
                code="E_SRC_MISSING",
                user_message=f"Source file not found: {src.name}",
                detail=f"File does not exist: {src}",
            )

        # args encodes the in-memory conversion specification
        args = ["pillow", str(src), target, str(tmp_out)]
        return Plan(args=args, duration_s=None)

    def run(
        self,
        plan: Plan,
        on_progress: ProgressCb,
        cancel: CancelToken,
    ) -> None:
        """Execute image conversion with EXIF transposition and alpha flattening."""
        if len(plan.args) < 4:
            raise CuttleError(
                code="E_TOOL_FAILED",
                user_message="Invalid plan arguments for image conversion.",
                detail=f"Expected 4 arguments in plan.args, got {plan.args}",
            )

        src = Path(plan.args[1])
        dst_fmt = plan.args[2].lower()
        tmp_out = Path(plan.args[3])

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled before starting image decoding.",
            )

        on_progress(0.0, "opening")

        try:
            with Image.open(src) as img:
                # 1. EXIF orientation handling
                transposed = ImageOps.exif_transpose(img)
                work_img = transposed if transposed is not None else img.copy()

                if cancel.cancelled:
                    raise CuttleError(
                        code="E_CANCELLED",
                        user_message="The conversion was cancelled.",
                        detail="Cancelled after image transposition.",
                    )

                on_progress(50.0, "converting")

                # 2. Transparency handling
                if dst_fmt in FORMATS_WITHOUT_ALPHA:
                    # Target does not support transparency: flatten over solid white
                    if work_img.mode in ("RGBA", "LA") or (
                        work_img.mode == "P" and "transparency" in work_img.info
                    ):
                        rgba = work_img.convert("RGBA")
                        white_bg = Image.new("RGB", rgba.size, (255, 255, 255))
                        alpha_mask = rgba.split()[3]
                        white_bg.paste(rgba, mask=alpha_mask)
                        work_img = white_bg
                    elif work_img.mode != "RGB":
                        work_img = work_img.convert("RGB")
                elif work_img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                    # For alpha-capable formats, convert exotic modes to RGB/RGBA
                    work_img = work_img.convert("RGBA" if "A" in work_img.mode else "RGB")

                # 3. Format-specific save options
                pil_format = PIL_FORMAT_MAP.get(dst_fmt, dst_fmt.upper())
                save_kwargs: dict[str, object] = {}

                if pil_format == "JPEG":
                    save_kwargs["quality"] = 90
                    save_kwargs["optimize"] = True
                elif pil_format == "WEBP":
                    save_kwargs["quality"] = 85
                    save_kwargs["method"] = 6
                elif pil_format == "PNG":
                    save_kwargs["optimize"] = True

                if cancel.cancelled:
                    raise CuttleError(
                        code="E_CANCELLED",
                        user_message="The conversion was cancelled.",
                        detail="Cancelled before saving output.",
                    )

                work_img.save(tmp_out, format=pil_format, **save_kwargs)

        except CuttleError:
            raise
        except (Image.UnidentifiedImageError, OSError, ValueError) as err:
            raise CuttleError(
                code="E_SRC_CORRUPT",
                user_message=f"Could not read image file: {src.name}",
                detail=str(err),
            ) from err
        except Exception as err:
            raise CuttleError(
                code="E_TOOL_FAILED",
                user_message="Image conversion failed.",
                detail=str(err),
            ) from err

        on_progress(100.0, "complete")

    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Validate output image by fully decoding it and checking dimensions."""
        if not out.is_file() or out.stat().st_size == 0:
            return ValidationResult(ok=False, reason="Output file is missing or 0 bytes.")

        try:
            with Image.open(out) as img:
                img.load()
                w, h = img.size
                if w <= 0 or h <= 0:
                    return ValidationResult(
                        ok=False,
                        reason=f"Invalid image dimensions: {w}x{h}",
                    )
        except Exception as err:
            return ValidationResult(
                ok=False,
                reason=f"Output image decode validation failed: {err}",
            )

        return ValidationResult(ok=True)
