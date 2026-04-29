"""Qirabot - AI-powered device automation SDK."""

from qirabot.actions import Action, DEFAULT_AI_MAX_STEPS, ScreenshotMode
from qirabot.client import (
    DeviceInfo,
    Devices,
    Qirabot,
    SandboxInfo,
    Sandboxes,
    StepResult,
    TaskResult,
    Tasks,
)
from qirabot.exceptions import (
    ActionError,
    AuthenticationError,
    DeviceBusyError,
    DeviceOfflineError,
    LeaseExpiredError,
    QirabotError,
    QirabotTimeoutError,
)
from qirabot.task_context import ScreenshotEvent, StepEvent, TaskContext

__all__ = [
    "Action",
    "ActionError",
    "DEFAULT_AI_MAX_STEPS",
    "AuthenticationError",
    "DeviceBusyError",
    "DeviceInfo",
    "DeviceOfflineError",
    "Devices",
    "LeaseExpiredError",
    "Qirabot",
    "QirabotError",
    "SandboxInfo",
    "Sandboxes",
    "QirabotTimeoutError",
    "ScreenshotEvent",
    "ScreenshotMode",
    "StepEvent",
    "StepResult",
    "TaskContext",
    "TaskResult",
    "Tasks",
]
