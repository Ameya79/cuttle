"""Unit tests for Windows 11 sparse package configuration and registration scripts.

Per task card P4-04:
- Validates packaging/AppxManifest.xml schema and extension declarations.
- Validates registration and unregistration PowerShell scripts.
- Validates docs/dev-windows-shell.md documentation.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = ROOT_DIR / "packaging" / "AppxManifest.xml"
REGISTER_SCRIPT = ROOT_DIR / "scripts" / "register_sparse_package.ps1"
UNREGISTER_SCRIPT = ROOT_DIR / "scripts" / "unregister_sparse_package.ps1"
DOCS_PATH = ROOT_DIR / "docs" / "dev-windows-shell.md"


class TestSparsePackageManifest:
    def test_manifest_file_exists_and_is_valid_xml(self) -> None:
        assert MANIFEST_PATH.is_file(), "AppxManifest.xml must exist"
        tree = ET.parse(MANIFEST_PATH)
        root = tree.getroot()
        assert "Package" in root.tag

    def test_identity_and_dependencies(self) -> None:
        tree = ET.parse(MANIFEST_PATH)
        root = tree.getroot()

        # Find Identity element
        identity = None
        for elem in root.iter():
            if elem.tag.endswith("Identity"):
                identity = elem
                break
        assert identity is not None, "Identity element required"
        assert identity.attrib.get("Name") == "Cuttle.Converter"
        assert identity.attrib.get("ProcessorArchitecture") == "x64"

        # Find MinVersion
        min_version = None
        for elem in root.iter():
            if elem.tag.endswith("TargetDeviceFamily"):
                min_version = elem.attrib.get("MinVersion")
                break
        assert min_version == "10.0.22000.0", "Must target Windows 11 build 22000+"

    def test_context_menu_extension_and_clsid(self) -> None:
        tree = ET.parse(MANIFEST_PATH)
        root = tree.getroot()

        verbs = [
            elem.attrib.get("Clsid")
            for elem in root.iter()
            if elem.tag.endswith("Verb") and elem.attrib.get("Clsid")
        ]
        assert len(verbs) >= 2, "Must declare verbs for both * and Directory"
        for clsid in verbs:
            # Clean uppercase compare
            clean_clsid = clsid.strip("{}").upper()
            assert clean_clsid == "F4312356-5D3C-486B-8C92-72188A47559B"


class TestSparsePackageScriptsAndDocs:
    def test_registration_scripts_exist_and_contain_required_commands(self) -> None:
        assert REGISTER_SCRIPT.is_file()
        reg_content = REGISTER_SCRIPT.read_text(encoding="utf-8")
        assert "Add-AppxPackage" in reg_content
        assert "-Register" in reg_content
        assert "regsvr32.exe" in reg_content

        assert UNREGISTER_SCRIPT.is_file()
        unreg_content = UNREGISTER_SCRIPT.read_text(encoding="utf-8")
        assert "Remove-AppxPackage" in unreg_content
        assert "regsvr32.exe" in unreg_content

    def test_documentation_exists(self) -> None:
        assert DOCS_PATH.is_file()
        content = DOCS_PATH.read_text(encoding="utf-8")
        assert "IExplorerCommand" in content
        assert "Sparse Package" in content
        assert "register_sparse_package.ps1" in content
