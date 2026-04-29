"""Tests for client data classes, resource objects, and submit validation."""

from unittest.mock import MagicMock

import pytest

from qirabot.actions import Action, DEFAULT_AI_MAX_STEPS
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

SANDBOX_RUNNING = {
    "id": "sb1", "name": "s", "status": "running",
    "sandboxType": "chrome", "deviceId": "d1",
    "storageSize": "10Gi", "idleTimeout": 300,
}
SANDBOX_SLEEPING = {**SANDBOX_RUNNING, "status": "sleeping"}


class TestDeviceInfo:
    def test_from_dict(self):
        d = DeviceInfo.from_dict({"id": "d1", "name": "Pixel", "platform": "android", "online": True})
        assert d.id == "d1"
        assert d.name == "Pixel"
        assert d.platform == "android"
        assert d.online is True

    def test_from_dict_defaults(self):
        d = DeviceInfo.from_dict({})
        assert d.id == ""
        assert d.name == ""
        assert d.platform == ""
        assert d.online is False


class TestStepResult:
    def test_from_dict(self):
        s = StepResult.from_dict({
            "stepNumber": 3,
            "actionType": "click",
            "status": "succeeded",
            "output": "ok",
            "actionDurationTimeMs": 100,
            "stepDurationMs": 200,
        })
        assert s.number == 3
        assert s.action == "click"
        assert s.status == "succeeded"
        assert s.output == "ok"
        assert s.action_duration_ms == 100
        assert s.step_duration_ms == 200


class TestTaskResult:
    def test_succeeded(self):
        r = TaskResult(id="t1", status="succeeded")
        assert r.succeeded is True

    def test_failed(self):
        r = TaskResult(id="t1", status="failed", error="timeout")
        assert r.succeeded is False
        assert r.error == "timeout"

    def test_from_dict(self):
        r = TaskResult.from_dict({"id": "t1", "status": "succeeded", "currentStep": 5})
        assert r.id == "t1"
        assert r.current_step == 5


class TestSandboxInfo:
    def test_from_dict(self):
        s = SandboxInfo.from_dict({
            "id": "sb1",
            "name": "my-sandbox",
            "status": "running",
            "sandboxType": "chrome",
            "deviceId": "sandbox-sb1",
            "storageSize": "10Gi",
            "idleTimeout": 300,
            "resolution": "1280x720",
            "errorMessage": "something wrong",
        })
        assert s.id == "sb1"
        assert s.name == "my-sandbox"
        assert s.status == "running"
        assert s.sandbox_type == "chrome"
        assert s.device_id == "sandbox-sb1"
        assert s.storage_size == "10Gi"
        assert s.idle_timeout == 300
        assert s.resolution == "1280x720"
        assert s.error_message == "something wrong"

    def test_from_dict_defaults(self):
        s = SandboxInfo.from_dict({})
        assert s.id == ""
        assert s.name == ""
        assert s.status == ""
        assert s.sandbox_type == ""
        assert s.device_id == ""
        assert s.storage_size == ""
        assert s.idle_timeout == 0
        assert s.resolution == ""
        assert s.error_message == ""


class TestResourceObjects:
    def test_qirabot_has_resource_attributes(self):
        bot = Qirabot("key", base_url="http://localhost")
        assert isinstance(bot.devices, Devices)
        assert isinstance(bot.sandboxes, Sandboxes)
        assert isinstance(bot.tasks, Tasks)


class TestSubmitValidation:
    def test_both_actions_and_instruction_raises(self):
        bot = Qirabot("key", base_url="http://localhost")
        with pytest.raises(ValueError, match="Cannot specify both"):
            bot.tasks.submit(actions=[Action.click("btn")], instruction="do something")

    def test_neither_actions_nor_instruction_raises(self):
        bot = Qirabot("key", base_url="http://localhost")
        with pytest.raises(ValueError, match="Must specify either"):
            bot.tasks.submit()


class TestDevicesList:
    def test_list(self):
        transport = MagicMock()
        transport.request.return_value = [
            {"id": "d1", "name": "Pixel", "platform": "android", "online": True},
        ]
        devices = Devices(transport)
        result = devices.list()
        assert len(result) == 1
        assert result[0].id == "d1"
        transport.request.assert_called_once_with("GET", "/devices")

    def test_list_active(self):
        transport = MagicMock()
        transport.request.return_value = []
        devices = Devices(transport)
        result = devices.list_active()
        assert result == []
        transport.request.assert_called_once_with("GET", "/devices/active")


class TestSandboxesList:
    def test_list(self):
        transport = MagicMock()
        transport.request.return_value = [SANDBOX_RUNNING]
        sandboxes = Sandboxes(transport)
        result = sandboxes.list()
        assert len(result) == 1
        assert result[0].status == "running"

    def test_get(self):
        transport = MagicMock()
        transport.request.return_value = SANDBOX_SLEEPING
        sandboxes = Sandboxes(transport)
        result = sandboxes.get("sb1")
        assert result.status == "sleeping"
        transport.request.assert_called_once_with("GET", "/sandboxes/sb1")


class TestSandboxWakeIdempotent:
    def test_wake_already_running_skips_post(self):
        transport = MagicMock()
        transport.request.return_value = SANDBOX_RUNNING
        sandboxes = Sandboxes(transport)
        result = sandboxes.wake("sb1")
        assert result.status == "running"
        transport.post.assert_not_called()

    def test_wake_sleeping_calls_post(self):
        transport = MagicMock()
        transport.request.return_value = SANDBOX_SLEEPING
        transport.post.return_value = SANDBOX_RUNNING
        sandboxes = Sandboxes(transport)
        result = sandboxes.wake("sb1")
        assert result.status == "running"
        transport.post.assert_called_once_with("/sandboxes/sb1/wake")


class TestSandboxSleepIdempotent:
    def test_sleep_already_sleeping_skips_post(self):
        transport = MagicMock()
        transport.request.return_value = SANDBOX_SLEEPING
        sandboxes = Sandboxes(transport)
        result = sandboxes.sleep("sb1")
        assert result.status == "sleeping"
        transport.post.assert_not_called()

    def test_sleep_running_calls_post(self):
        transport = MagicMock()
        transport.request.return_value = SANDBOX_RUNNING
        transport.post.return_value = SANDBOX_SLEEPING
        sandboxes = Sandboxes(transport)
        result = sandboxes.sleep("sb1")
        assert result.status == "sleeping"
        transport.post.assert_called_once_with("/sandboxes/sb1/sleep")
