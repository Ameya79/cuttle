"""Lightweight CLI launcher invoked by Windows File Explorer context menus.

Per TRD §6.8 and task card P2-05:
- Ultra-low overhead: starts up and exits in under 20 milliseconds.
- Auto-starts background worker daemon if not already running.
- Dispatches convert, cancel, and ping commands over Windows Named Pipe.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from cuttle.platform.windows.pipe import call_pipe, get_default_pipe_name


def ensure_worker_running(
    pipe_name: str | None = None,
    timeout_s: float = 6.0,
) -> str:
    """Ensure background worker daemon is active; launch if missing.

    Returns:
        The active pipe name.
    """
    target_pipe = pipe_name or get_default_pipe_name()

    # 1. Quick probe
    try:
        ping_payload = json.dumps({"op": "ping"}).encode("utf-8")
        resp_raw = call_pipe(target_pipe, ping_payload, timeout_ms=200)
        resp = json.loads(resp_raw.decode("utf-8"))
        if resp.get("status") == "ok":
            return target_pipe
    except Exception:
        pass

    # 2. Worker is not running; auto-launch background process
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )

    project_root = Path(__file__).resolve().parent.parent.parent
    py_exec = sys.executable
    if sys.platform == "win32":
        candidate_pythonw = Path(sys.executable).with_name("pythonw.exe")
        if candidate_pythonw.is_file():
            py_exec = str(candidate_pythonw)

    cmd = [py_exec, "-m", "cuttle.worker.main"]
    if pipe_name:
        cmd.extend(["--pipe", pipe_name])

    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    subprocess.Popen(
        cmd,
        cwd=str(project_root),
        env=env,
        creationflags=creationflags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )

    # 3. Wait for pipe to become available
    start = time.monotonic()
    while (time.monotonic() - start) < timeout_s:
        try:
            resp_raw = call_pipe(
                target_pipe,
                json.dumps({"op": "ping"}).encode("utf-8"),
                timeout_ms=500,
            )
            resp = json.loads(resp_raw.decode("utf-8"))
            if resp.get("status") == "ok":
                return target_pipe
        except Exception:
            time.sleep(0.05)

    raise TimeoutError(f"Failed to connect to worker pipe {target_pipe} after {timeout_s}s")


def cmd_submit(args: argparse.Namespace) -> int:
    """Handle 'cuttlectl submit' command."""
    target_fmt = args.to.lower().lstrip(".")
    files: list[Path] = [Path(f) for f in args.files]

    # Validate file existence
    missing = [f for f in files if not f.exists()]
    if missing:
        print(f"Error: {len(missing)} files do not exist: {missing[0]}", file=sys.stderr)
        return 1

    try:
        pipe_name = ensure_worker_running(args.pipe)
    except Exception as e:
        print(f"Error: Could not reach or start Cuttle worker daemon: {e}", file=sys.stderr)
        return 1

    batch_id: str | None = None
    out_dir_str = str(Path(args.out_dir).resolve()) if args.out_dir else None

    for f in files:
        req = {
            "op": "convert",
            "src": str(f.resolve()),
            "dst": target_fmt,
        }
        if out_dir_str:
            req["out_dir"] = out_dir_str

        try:
            resp_raw = call_pipe(pipe_name, json.dumps(req).encode("utf-8"))
            resp = json.loads(resp_raw.decode("utf-8"))
            if resp.get("status") != "queued":
                print(f"Warning: Unexpected server response for {f.name}: {resp}", file=sys.stderr)
            elif batch_id is None:
                batch_id = resp.get("batch_id")
        except Exception as e:
            print(f"Error submitting {f.name}: {e}", file=sys.stderr)
            return 1

    print(f"Submitted {len(files)} file(s) for conversion to {target_fmt} (Batch: {batch_id})")
    return 0


def cmd_ping(args: argparse.Namespace) -> int:
    """Handle 'cuttlectl ping' command."""
    pipe_name = args.pipe or get_default_pipe_name()
    try:
        resp_raw = call_pipe(pipe_name, json.dumps({"op": "ping"}).encode("utf-8"), timeout_ms=1000)
        resp = json.loads(resp_raw.decode("utf-8"))
        if resp.get("status") == "ok":
            print("Cuttle worker daemon is active (pong).")
            return 0
        print(f"Worker returned error status: {resp}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Cuttle worker daemon is not running: {e}", file=sys.stderr)
        return 1


def cmd_cancel(args: argparse.Namespace) -> int:
    """Handle 'cuttlectl cancel' command."""
    pipe_name = args.pipe or get_default_pipe_name()
    if args.job:
        req = {"op": "cancel_job", "job_id": args.job}
    elif args.batch:
        req = {"op": "cancel_batch", "batch_id": args.batch}
    else:
        print("Error: Specify either --job <id> or --batch <id>", file=sys.stderr)
        return 1

    try:
        resp_raw = call_pipe(pipe_name, json.dumps(req).encode("utf-8"), timeout_ms=2000)
        resp = json.loads(resp_raw.decode("utf-8"))
        print(f"Cancellation dispatched: {resp}")
        return 0
    except Exception as e:
        print(f"Failed to cancel: {e}", file=sys.stderr)
        return 1


def cmd_install_shell(args: argparse.Namespace) -> int:
    """Handle 'cuttlectl install-shell' command."""
    from cuttle.shell.registry_installer import RegistryConfig, install_context_menus

    cfg = RegistryConfig(
        base_path=args.base_path or r"Software\Classes",
        manifest_path=args.manifest,
    )
    keys = install_context_menus(cfg)
    print(f"Registered {len(keys)} context menu keys.")
    return 0


def cmd_uninstall_shell(args: argparse.Namespace) -> int:
    """Handle 'cuttlectl uninstall-shell' command."""
    from cuttle.shell.registry_installer import RegistryConfig, uninstall_context_menus

    cfg = RegistryConfig(
        base_path=args.base_path or r"Software\Classes",
        manifest_path=args.manifest,
    )
    count = uninstall_context_menus(cfg)
    print(f"Uninstalled {count} context menu keys.")
    return 0


def cmd_missing_tool(args: argparse.Namespace) -> int:
    """Handle 'cuttlectl missing-tool' command."""
    from cuttle.ui.missing_tool_dialog import show_missing_tool_dialog

    show_missing_tool_dialog(tool_name=args.tool)
    return 0


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)

    # Shorthand support: cuttlectl <file1> [<file2> ...] <target_fmt>
    known_cmds = {
        "submit",
        "ping",
        "cancel",
        "install-shell",
        "uninstall-shell",
        "missing-tool",
        "-h",
        "--help",
    }
    if (
        raw_args
        and raw_args[0] not in known_cmds
        and not raw_args[0].startswith("-")
        and len(raw_args) >= 2
    ):
        target_fmt = raw_args[-1]
        files = raw_args[:-1]
        raw_args = ["submit", "--to", target_fmt, *files]

    parser = argparse.ArgumentParser(
        prog="cuttlectl",
        description="Fast launcher and controller for Cuttle file conversions",
    )
    parser.add_argument("--pipe", default=None, help="Custom named pipe name")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Submit subcommand
    p_submit = subparsers.add_parser("submit", help="Submit files for conversion")
    p_submit.add_argument("--to", required=True, help="Target format extension (e.g. mp3, png)")
    p_submit.add_argument("--out-dir", default=None, help="Optional output directory")
    p_submit.add_argument("files", nargs="+", help="One or more file paths to convert")
    p_submit.set_defaults(func=cmd_submit)

    # Ping subcommand
    p_ping = subparsers.add_parser("ping", help="Check worker status")
    p_ping.set_defaults(func=cmd_ping)

    # Cancel subcommand
    p_cancel = subparsers.add_parser("cancel", help="Cancel conversion job or batch")
    p_cancel.add_argument("--job", default=None, help="Specific job ID to cancel")
    p_cancel.add_argument("--batch", default=None, help="Specific batch ID to cancel")
    p_cancel.set_defaults(func=cmd_cancel)

    # install-shell subcommand
    p_install = subparsers.add_parser("install-shell", help="Register Explorer context menus")
    p_install.add_argument("--base-path", default=None, help="Custom registry base path")
    p_install.add_argument("--manifest", default=None, help="Custom manifest file path")
    p_install.set_defaults(func=cmd_install_shell)

    # uninstall-shell subcommand
    p_uninstall = subparsers.add_parser("uninstall-shell", help="Remove Explorer context menus")
    p_uninstall.add_argument("--base-path", default=None, help="Custom registry base path")
    p_uninstall.add_argument("--manifest", default=None, help="Custom manifest file path")
    p_uninstall.set_defaults(func=cmd_uninstall_shell)

    # missing-tool subcommand
    p_missing = subparsers.add_parser("missing-tool", help="Display missing tool guidance dialog")
    p_missing.add_argument("tool", default="libreoffice", nargs="?", help="Tool name")
    p_missing.set_defaults(func=cmd_missing_tool)

    args = parser.parse_args(raw_args)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
