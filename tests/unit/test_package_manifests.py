"""Unit tests for package manager manifests (P6-03).

Per TRD task card P6-03:
- winget manifest in packaging/winget/
- Scoop manifest in packaging/scoop/
- Chocolatey package in packaging/chocolatey/
- Test each locally before submitting.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_winget_manifest_validity() -> None:
    """Validate winget manifest keys, architecture, and installer configuration."""
    winget_file = PROJECT_ROOT / "packaging" / "winget" / "cuttle.yaml"
    assert winget_file.is_file()

    text = winget_file.read_text(encoding="utf-8")
    assert "PackageIdentifier: Ameya79.Cuttle" in text
    assert "PackageVersion: 1.0.0" in text
    assert "InstallerType: inno" in text
    assert "Cuttle-Setup-x64.exe" in text
    assert "Scope: user" in text


def test_scoop_manifest_validity() -> None:
    """Validate Scoop manifest JSON structure and binary entries."""
    scoop_file = PROJECT_ROOT / "packaging" / "scoop" / "cuttle.json"
    assert scoop_file.is_file()

    data = json.loads(scoop_file.read_text(encoding="utf-8"))
    assert data["version"] == "1.0.0"
    assert data["license"] == "GPL-3.0-only"
    assert "cuttle.exe" in data["bin"]
    assert "cuttlectl.exe" in data["bin"]
    assert "cuttle-portable-x64.zip" in data["architecture"]["64bit"]["url"]
    assert any("install-shell" in cmd for cmd in data.get("post_install", []))
    assert any("uninstall-shell" in cmd for cmd in data.get("pre_uninstall", []))


def test_chocolatey_manifest_validity() -> None:
    """Validate Chocolatey nuspec XML and automation scripts."""
    nuspec_file = PROJECT_ROOT / "packaging" / "chocolatey" / "cuttle.nuspec"
    assert nuspec_file.is_file()

    tree = ET.parse(nuspec_file)
    root = tree.getroot()

    # Find metadata elements irrespective of namespace
    id_elem = root.find(".//{*}id")
    assert id_elem is not None and id_elem.text == "cuttle"

    version_elem = root.find(".//{*}version")
    assert version_elem is not None and version_elem.text == "1.0.0"

    install_ps1 = PROJECT_ROOT / "packaging" / "chocolatey" / "tools" / "chocolateyinstall.ps1"
    uninstall_ps1 = PROJECT_ROOT / "packaging" / "chocolatey" / "tools" / "chocolateyuninstall.ps1"

    assert install_ps1.is_file()
    assert uninstall_ps1.is_file()

    install_text = install_ps1.read_text(encoding="utf-8")
    assert "Install-ChocolateyPackage" in install_text
    assert "Cuttle-Setup-x64.exe" in install_text
