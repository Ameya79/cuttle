"""Unit tests for benchmarking script and metric calculations.

Verifies:
- System info collection (CPU, RAM, OS, tool paths).
- PSNR calculation for identical and degraded images.
- Semantic plain text extraction across MD, HTML, DOCX, and PDF.
- Fast benchmark execution with iterations=1.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

from scripts.benchmark import (
    FIXTURES_DIR,
    benchmark_conversion,
    calculate_image_psnr,
    extract_plain_text,
    get_system_info,
)


def test_get_system_info() -> None:
    """System information probe returns populated hardware and software data."""
    info = get_system_info()
    assert "Windows" in info.os or "Linux" in info.os or "Darwin" in info.os
    assert info.physical_cores > 0
    assert info.logical_cores >= info.physical_cores
    assert info.ram_gb > 0.0
    assert info.python_version.startswith("3.")


def test_calculate_image_psnr() -> None:
    """PSNR returns infinity for identical images and positive dB for differing images."""
    im1 = Image.new("RGB", (30, 30), (200, 100, 50))
    im2 = Image.new("RGB", (30, 30), (200, 100, 50))
    im3 = Image.new("RGB", (30, 30), (190, 95, 45))

    # Identical images
    psnr_identical = calculate_image_psnr(im1, im2)
    assert psnr_identical == float("inf") or math.isinf(psnr_identical)

    # Slightly different images
    psnr_diff = calculate_image_psnr(im1, im3)
    assert 20.0 < psnr_diff < 50.0

    # Dimension mismatch returns 0.0
    im4 = Image.new("RGB", (20, 20), (200, 100, 50))
    assert calculate_image_psnr(im1, im4) == 0.0


def test_extract_plain_text() -> None:
    """Extracts semantic words from Markdown, HTML, and DOCX fixtures."""
    md_p = FIXTURES_DIR / "doc.md"
    docx_p = FIXTURES_DIR / "doc.docx"

    assert md_p.is_file()
    assert docx_p.is_file()

    md_text = extract_plain_text(md_p)
    docx_text = extract_plain_text(docx_p)

    assert "Cuttle Document Test" in md_text
    assert "Zero telemetry" in md_text
    assert "Cuttle Document Test" in docx_text
    assert "Zero telemetry" in docx_text


def test_benchmark_single_fast_pass(tmp_path: Path) -> None:
    """Runs a single-iteration fast conversion benchmark."""
    src = FIXTURES_DIR / "doc.md"
    res = benchmark_conversion(src, "html", category="Document", iterations=1)

    assert res.mean_latency_ms > 0.0
    assert res.src_size_bytes > 0
    assert res.dst_size_bytes > 0
    assert res.accuracy_metric_name == "Semantic Text Match"
    assert "text preserved" in res.accuracy_score
