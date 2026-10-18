"""Platform-specific utilities and abstractions for Cuttle.

Per AGENTS.md:
Engine has no OS specific code. Windows code only in cuttle/platform/windows and cuttle/shell.
"""

from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProcessGuard(Protocol):
    """Protocol for platform process tree supervisors."""

    def assign_process(self, pid: int) -> bool:
        """Assign process pid to the supervision tree."""
        ...

    def terminate(self, exit_code: int = 1) -> None:
        """Terminate all supervised processes in the tree."""
        ...

    def close(self) -> None:
        """Release underlying resources."""
        ...


class NullProcessGuard:
    """Fallback no-op process guard for non-Windows platforms."""

    def assign_process(self, pid: int) -> bool:
        return True

    def terminate(self, exit_code: int = 1) -> None:
        pass

    def close(self) -> None:
        pass


def create_process_guard() -> ProcessGuard:
    """Return a platform-appropriate ProcessGuard instance."""
    if sys.platform == "win32":
        from cuttle.platform.windows.jobobject import WindowsJobObject

        return WindowsJobObject()
    return NullProcessGuard()
