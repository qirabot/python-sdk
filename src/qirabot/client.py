"""Main client for Qirabot SDK."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, overload

from qirabot._transport import Transport
from qirabot.actions import Action, DEFAULT_AI_MAX_STEPS, ScreenshotMode
from qirabot.exceptions import QirabotTimeoutError
from qirabot.task_context import TaskContext


@dataclass
class DeviceInfo:
    """Device information."""

    id: str
    name: str
    platform: str
    online: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceInfo:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            platform=data.get("platform", ""),
            online=data.get("online", False),
        )


@dataclass
class StepResult:
    """Result of a single step in a task."""

    number: int
    action: str
    status: str
    output: str = ""
    error: str = ""
    action_duration_ms: int = 0
    step_duration_ms: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepResult:
        return cls(
            number=data.get("stepNumber", 0),
            action=data.get("actionType", ""),
            status=data.get("status", ""),
            output=data.get("output", ""),
            error=data.get("error", ""),
            action_duration_ms=data.get("actionDurationTimeMs", 0),
            step_duration_ms=data.get("stepDurationMs", 0),
        )


@dataclass
class TaskResult:
    """Result of a completed task."""

    id: str
    status: str
    current_step: int = 0
    source: str = ""
    error: str = ""
    steps: list[StepResult] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskResult:
        return cls(
            id=data.get("id", ""),
            status=data.get("status", ""),
            current_step=data.get("currentStep", 0),
            source=data.get("source", ""),
            error=data.get("error", ""),
        )


@dataclass
class SandboxInfo:
    """Sandbox information."""

    id: str
    name: str
    status: str
    sandbox_type: str
    device_id: str
    storage_size: str
    idle_timeout: int
    resolution: str = ""
    error_message: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SandboxInfo:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            status=data.get("status", ""),
            sandbox_type=data.get("sandboxType", ""),
            device_id=data.get("deviceId", ""),
            storage_size=data.get("storageSize", ""),
            idle_timeout=data.get("idleTimeout", 0),
            resolution=data.get("resolution", ""),
            error_message=data.get("errorMessage", ""),
        )


class Devices:
    """Device resource."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list(self) -> list[DeviceInfo]:
        """List all devices for the current user."""
        resp = self._transport.request("GET", "/devices")
        return [DeviceInfo.from_dict(d) for d in resp] if isinstance(resp, list) else []

    def list_active(self) -> list[DeviceInfo]:
        """List online devices for the current user."""
        resp = self._transport.request("GET", "/devices/active")
        return [DeviceInfo.from_dict(d) for d in resp] if isinstance(resp, list) else []


