"""Exceptions for Qirabot SDK."""

from __future__ import annotations

from typing import Any


class QirabotError(Exception):
    """Base exception for all Qirabot SDK errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        status_code: int | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class AuthenticationError(QirabotError):
    """API key is missing or invalid (401)."""


class DeviceBusyError(QirabotError):
    """Device already has a running task (409)."""


class DeviceOfflineError(QirabotError):
    """Device is not connected (400)."""


class LeaseExpiredError(QirabotError):
    """Task lease has expired (409)."""


class ActionError(QirabotError):
    """A device action failed during task."""


class QirabotTimeoutError(QirabotError):
    """Operation timed out (client-side)."""


# Error code → exception class mapping
_ERROR_CODE_MAP: dict[str, type[QirabotError]] = {
    "auth.api_key_missing": AuthenticationError,
    "auth.api_key_invalid": AuthenticationError,
    "sdk.device_busy": DeviceBusyError,
    "sdk.device_not_connected": DeviceOfflineError,
    "sdk.task_not_found": QirabotError,
    "sdk.task_not_active": QirabotError,
    "sdk.lease_expired": LeaseExpiredError,
}

_STATUS_CODE_MAP: dict[int, type[QirabotError]] = {
    401: AuthenticationError,
    409: DeviceBusyError,
}


def raise_for_error(status_code: int, data: dict[str, Any]) -> None:
    """Raise the appropriate exception for an error response.

    Supports both flat format {"code": "...", "message": "..."}
    and nested format {"error": {"code": "...", "message": "..."}}.
    """
    error = data.get("error", {})
    if isinstance(error, str):
        message = error or data.get("message", f"Request failed with status {status_code}")
        code = data.get("code")
    elif error:
        message = error.get("message", f"Request failed with status {status_code}")
        code = error.get("code")
    else:
        message = data.get("message", f"Request failed with status {status_code}")
        code = data.get("code")

    if code and code in _ERROR_CODE_MAP:
        raise _ERROR_CODE_MAP[code](message, code=code, status_code=status_code)

    exc_cls = _STATUS_CODE_MAP.get(status_code, QirabotError)
    raise exc_cls(message, code=code, status_code=status_code)
