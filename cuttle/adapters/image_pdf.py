"""PDF and image extras adapter (P5-04).

Per TRD task card P5-04:
- PDF to images (extract or render pages to individual images).
- Images to PDF (convert individual images to PDF documents).
- Merge multiple selected images into a single PDF document in exact specified order.
- Uses Pillow and pypdf (no new dependency).
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path
from typing import Any

import pypdf
from PIL import Image, ImageOps

from cuttle.adapters.base import BaseAdapter
from cuttle.adapters.pdf import validate_pdf
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import (
    CancelToken,
    Plan,
    ProgressCb,
    Quality,
    ValidationResult,
)

SUPPORTED_IMAGE_FORMATS = frozenset({"png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "heic"})
IMAGE_TARGET_FORMATS = frozenset({"png", "jpg", "jpeg", "webp", "bmp", "tiff"})


def merge_images_to_pdf(image_paths: list[Path], out_pdf: Path) -> Path:
    """Merge multiple image files into a single multi-page PDF preserving exact order."""
    if not image_paths:
        raise CuttleError(
            code="E_SRC_MISSING",
            user_message="No images provided for PDF creation.",
            detail="The list of input image paths was empty.",
        )

    for p in image_paths:
        if not p.is_file():
            raise CuttleError(
                code="E_SRC_MISSING",
                user_message=f"Image not found: {p.name}",
                detail=f"File does not exist: {p}",
            )

    pil_images: list[Any] = []
    try:
        for p in image_paths:
            img = Image.open(p)
            transposed = ImageOps.exif_transpose(img)
            work_img = transposed if transposed is not None else img

            # PDF export in Pillow requires RGB or L mode
            if work_img.mode in ("RGBA", "LA", "P"):
                rgb = Image.new("RGB", work_img.size, (255, 255, 255))
                if work_img.mode in ("RGBA", "LA"):
                    mask = work_img.split()[-1]
                    rgb.paste(work_img, mask=mask)
                else:
                    rgb.paste(work_img.convert("RGB"))
                pil_images.append(rgb)
            elif work_img.mode != "RGB":
                pil_images.append(work_img.convert("RGB"))
            else:
                pil_images.append(work_img.copy())

        first = pil_images[0]
        rest = pil_images[1:] if len(pil_images) > 1 else []

        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        first.save(out_pdf, format="PDF", save_all=True, append_images=rest)
    finally:
        for img_item in pil_images:
            with contextlib.suppress(Exception):
                img_item.close()

    return out_pdf


def pdf_to_images(
    pdf_path: Path,
    out_dir: Path,
    fmt: str = "png",
    cancel: CancelToken | None = None,
    on_progress: ProgressCb | None = None,
) -> list[Path]:
    """Render each page of a PDF document into an image file."""
    if not pdf_path.is_file():
        raise CuttleError(
            code="E_SRC_MISSING",
            user_message=f"PDF file not found: {pdf_path.name}",
            detail=f"File does not exist: {pdf_path}",
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    generated_images: list[Path] = []

    # Use pymupdf for fast, high-quality vector-to-raster page rendering
    try:
        import pymupdf

        mupdf: Any = pymupdf
        doc: Any = mupdf.open(str(pdf_path))
        total_pages: int = len(doc)
        if total_pages == 0:
            raise CuttleError(
                code="E_SRC_CORRUPT",
                user_message=f"PDF file '{pdf_path.name}' has no pages.",
                detail="Document contains 0 pages.",
            )

        for i, page_item in enumerate(doc):
            if cancel and cancel.cancelled:
                raise CuttleError(
                    code="E_CANCELLED",
                    user_message="The conversion was cancelled.",
                    detail="Cancelled during PDF page rendering.",
                )

            if on_progress:
                on_progress(
                    float(i) / total_pages * 100.0, f"Rendering page {i + 1} of {total_pages}..."
                )

            page_any: Any = page_item
            pix: Any = page_any.get_pixmap()
            out_file = out_dir / f"{pdf_path.stem}_page_{i + 1:03d}.{fmt.lower()}"
            pix.save(str(out_file))
            generated_images.append(out_file)

        doc.close()
    except Exception as exc:
        if isinstance(exc, CuttleError):
            raise
        # Fallback to pypdf image extraction if rendering failed
        reader = pypdf.PdfReader(str(pdf_path))
        if len(reader.pages) == 0:
            raise CuttleError(
                code="E_SRC_CORRUPT",
                user_message=f"PDF file '{pdf_path.name}' has no pages.",
                detail=str(exc),
            ) from exc

        count = 0
        for _i, page in enumerate(reader.pages):
            for img_obj in page.images:
                count += 1
                out_file = out_dir / f"{pdf_path.stem}_page_{count:03d}.{fmt.lower()}"
                with open(out_file, "wb") as f:
                    f.write(img_obj.data)
                generated_images.append(out_file)

        if not generated_images:
            raise CuttleError(
                code="E_CONV_FAILED",
                user_message=f"Could not extract or render pages from '{pdf_path.name}'.",
                detail=str(exc),
            ) from exc

    return generated_images


class ImagePdfAdapter(BaseAdapter):
    """Adapter for bidirectional PDF <-> Image conversions and multi-image packaging."""

    name = "image_pdf"

    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """Supported: PDF to images and images to PDF."""
        src = src_fmt.lower()
        dst = dst_fmt.lower()

        if src == "pdf" and dst in IMAGE_TARGET_FORMATS:
            return Quality.LOSSLESS if dst in ("png", "tiff", "bmp") else Quality.LOSSY

        if src in SUPPORTED_IMAGE_FORMATS and dst == "pdf":
            return Quality.LOSSLESS if src in ("png", "tiff", "bmp") else Quality.LOSSY

        return None

    def plan(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str],
    ) -> Plan:
        """Construct conversion plan for PDF <-> Image."""
        args = ["image_pdf", str(src), dst_fmt.lower(), str(tmp_out)]
        return Plan(args=args, duration_s=1.0)

    def run(
        self,
        plan: Plan,
        on_progress: ProgressCb,
        cancel: CancelToken,
    ) -> None:
        """Execute PDF <-> Image conversion."""
        if len(plan.args) < 4:
            raise CuttleError(
                code="E_TOOL_FAILED",
                user_message="Invalid plan arguments for image/PDF conversion.",
                detail=f"Expected 4 arguments in plan.args, got {plan.args}",
            )

        src = Path(plan.args[1])
        dst_fmt = plan.args[2].lower()
        tmp_out = Path(plan.args[3])

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled before conversion started.",
            )

        if dst_fmt == "pdf":
            # Image to PDF
            on_progress(20.0, f"Converting image {src.name} to PDF...")
            merge_images_to_pdf([src], tmp_out)
        elif src.suffix.lower() == ".pdf":
            # PDF to image
            on_progress(20.0, f"Rendering PDF pages to {dst_fmt.upper()}...")
            rendered = pdf_to_images(
                src,
                out_dir=tmp_out.parent,
                fmt=dst_fmt,
                cancel=cancel,
                on_progress=on_progress,
            )
            if not rendered:
                raise CuttleError(
                    code="E_CONV_FAILED",
                    user_message=f"No image pages could be rendered from '{src.name}'.",
                    detail="pdf_to_images returned empty list.",
                )

            # Move or copy the first rendered page to tmp_out so the primary expected output exists
            if rendered[0] != tmp_out:
                shutil.copyfile(rendered[0], tmp_out)
        else:
            raise CuttleError(
                code="E_UNSUPPORTED",
                user_message=f"Unsupported format conversion from '{src.suffix}' to '{dst_fmt}'.",
                detail="ImagePdfAdapter only supports PDF to Image and Image to PDF.",
            )

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled after file generation.",
            )

        on_progress(100.0, "Done")

    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Validate converted image or PDF file."""
        clean_name = out.name.removesuffix(".cuttle-part").lower()
        if clean_name.endswith(".pdf") or (src.suffix.lower() != ".pdf"):
            return validate_pdf(out)

        # Validate image file
        try:
            with Image.open(out) as img:
                img.verify()
            return ValidationResult(ok=True)
        except Exception as exc:
            return ValidationResult(ok=False, reason=f"Invalid image file: {exc}")
