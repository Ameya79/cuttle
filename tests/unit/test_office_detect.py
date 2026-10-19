"""Unit tests for Windows LibreOffice detection.

Per task card P3-02:
- Find soffice.exe in fake directory trees.
- Query App Paths registry.
- Extract version string.
- Return installed=False when missing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from cuttle.platform.windows.office_detect import (
    OfficeInfo,
    detect_office,
    probe_soffice_version,
)


def test_office_info_defaults() -> None:
    info = OfficeInfo(installed=False)
    assert not info.installed
    assert info.path is None
    assert info.version is None
    assert info.name == "LibreOffice"


def test_detect_office_fake_directory(tmp_path: Path) -> None:
    fake_program_dir = tmp_path / "LibreOffice" / "program"
    fake_program_dir.mkdir(parents=True)
    fake_soffice = fake_program_dir / "soffice.exe"
    fake_soffice.write_bytes(b"MZfakebinary")

    with patch(
        "cuttle.platform.windows.office_detect.probe_soffice_version",
        return_value="LibreOffice 24.8.2.1",
    ):
        info = detect_office(
            search_paths=[fake_soffice],
            check_registry=False,
            probe_version=True,
        )

    assert info.installed is True
    assert info.path == fake_soffice
    assert info.version == "LibreOffice 24.8.2.1"


def test_detect_office_registry_mock(tmp_path: Path) -> None:
    fake_exe = tmp_path / "soffice.exe"
    fake_exe.write_bytes(b"fake")

    with (
        patch(
            "cuttle.platform.windows.office_detect._query_registry_app_path",
            return_value=fake_exe,
        ),
        patch(
            "cuttle.platform.windows.office_detect.probe_soffice_version",
            return_value="LibreOffice 7.6.4",
        ),
    ):
        info = detect_office(search_paths=[], check_registry=True, probe_version=True)

    assert info.installed is True
    assert info.path == fake_exe
    assert info.version == "LibreOffice 7.6.4"


def test_detect_office_not_installed() -> None:
    with (
        patch(
            "cuttle.platform.windows.office_detect._query_registry_app_path",
            return_value=None,
        ),
        patch("shutil.which", return_value=None),
        patch(
            "cuttle.platform.windows.office_detect.get_common_office_paths",
            return_value=[],
        ),
    ):
        info = detect_office(search_paths=[], check_registry=True, probe_version=False)

    assert info.installed is False
    assert info.path is None
    assert info.version is None


def test_probe_soffice_version_success(tmp_path: Path) -> None:
    fake_exe = tmp_path / "soffice.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "LibreOffice 24.2.1.2 420(mb1)\n"

        ver = probe_soffice_version(fake_exe)
        assert ver == "LibreOffice 24.2.1.2 420(mb1)"


def test_probe_soffice_version_failure(tmp_path: Path) -> None:
    fake_exe = tmp_path / "soffice.exe"
    fake_exe.write_text("stub", encoding="utf-8")

    with patch("subprocess.run", side_effect=OSError("Exec failed")):
        ver = probe_soffice_version(fake_exe)
        assert ver is None
