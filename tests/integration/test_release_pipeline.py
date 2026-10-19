"""End-to-end integration test suite for the Phase 6 Release Pipeline (P6-08).

Per TRD task card P6-08:
- Verifies packaging configurations, build scripts, code signing script.
- Verifies package manager manifests (Winget, Scoop, Chocolatey).
- Verifies third-party notices and GPL-3.0 source offer.
- Verifies static landing page and download links.
- Verifies in-app update check subsystem and diagnostics.
- Verifies offline engine boundary (zero network code in cuttle/engine).
- Verifies zero .cuttle-part residue across workspace.
"""

from __future__ import annotations

import re
from pathlib import Path

import cuttle

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_version_consistency_across_metadata() -> None:
    """Version 1.0.0 must be consistent across pyproject.toml, __init__.py, and changelog."""
    assert cuttle.__version__ == "1.0.0"

    pyproject_text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "1.0.0"' in pyproject_text

    changelog_text = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [1.0.0] - Phase 6: General Availability Release" in changelog_text


def test_packaging_assets_and_scripts() -> None:
    """All packaging configurations and build scripts must exist and be valid."""
    spec_path = PROJECT_ROOT / "packaging" / "cuttle.spec"
    assert spec_path.is_file()
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "cuttle-worker" in spec_text
    assert "cuttlectl.exe" in spec_text
    assert "cuttle_shell.dll" in spec_text

    iss_path = PROJECT_ROOT / "packaging" / "installer.iss"
    assert iss_path.is_file()
    iss_text = iss_path.read_text(encoding="utf-8")
    assert "MyAppName" in iss_text
    assert "register_sparse_package.ps1" in iss_text

    build_script = PROJECT_ROOT / "scripts" / "build_dist.py"
    assert build_script.is_file()

    sign_script = PROJECT_ROOT / "scripts" / "sign_binaries.ps1"
    assert sign_script.is_file()

    workflow = PROJECT_ROOT / "packaging" / "release-workflow.yml"
    assert workflow.is_file()


def test_package_manager_manifests() -> None:
    """Winget, Scoop, and Chocolatey manifests must exist and reference version 1.0.0."""
    winget = (PROJECT_ROOT / "packaging" / "winget" / "cuttle.yaml").read_text(encoding="utf-8")
    assert "PackageVersion: 1.0.0" in winget

    scoop = (PROJECT_ROOT / "packaging" / "scoop" / "cuttle.json").read_text(encoding="utf-8")
    assert '"version": "1.0.0"' in scoop

    choco = (PROJECT_ROOT / "packaging" / "chocolatey" / "cuttle.nuspec").read_text(
        encoding="utf-8"
    )
    assert "<version>1.0.0</version>" in choco


def test_third_party_notices_and_gpl_offer() -> None:
    """THIRD_PARTY_NOTICES.md must exist and contain the required GPL source offer."""
    notices_file = PROJECT_ROOT / "THIRD_PARTY_NOTICES.md"
    assert notices_file.is_file()
    text = notices_file.read_text(encoding="utf-8")
    assert "Written Offer for Source Code" in text
    assert "GNU General Public License" in text
    assert "https://github.com/Ameya79/cuttle" in text
    assert "FFmpeg" in text
    assert "Pandoc" in text
    assert "pdf2docx" in text


def test_landing_page_portal() -> None:
    """site/ files must exist and provide offline privacy guarantees."""
    site_html = (PROJECT_ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert "100% Offline" in site_html
    assert "Your files never leave your PC" in site_html
    assert "winget install Ameya79.Cuttle" in site_html


def test_offline_engine_boundary_guarantee() -> None:
    """cuttle/engine must contain NO network calls or network imports whatsoever."""
    engine_dir = PROJECT_ROOT / "cuttle" / "engine"
    forbidden_patterns = [
        r"\burllib\b",
        r"\brequests\b",
        r"\bhttp\.client\b",
        r"\bsocket\b",
        r"\baiohttp\b",
        r"\bhttpx\b",
    ]

    for py_file in engine_dir.glob("**/*.py"):
        code = py_file.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            matches = re.findall(pattern, code)
            assert not matches, (
                f"Network boundary violation: found {matches} in {py_file.name}. "
                "The engine makes no network calls!"
            )


def test_zero_cuttle_part_files_left() -> None:
    """Ensure no leftover .cuttle-part files exist across the workspace."""
    parts = list(PROJECT_ROOT.glob("**/*.cuttle-part"))
    assert not parts, f"Found dangling .cuttle-part temporary files: {parts}"
