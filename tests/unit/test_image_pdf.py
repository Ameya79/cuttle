"""Unit tests for PDF and image extras (P5-04).

Per TRD task card P5-04:
- PDF to images (render pages to images).
- Images to PDF.
- Merge several selected images into one PDF in exact specified order.
- Tests for page counts and order.
"""

from __future__ import annotations

from pathlib import Path

import pypdf
import pytest
from PIL import Image

from cuttle.adapters.image_pdf import (
    ImagePdfAdapter,
    merge_images_to_pdf,
    pdf_to_images,
)
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import CancelToken, Quality


def create_colored_image(path: Path, color: tuple[int, int, int]) -> Path:
    """Create a 100x100 solid color RGB test image."""
    img = Image.new("RGB", (100, 100), color=color)
    img.save(path, format="PNG")
    return path


def create_multi_page_pdf(path: Path, page_count: int = 3) -> Path:
    """Generate a multi-page PDF using pypdf."""
    writer = pypdf.PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=200, height=200)

    with open(path, "wb") as f:
        writer.write(f)

    return path


def test_image_pdf_adapter_capabilities() -> None:
    """ImagePdfAdapter supports bidirectional image <-> PDF conversions."""
    adapter = ImagePdfAdapter()
    assert adapter.can_convert("pdf", "png") == Quality.LOSSLESS
    assert adapter.can_convert("pdf", "jpg") == Quality.LOSSY
    assert adapter.can_convert("png", "pdf") == Quality.LOSSLESS
    assert adapter.can_convert("jpg", "pdf") == Quality.LOSSY
    assert adapter.can_convert("txt", "pdf") is None


def test_single_image_to_pdf(tmp_path: Path) -> None:
    """Single image converted to PDF produces valid 1-page document."""
    img_path = create_colored_image(tmp_path / "photo.png", (255, 100, 50))
    out_pdf = tmp_path / "photo.pdf"

    adapter = ImagePdfAdapter()
    plan = adapter.plan(img_path, "pdf", out_pdf, {})
    cancel = CancelToken()
    adapter.run(plan, on_progress=lambda p, m: None, cancel=cancel)

    assert out_pdf.is_file()
    reader = pypdf.PdfReader(str(out_pdf))
    assert len(reader.pages) == 1

    val_res = adapter.validate(img_path, out_pdf)
    assert val_res.ok is True


def test_pdf_to_images_page_count(tmp_path: Path) -> None:
    """PDF with 3 pages renders into exactly 3 image files."""
    pdf_path = create_multi_page_pdf(tmp_path / "document.pdf", page_count=3)
    out_dir = tmp_path / "rendered"

    images = pdf_to_images(pdf_path, out_dir=out_dir, fmt="png")
    assert len(images) == 3
    for img_file in images:
        assert img_file.is_file()
        with Image.open(img_file) as im:
            assert im.width > 0
            assert im.height > 0


def test_merge_several_images_into_one_pdf_preserves_count_and_order(tmp_path: Path) -> None:
    """Merge 3 images (Red, Green, Blue) into one PDF, asserting exact page count and sequence."""
    red_img = create_colored_image(tmp_path / "1_red.png", (255, 0, 0))
    green_img = create_colored_image(tmp_path / "2_green.png", (0, 255, 0))
    blue_img = create_colored_image(tmp_path / "3_blue.png", (0, 0, 255))

    ordered_inputs = [red_img, green_img, blue_img]
    out_pdf = tmp_path / "merged_palette.pdf"

    merge_images_to_pdf(ordered_inputs, out_pdf)

    assert out_pdf.is_file()
    reader = pypdf.PdfReader(str(out_pdf))
    # Test page count
    assert len(reader.pages) == 3

    # Render pages back to verify color ordering
    rendered_pages = pdf_to_images(out_pdf, out_dir=tmp_path / "extracted", fmt="png")
    assert len(rendered_pages) == 3

    with Image.open(rendered_pages[0]) as p1:
        rgb1 = p1.convert("RGB").getpixel((50, 50))
        # First page must be red (high red, low green/blue)
        assert rgb1[0] > 200 and rgb1[1] < 50 and rgb1[2] < 50

    with Image.open(rendered_pages[1]) as p2:
        rgb2 = p2.convert("RGB").getpixel((50, 50))
        # Second page must be green
        assert rgb2[0] < 50 and rgb2[1] > 200 and rgb2[2] < 50

    with Image.open(rendered_pages[2]) as p3:
        rgb3 = p3.convert("RGB").getpixel((50, 50))
        # Third page must be blue
        assert rgb3[0] < 50 and rgb3[1] < 50 and rgb3[2] > 200


def test_cancellation_honored(tmp_path: Path) -> None:
    """Cancelled token terminates operation cleanly."""
    pdf_path = create_multi_page_pdf(tmp_path / "document.pdf", page_count=2)
    adapter = ImagePdfAdapter()
    plan = adapter.plan(pdf_path, "png", tmp_path / "out.png", {})

    cancel = CancelToken()
    cancel.cancel()

    with pytest.raises(CuttleError) as exc_info:
        adapter.run(plan, on_progress=lambda p, m: None, cancel=cancel)
    assert exc_info.value.code == "E_CANCELLED"
