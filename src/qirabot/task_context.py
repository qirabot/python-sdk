"""Task context for Qirabot SDK."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

from qirabot.actions import Action, DEFAULT_AI_MAX_STEPS, ScreenshotMode
from qirabot.exceptions import ActionError

if TYPE_CHECKING:
    from qirabot._transport import Transport, WSConnection

logger = logging.getLogger("qirabot")

_HEARTBEAT_INTERVAL = 15.0  # seconds


@dataclass
class StepEvent:
    """Emitted after each step completes."""

    number: int
    action: str
    status: str
    output: str | None = None
    decision: str | None = None
    error: str | None = None
    action_duration_time_ms: int = 0
    step_duration_ms: int = 0


@dataclass
class ScreenshotEvent:
    """Emitted when a step has a screenshot available.

    For inline mode, ``data`` contains the raw PNG bytes directly.
    For cloud mode, use ``save()`` or ``to_bytes()`` to download from the server.
    """

    number: int
    task_id: str
    data: bytes | None = None
    _transport: Transport | None = field(default=None, repr=False)

    def save(self, local_path: str) -> None:
        """Save the screenshot to a local file."""
        img = self.to_bytes()
        with open(local_path, "wb") as f:
            f.write(img)

    def to_bytes(self) -> bytes:
        """Return raw screenshot bytes.

        For inline mode, returns the data directly.
        For cloud mode, downloads from the server.
        """
        if self.data is not None:
            return self.data
        if self._transport is None:
            raise RuntimeError("Transport not available")
        return self._transport.get_bytes(
            f"/screenshots?taskId={self.task_id}&step={self.number}"
        )


# Type alias for event handlers
EventHandler = Callable[..., Any]


class TaskContext:
    """Interactive task context for step-by-step device automation.

    Created by ``Qirabot.task()``. Use as a context manager::

        with bot.task("device-id") as t:
            t.click("Login button")
            t.type("username", "admin")
    """

    def __init__(
        self,
        transport: Transport,
        task_id: str,
        device_id: str,
        screenshot_mode: ScreenshotMode = "cloud",
    ):
        self._transport = transport
        self._task_id = task_id
        self._device_id = device_id
        self._screenshot_mode = screenshot_mode
        self._heartbeat_stop: threading.Event | None = None
        self._heartbeat_thread: threading.Thread | None = None
        self._listeners: dict[str, list[EventHandler]] = {}
        self._ws: WSConnection | None = None

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def device_id(self) -> str:
        return self._device_id

    # ── Event system ──

    def on(self, event: str, handler: EventHandler) -> TaskContext:
        """Register an event listener.

        Supported events:
            - ``"step"``: called with :class:`StepEvent` after each step completes.
            - ``"screenshot"``: called with :class:`ScreenshotEvent` when a screenshot is available.

        Returns self for chaining.
        """
        self._listeners.setdefault(event, []).append(handler)
        return self

    def off(self, event: str, handler: EventHandler | None = None) -> TaskContext:
        """Remove event listener(s).

        If handler is None, removes all listeners for the event.
        """
        if handler is None:
            self._listeners.pop(event, None)
        elif event in self._listeners:
            self._listeners[event] = [h for h in self._listeners[event] if h is not handler]
        return self

    def _emit(self, event: str, data: Any) -> None:
        for handler in self._listeners.get(event, []):
            try:
                handler(data)
            except Exception:
                logger.exception("Error in %s event handler", event)

    # ── Context manager ──

    def __enter__(self) -> TaskContext:
        self._start_heartbeat()
        self._ws = self._transport.ws_connect(
            f"/sdk/tasks/{self._task_id}/ws"
        )
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        self._stop_heartbeat()
        try:
            if exc_type is None:
                self.complete()
            elif issubclass(exc_type, KeyboardInterrupt):
                self.cancel()
            else:
                self.complete(status="failed", error_message=str(exc_val) if exc_val else "")
        except Exception:
            logger.exception("Failed to complete task during cleanup")
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    # ── Device actions ──

    def click(self, locate: str, **kw: Any) -> None:
        self._act(Action.click(locate), **kw)

    def double_click(self, locate: str, **kw: Any) -> None:
        self._act(Action.double_click(locate), **kw)

    def right_click(self, locate: str, **kw: Any) -> None:
        self._act(Action.right_click(locate), **kw)

    def hover(self, locate: str, **kw: Any) -> None:
        self._act(Action.hover(locate), **kw)

    def type_text(self, locate: str, content: str, clear_before_typing: bool = False, press_enter: bool = False, **kw: Any) -> None:
        self._act(Action.type_text(locate, content, clear_before_typing=clear_before_typing, press_enter=press_enter), **kw)

    def type_direct(self, content: str, **kw: Any) -> None:
        self._act(Action.type_direct(content), **kw)

    def clear_text(self, locate: str, **kw: Any) -> None:
        self._act(Action.clear_text(locate), **kw)

    def press_key(self, key: str, **kw: Any) -> None:
        self._act(Action.press_key(key), **kw)

    def navigate(self, url: str, **kw: Any) -> None:
        self._act(Action.navigate(url), **kw)

    def go_back(self, **kw: Any) -> None:
        self._act(Action.go_back(), **kw)

    def scroll(self, direction: str = "down", distance: int | None = None, **kw: Any) -> None:
        self._act(Action.scroll(direction, distance), **kw)

    def scroll_at(self, locate: str, direction: str = "down", distance: int | None = None, **kw: Any) -> None:
        self._act(Action.scroll_at(locate, direction, distance), **kw)

    def swipe(self, direction: str, locate: str | None = None, distance: int | None = None, duration_ms: int = 500, **kw: Any) -> None:
        self._act(Action.swipe(direction, locate, distance, duration_ms), **kw)

    def wait(self, duration_ms: int, **kw: Any) -> None:
        self._act(Action.wait(duration_ms), **kw)

    def wait_for(self, assertion: str, timeout_ms: int, check_interval_ms: int = 1000, model_alias: str | None = None, **kw: Any) -> None:
        self._act(Action.wait_for(assertion, timeout_ms, check_interval_ms, model_alias=model_alias), **kw)

    def take_screenshot(self, path: str | None = None, **kw: Any) -> bytes | None:
        """Take a screenshot.

        Args:
            path: If provided, save the screenshot to this local file path.

        Returns:
            Screenshot bytes if path is None, otherwise None.
        """
        captured: dict[str, Any] = {}

        def _capture_screenshot(event: ScreenshotEvent) -> None:
            captured["event"] = event

        self.on("screenshot", _capture_screenshot)
        try:
            self._act(Action.take_screenshot(), **kw)
        finally:
            self.off("screenshot", _capture_screenshot)

        event: ScreenshotEvent | None = captured.get("event")
        if event is not None:
            img = event.to_bytes()
            if path:
                with open(path, "wb") as f:
                    f.write(img)
                return None
            return img
        return None

    def extract(self, instruction: str, variable: str = "result", model_alias: str | None = None, **kw: Any) -> str:
        """Extract data from the screen using AI.

        Returns:
            The extracted value as a string.
        """
        result = self._act(Action.extract(instruction, variable, model_alias=model_alias), **kw)
        return result.get("output", "") if result else ""

    def verify(self, assertion: str, model_alias: str | None = None, **kw: Any) -> bool:
        """Verify a condition on the screen using AI.

        Returns:
            True if the assertion passes, False otherwise.
        """
        result = self._act(Action.verify(assertion, model_alias=model_alias), **kw)
        output = result.get("output", "") if result else ""
        return output.lower() in ("true", "pass", "yes", "1") if output else False

    def ai(self, instruction: str, max_steps: int = DEFAULT_AI_MAX_STEPS, model_alias: str | None = None, language: str | None = None, **kw: Any) -> str:
        """Let AI autonomously complete a task.

        Args:
            instruction: Natural language description of the goal.
            max_steps: Maximum number of steps AI can take.
            model_alias: Optional model alias to override the session default.
            language: Optional language to override the session default (e.g. "zh", "en").

        Returns:
            The output string from the AI task, or empty string if none.
        """
        result = self._act(Action.ai(instruction, max_steps, model_alias=model_alias, language=language), **kw)
        return result.get("output", "") if result else ""

    def drag(self, from_locate: str, to_locate: str, **kw: Any) -> None:
        self._act(Action.drag(from_locate, to_locate), **kw)

    def start_app(self, package: str, **kw: Any) -> None:
        self._act(Action.start_app(package), **kw)

    def stop_app(self, package: str, **kw: Any) -> None:
        self._act(Action.stop_app(package), **kw)

    # ── Execution lifecycle ──

    def complete(self, status: str = "succeeded", error_message: str = "") -> None:
        """Complete the task and release the device."""
        body: dict[str, Any] = {"status": status}
        if error_message:
            body["errorMessage"] = error_message
        try:
            self._transport.post(f"/sdk/tasks/{self._task_id}/complete", body)
        except Exception:
            logger.exception("Failed to complete task %s", self._task_id)

    def cancel(self) -> None:
        """Cancel the task and release the device."""
        try:
            self._transport.delete(f"/sdk/tasks/{self._task_id}")
        except Exception:
            logger.exception("Failed to cancel task %s", self._task_id)

    # ── Internal ──

    def _act(self, action: Action, timeout: float = 300.0, on_step: EventHandler | None = None) -> dict[str, Any] | None:
        """Execute a single action via WebSocket and return the final result data."""
        if self._ws is None:
            raise RuntimeError("Task not started. Use as a context manager.")

        self._ws.send_action(action.to_dict())

        last_result: dict[str, Any] = {}

        while True:
            msg = self._ws.receive(timeout=timeout)
            msg_type = msg.data.get("type", "")

            if msg_type == "step":
                step_event = StepEvent(
                    number=msg.data.get("stepNumber", 0),
                    action=msg.data.get("actionType", ""),
                    status=msg.data.get("status", ""),
                    output=msg.data.get("output"),
                    decision=msg.data.get("decision"),
                    error=msg.data.get("error"),
                    action_duration_time_ms=msg.data.get("actionDurationTimeMs", 0),
                    step_duration_ms=msg.data.get("stepDurationMs", 0),
                )
                self._emit("step", step_event)
                if on_step:
                    on_step(step_event)

                # Emit screenshot event if available (inline binary or cloud path)
                has_screenshot = msg.screenshot is not None
                screenshot_path = msg.data.get("screenshotPath")
                if has_screenshot or screenshot_path:
                    screenshot_event = ScreenshotEvent(
                        number=step_event.number,
                        task_id=self._task_id,
                        data=msg.screenshot,
                        _transport=self._transport if screenshot_path else None,
                    )
                    self._emit("screenshot", screenshot_event)

            elif msg_type == "result":
                last_result = msg.data
                if not msg.data.get("success", False) and not msg.data.get("finished", False):
                    error_msg = msg.data.get("error", "Action failed")
                    if "max steps" in error_msg.lower():
                        logger.warning("AI action reached max steps: %s", error_msg)
                    else:
                        raise ActionError(error_msg, code="action.failed")
                break

            elif msg_type == "error":
                error_msg = msg.data.get("error", "Unknown error")
                raise ActionError(error_msg, code="ws.error")

        return last_result

    def _start_heartbeat(self) -> None:
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        if self._heartbeat_stop:
            self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5.0)

    def _heartbeat_loop(self) -> None:
        assert self._heartbeat_stop is not None
        while not self._heartbeat_stop.wait(_HEARTBEAT_INTERVAL):
            try:
                self._transport.post(f"/sdk/tasks/{self._task_id}/heartbeat")
            except Exception:
                logger.warning("Heartbeat failed for task %s", self._task_id)
