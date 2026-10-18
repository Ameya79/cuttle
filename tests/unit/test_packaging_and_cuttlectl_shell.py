"""Unit tests for packaging configuration and cuttlectl shell subcommands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from cuttle.worker.cuttlectl import main


def test_cuttlectl_shorthand_arg_rewriting(tmp_path: Path) -> None:
    sample_file = tmp_path / "song.wav"
    sample_file.write_text("audio")

    # Invoking with shorthand: cuttlectl <file> <to>
    with patch("cuttle.worker.cuttlectl.cmd_submit") as mock_submit:
        mock_submit.return_value = 0
        ret = main([str(sample_file), "mp3"])
        assert ret == 0
        mock_submit.assert_called_once()
        args = mock_submit.call_args[0][0]
        assert args.to == "mp3"
        assert args.files == [str(sample_file)]


def test_cuttlectl_install_shell_subcommand(tmp_path: Path) -> None:
    manifest_path = tmp_path / "installed_keys.json"

    with patch(
        "cuttle.shell.registry_installer.install_context_menus", return_value=["key1", "key2"]
    ) as mock_install:
        ret = main(["install-shell", "--manifest", str(manifest_path)])
        assert ret == 0
        mock_install.assert_called_once()
        cfg = mock_install.call_args[0][0]
        assert cfg.manifest_path == str(manifest_path)


def test_cuttlectl_uninstall_shell_subcommand(tmp_path: Path) -> None:
    manifest_path = tmp_path / "installed_keys.json"

    with patch(
        "cuttle.shell.registry_installer.uninstall_context_menus", return_value=5
    ) as mock_uninstall:
        ret = main(["uninstall-shell", "--manifest", str(manifest_path)])
        assert ret == 0
        mock_uninstall.assert_called_once()
        cfg = mock_uninstall.call_args[0][0]
        assert cfg.manifest_path == str(manifest_path)


def test_packaging_spec_file_validity() -> None:
    root = Path(__file__).resolve().parent.parent.parent
    spec_file = root / "packaging" / "cuttle.spec"
    assert spec_file.is_file()

    content = spec_file.read_text(encoding="utf-8")
    assert "cli.py" in content
    assert "cuttlectl.py" in content
    assert "main.py" in content
    assert 'name="cuttle"' in content or "name='cuttle'" in content
    assert 'name="cuttlectl"' in content or "name='cuttlectl'" in content
    assert 'name="cuttle-worker"' in content or "name='cuttle-worker'" in content


def test_inno_setup_script_validity() -> None:
    root = Path(__file__).resolve().parent.parent.parent
    iss_file = root / "packaging" / "installer.iss"
    assert iss_file.is_file()

    content = iss_file.read_text(encoding="utf-8")
    assert "MyAppName" in content
    assert "cuttlectl.exe" in content
    assert "install-shell" in content
    assert "uninstall-shell" in content
