"""Unit tests for the Cuttle static landing page and download portal (P6-05).

Per TRD task card P6-05:
- Landing page includes big download button.
- "Your files never leave your PC" privacy guarantee.
- Feature walkthrough demo and format explorer.
- Link to docs/quality.md.
- Checksum verification and package manager install commands.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SITE_DIR = PROJECT_ROOT / "site"


def test_site_assets_exist() -> None:
    """Core HTML, CSS, and JS files must exist in site/ directory."""
    assert (SITE_DIR / "index.html").is_file()
    assert (SITE_DIR / "styles.css").is_file()
    assert (SITE_DIR / "script.js").is_file()
    assert (SITE_DIR / "README.md").is_file()


def test_landing_page_html_structure() -> None:
    """index.html must have proper semantic structure, single h1, and meta tags."""
    content = (SITE_DIR / "index.html").read_text(encoding="utf-8")

    assert "<!DOCTYPE html>" in content
    assert "<title>Cuttle — Offline Windows Right-Click File Converter</title>" in content
    assert 'meta name="description"' in content
    assert content.count("<h1") == 1
    assert "Right-Click Any File" in content

    # Navigation & Semantic Sections
    assert 'id="navbar"' in content
    assert 'id="hero"' in content
    assert 'id="privacy"' in content
    assert 'id="features"' in content
    assert 'id="formats"' in content
    assert 'id="install"' in content


def test_download_links_and_package_commands() -> None:
    """Download buttons and package manager commands must be correctly defined."""
    content = (SITE_DIR / "index.html").read_text(encoding="utf-8")

    # Installer and portable links
    setup_url = "https://github.com/Ameya79/cuttle/releases/latest/download/cuttle-setup-x64.exe"
    zip_url = "https://github.com/Ameya79/cuttle/releases/latest/download/cuttle-portable-x64.zip"
    assert setup_url in content
    assert zip_url in content

    # Package managers
    assert "winget install Ameya79.Cuttle" in content
    assert "docs/quality.md" in content

    # Script commands for Scoop and Chocolatey
    js_content = (SITE_DIR / "script.js").read_text(encoding="utf-8")
    assert "scoop install cuttle" in js_content
    assert "choco install cuttle" in js_content


def test_privacy_guarantee_present() -> None:
    """Privacy guarantee banner must explicitly reassure users that files never leave PC."""
    content = (SITE_DIR / "index.html").read_text(encoding="utf-8")
    assert "Your files never leave your PC" in content
    assert "Zero Network Calls" in content
    assert "GPL-3.0" in content