class Sandboxes:
    """Sandbox resource."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list(self) -> list[SandboxInfo]:
        """List all sandboxes for the current user."""
        resp = self._transport.request("GET", "/sandboxes")
        return [SandboxInfo.from_dict(s) for s in resp] if isinstance(resp, list) else []

    def get(self, sandbox_id: str) -> SandboxInfo:
        """Get sandbox information by ID."""
        resp = self._transport.request("GET", f"/sandboxes/{sandbox_id}")
        return SandboxInfo.from_dict(resp)

    def wake(
        self,
        sandbox_id: str,
        timeout: float = 120.0,
        poll_interval: float = 3.0,
    ) -> SandboxInfo:
        """Wake a sandbox and wait until it is running.

        No-op if the sandbox is already running.

        Raises:
            QirabotTimeoutError: If the sandbox does not reach 'running' within the timeout.
        """
        info = self.get(sandbox_id)
        if info.status == "running":
            return info
        if info.status != "pending":
            self._transport.post(f"/sandboxes/{sandbox_id}/wake")
        return self._wait_status(sandbox_id, "running", timeout, poll_interval)

    def sleep(
        self,
        sandbox_id: str,
        timeout: float = 120.0,
        poll_interval: float = 3.0,
    ) -> SandboxInfo:
        """Put a sandbox to sleep and wait until it is sleeping.

        No-op if the sandbox is already sleeping.

        Raises:
            QirabotTimeoutError: If the sandbox does not reach 'sleeping' within the timeout.
        """
        info = self.get(sandbox_id)
        if info.status == "sleeping":
            return info
        self._transport.post(f"/sandboxes/{sandbox_id}/sleep")
        return self._wait_status(sandbox_id, "sleeping", timeout, poll_interval)

    def _wait_status(
        self,
        sandbox_id: str,
        target: str,
        timeout: float,
        poll_interval: float,
    ) -> SandboxInfo:
        deadline = time.monotonic() + timeout
        while True:
            info = self.get(sandbox_id)
            if info.status == target:
                return info
            if info.error_message:
                raise QirabotTimeoutError(f"Sandbox {sandbox_id} entered error state: {info.error_message}")
            if time.monotonic() >= deadline:
                raise QirabotTimeoutError(
                    f"Sandbox {sandbox_id} did not reach '{target}' within {timeout}s (current: {info.status})"
                )
            time.sleep(poll_interval)


class Tasks:
    """Task resource."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    @overload
    def submit(
        self,
        device_id: str = "",
        *,
        actions: list[Action],
        name: str = "",
        model_alias: str = "",
        language: str = "",
        screenshot_mode: ScreenshotMode = "cloud",
    ) -> str: ...

    @overload
    def submit(
        self,
        device_id: str = "",
        *,
        instruction: str,
        name: str = "",
        model_alias: str = "",
        language: str = "",
        max_steps: int = DEFAULT_AI_MAX_STEPS,
        screenshot_mode: ScreenshotMode = "cloud",
    ) -> str: ...

    def submit(
        self,
        device_id: str = "",
        *,
        actions: list[Action] | None = None,
        instruction: str = "",
        name: str = "",
        model_alias: str = "",
        language: str = "",
        max_steps: int = DEFAULT_AI_MAX_STEPS,
        screenshot_mode: ScreenshotMode = "cloud",
    ) -> str:
        """Submit actions for autonomous execution and return the task ID immediately.

        Use ``wait()`` to poll for completion.

        Args:
            device_id: The device to run on (optional if sandbox is configured).
            actions: List of actions to execute sequentially.
            instruction: Shorthand for a single AI action. Mutually exclusive with ``actions``.
            name: Optional task name for grouping and filtering in execution history.
            model_alias: Optional AI model alias.
            language: Optional language (e.g. "zh", "en").
            max_steps: Max steps for AI instruction (default 10).
            screenshot_mode: "cloud", "inline", or "none".

        Returns:
            The task ID string.
        """
        if instruction and actions:
            raise ValueError("Cannot specify both 'actions' and 'instruction'")
        if not instruction and not actions:
            raise ValueError("Must specify either 'actions' or 'instruction'")

        if instruction:
            steps = [Action.ai(instruction, max_steps=max_steps, model_alias=model_alias or None, language=language or None)]
        else:
            steps = actions  # type: ignore[assignment]

        body: dict[str, Any] = {
            "actions": [a.to_dict() for a in steps],
        }
        if device_id:
            body["deviceId"] = device_id
        if name:
            body["name"] = name
        if model_alias:
            body["modelAlias"] = model_alias
        if language:
            body["language"] = language
        if screenshot_mode != "cloud":
            body["screenshotMode"] = screenshot_mode

        resp = self._transport.post("/sdk/tasks/submit", body)
        task_id: str = resp["taskId"]
        return task_id

    def wait(
        self,
        task_id: str,
        timeout: float = 120.0,
        poll_interval: float = 3.0,
    ) -> TaskResult:
        """Poll until a submitted task reaches a terminal state.

        Args:
            task_id: The task ID returned by ``submit()``.
            timeout: Maximum seconds to wait (default 120).
            poll_interval: Seconds between polls (default 3).

        Returns:
            A :class:`TaskResult` with the final status and steps.

        Raises:
            QirabotTimeoutError: If the task does not complete within the timeout.
        """
        deadline = time.monotonic() + timeout
        while True:
            resp = self._transport.request("GET", f"/tasks/{task_id}")
            status = resp.get("status", "")
            if status not in ("pending", "running"):
                result = TaskResult.from_dict(resp)
                steps_resp = self._transport.request("GET", f"/tasks/{task_id}/steps")
                if isinstance(steps_resp, list):
                    result.steps = [StepResult.from_dict(s) for s in steps_resp]
                return result
            if time.monotonic() >= deadline:
                raise QirabotTimeoutError(f"Task {task_id} did not complete within {timeout}s")
            time.sleep(poll_interval)

    @contextmanager
    def session(
        self,
        device_id: str,
        name: str = "",
        model_alias: str = "",
        language: str = "",
        screenshot_mode: ScreenshotMode = "cloud",
    ) -> Iterator[TaskContext]:
        """Create a task on a device and return an interactive context.

        Args:
            device_id: The device to connect to.
            name: Optional task name for grouping and filtering in execution history.
            model_alias: Optional AI model alias to use (default: server default).
            language: Optional language for AI responses (e.g. "zh", "en", "ja").
            screenshot_mode: Screenshot storage mode:
                - "cloud": store to cloud, return path (default)
                - "inline": no cloud storage, send binary via WebSocket
                - "none": no screenshots stored or returned

        Yields:
            A TaskContext that auto-completes on exit.
        """
        body: dict[str, Any] = {"deviceId": device_id}
        if name:
            body["name"] = name
        if model_alias:
            body["modelAlias"] = model_alias
        if language:
            body["language"] = language
        if screenshot_mode != "cloud":
            body["screenshotMode"] = screenshot_mode

        resp = self._transport.post("/sdk/tasks", body)
        task_id = resp["taskId"]

        ctx = TaskContext(
            transport=self._transport,
            task_id=task_id,
            device_id=device_id,
            screenshot_mode=screenshot_mode,
        )
        with ctx:
            yield ctx

    def screenshot(
        self,
        task_id: str,
        step: int,
        path: str | None = None,
    ) -> bytes | None:
        """Download a screenshot for a specific step of a completed task.

        Args:
            task_id: The task ID.
            step: The step number.
            path: If provided, save the screenshot to this local file path.

        Returns:
            Screenshot bytes if path is None, otherwise None.
        """
        data = self._transport.get_bytes(f"/screenshots?taskId={task_id}&step={step}")
        if path:
            with open(path, "wb") as f:
                f.write(data)
            return None
        return data

    def screenshots(self, task_id: str, path: str) -> None:
        """Download all screenshots for a task as a ZIP file.

        Args:
            task_id: The task ID.
            path: Local file path to save the ZIP archive.
        """
        self._transport.stream_to_file(f"/tasks/{task_id}/images/download", path)


class Qirabot:
    """Qirabot SDK client.

    Usage::

        bot = Qirabot("qk_xxx")
        with bot.tasks.session("device-id") as s:
            s.click("Login button")
            s.type_text("username", "admin")
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://app.qirabot.com",
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ):
        self._transport = Transport(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
        self.devices = Devices(self._transport)
        self.sandboxes = Sandboxes(self._transport)
        self.tasks = Tasks(self._transport)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._transport.close()

    def __enter__(self) -> Qirabot:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
