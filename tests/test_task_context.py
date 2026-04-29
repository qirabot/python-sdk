"""Tests for TaskContext._act result handling logic."""

import pytest
from unittest.mock import MagicMock

from qirabot._transport import StepMessage
from qirabot.exceptions import ActionError
from qirabot.task_context import TaskContext, StepEvent, ScreenshotEvent


def _make_context_with_ws(messages: list[StepMessage]) -> TaskContext:
    """Create a TaskContext with a mocked WebSocket that returns pre-defined messages."""
    transport = MagicMock()
    ctx = TaskContext(transport=transport, task_id="t1", device_id="d1")
    ws = MagicMock()
    ws.receive = MagicMock(side_effect=messages)
    ctx._ws = ws
    return ctx


class TestActResultHandling:
    def test_success_result(self):
        msgs = [
            StepMessage(data={"type": "result", "success": True, "finished": True, "output": "done"}),
        ]
        ctx = _make_context_with_ws(msgs)
        from qirabot.actions import Action
        result = ctx._act(Action.click("btn"))
        assert result["success"] is True
        assert result["output"] == "done"

    def test_action_error_raised(self):
        msgs = [
            StepMessage(data={"type": "result", "success": False, "error": "element not found"}),
        ]
        ctx = _make_context_with_ws(msgs)
        from qirabot.actions import Action
        with pytest.raises(ActionError, match="element not found"):
            ctx._act(Action.click("btn"))

    def test_max_steps_no_exception(self):
        msgs = [
            StepMessage(data={
                "type": "result",
                "success": False,
                "error": "AI decision reached max steps (20)",
                "output": "partial output",
            }),
        ]
        ctx = _make_context_with_ws(msgs)
        from qirabot.actions import Action
        result = ctx._act(Action.ai("do something"))
        assert result["output"] == "partial output"

    def test_max_steps_case_insensitive(self):
        msgs = [
            StepMessage(data={
                "type": "result",
                "success": False,
                "error": "AI decision reached Max Steps (10)",
                "output": "",
            }),
        ]
        ctx = _make_context_with_ws(msgs)
        from qirabot.actions import Action
        result = ctx._act(Action.ai("do something"))
        assert result is not None

    def test_ws_error_raised(self):
        msgs = [
            StepMessage(data={"type": "error", "error": "connection lost"}),
        ]
        ctx = _make_context_with_ws(msgs)
        from qirabot.actions import Action
        with pytest.raises(ActionError, match="connection lost"):
            ctx._act(Action.click("btn"))

    def test_step_events_emitted(self):
        events = []
        msgs = [
            StepMessage(data={
                "type": "step",
                "stepNumber": 1,
                "actionType": "click",
                "status": "succeeded",
            }),
            StepMessage(data={"type": "result", "success": True, "finished": True}),
        ]
        ctx = _make_context_with_ws(msgs)
        ctx.on("step", lambda e: events.append(e))
        from qirabot.actions import Action
        ctx._act(Action.click("btn"))
        assert len(events) == 1
        assert isinstance(events[0], StepEvent)
        assert events[0].number == 1

    def test_screenshot_event_emitted_inline(self):
        events = []
        msgs = [
            StepMessage(
                data={"type": "step", "stepNumber": 1, "actionType": "click", "status": "succeeded"},
                screenshot=b"\x89PNG",
            ),
            StepMessage(data={"type": "result", "success": True, "finished": True}),
        ]
        ctx = _make_context_with_ws(msgs)
        ctx.on("screenshot", lambda e: events.append(e))
        from qirabot.actions import Action
        ctx._act(Action.click("btn"))
        assert len(events) == 1
        assert isinstance(events[0], ScreenshotEvent)
        assert events[0].data == b"\x89PNG"

    def test_screenshot_event_emitted_cloud(self):
        events = []
        msgs = [
            StepMessage(data={
                "type": "step",
                "stepNumber": 2,
                "actionType": "click",
                "status": "succeeded",
                "screenshotPath": "tasks/t1/steps/2.png",
            }),
            StepMessage(data={"type": "result", "success": True, "finished": True}),
        ]
        ctx = _make_context_with_ws(msgs)
        ctx.on("screenshot", lambda e: events.append(e))
        from qirabot.actions import Action
        ctx._act(Action.click("btn"))
        assert len(events) == 1
        assert events[0]._transport is not None

    def test_no_ws_raises_runtime_error(self):
        transport = MagicMock()
        ctx = TaskContext(transport=transport, task_id="t1", device_id="d1")
        from qirabot.actions import Action
        with pytest.raises(RuntimeError, match="Task not started"):
            ctx._act(Action.click("btn"))

    def test_on_step_callback(self):
        step_events = []
        msgs = [
            StepMessage(data={
                "type": "step",
                "stepNumber": 1,
                "actionType": "ai_decision",
                "status": "succeeded",
                "output": "clicked login",
            }),
            StepMessage(data={"type": "result", "success": True, "finished": True}),
        ]
        ctx = _make_context_with_ws(msgs)
        from qirabot.actions import Action
        ctx._act(Action.ai("login"), on_step=lambda e: step_events.append(e))
        assert len(step_events) == 1
        assert step_events[0].output == "clicked login"


class TestEventSystem:
    def test_on_off(self):
        transport = MagicMock()
        ctx = TaskContext(transport=transport, task_id="t1", device_id="d1")
        handler = MagicMock()
        ctx.on("step", handler)
        ctx._emit("step", "data")
        handler.assert_called_once_with("data")

        ctx.off("step", handler)
        ctx._emit("step", "data2")
        handler.assert_called_once()

    def test_off_all(self):
        transport = MagicMock()
        ctx = TaskContext(transport=transport, task_id="t1", device_id="d1")
        h1 = MagicMock()
        h2 = MagicMock()
        ctx.on("step", h1)
        ctx.on("step", h2)
        ctx.off("step")
        ctx._emit("step", "data")
        h1.assert_not_called()
        h2.assert_not_called()

    def test_chaining(self):
        transport = MagicMock()
        ctx = TaskContext(transport=transport, task_id="t1", device_id="d1")
        result = ctx.on("step", lambda e: None).on("screenshot", lambda e: None)
        assert result is ctx
