"""Cuttle CLI — the only place that prints to stdout."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="cuttle",
    help="Right-click file converter. Convert files from the command line.",
    no_args_is_help=True,
)


@app.command()
def doctor() -> None:
    """Check which conversion tools are available."""
    typer.echo("Cuttle doctor: tool check not yet implemented.")
    raise typer.Exit(code=0)
