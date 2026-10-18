"""Placeholder test — verifies the skeleton is wired correctly."""

from cuttle import __version__


def test_version_exists() -> None:
    """The package exposes a version string."""
    assert isinstance(__version__, str)
    assert __version__ == "0.1.0"


def test_cli_entry_point_imports() -> None:
    """The CLI app object can be imported without errors."""
    from cuttle.cli import app  # noqa: F401
