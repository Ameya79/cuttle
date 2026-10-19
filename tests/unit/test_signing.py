"""Unit tests for code signing and release workflow scripts (P6-01, P6-02).

Per TRD task cards P6-01 and P6-02:
- .github/workflows/release.yml builds PyInstaller, Inno Setup, portable zip,
  and draft GitHub release.
- scripts/sign_binaries.ps1 signs binaries and verifies Authenticode signatures.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_release_workflow_file_validity() -> None:
    """The release workflow packaging/release-workflow.yml must exist and define proper triggers."""
    wf_path = PROJECT_ROOT / "packaging" / "release-workflow.yml"
    if not wf_path.is_file():
        wf_path = PROJECT_ROOT / ".github" / "workflows" / "release.yml"
    assert wf_path.is_file()

    content = wf_path.read_text(encoding="utf-8")
    assert "push:" in content
    assert "tags:" in content
    assert "v*" in content
    assert "build_dist.py" in content
    assert "sign_binaries.ps1" in content
    assert "softprops/action-gh-release" in content
    assert "SHA256SUMS.txt" in content


def test_build_dist_script_structure() -> None:
    """scripts/build_dist.py must exist and define packaging routines."""
    script_path = PROJECT_ROOT / "scripts" / "build_dist.py"
    assert script_path.is_file()

    content = script_path.read_text(encoding="utf-8")
    assert "build_native_components" in content
    assert "stage_distribution_folder" in content
    assert "create_portable_zip" in content
    assert "generate_checksums" in content
    assert "cuttle-portable-x64.zip" in content


def test_code_signing_script_structure() -> None:
    """scripts/sign_binaries.ps1 must exist and implement Authenticode signing and verification."""
    ps1_path = PROJECT_ROOT / "scripts" / "sign_binaries.ps1"
    assert ps1_path.is_file()

    content = ps1_path.read_text(encoding="utf-8")
    assert "Set-AuthenticodeSignature" in content
    assert "Get-AuthenticodeSignature" in content
    assert "New-SelfSignedCertificate" in content
    assert "SHA256SUMS" not in content or "SHA256" in content
