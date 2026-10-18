"""Cuttle engine error types.

Every user-facing error is a CuttleError with a code from ERROR_CODES,
a plain-English user_message, and an optional technical detail string.
See TRD §6.2.
"""

from __future__ import annotations


class CuttleError(Exception):
    """Base exception for all Cuttle engine errors.

    Attributes:
        code: One of the ERROR_CODES below.
        user_message: Plain-English message safe to show to non-technical users.
        detail: Technical details for logs and bug reports. Never shown to users.
    """

    def __init__(self, code: str, user_message: str, detail: str = "") -> None:
        super().__init__(user_message)
        if code not in ERROR_CODES:
            raise ValueError(f"Unknown error code {code!r}. Add it to ERROR_CODES before using it.")
        self.code = code
        self.user_message = user_message
        self.detail = detail


# Allowed error codes.  Add a new one only by editing this tuple and the tests.
ERROR_CODES = (
    "E_UNSUPPORTED",
    "E_SRC_MISSING",
    "E_SRC_LOCKED",
    "E_SRC_PASSWORD",
    "E_SRC_CORRUPT",
    "E_TOOL_MISSING",
    "E_TOOL_FAILED",
    "E_TIMEOUT",
    "E_VALIDATION",
    "E_DISK_SPACE",
    "E_CANCELLED",
)
