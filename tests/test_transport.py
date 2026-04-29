"""Tests for transport layer (URL building, message parsing)."""

import json
import struct

from qirabot._transport import StepMessage, Transport, WSConnection


class TestTransportURLBuilding:
    def test_ws_url_from_https(self):
        t = Transport("https://app.qirabot.com", "key")
        url = t._build_ws_url("/sdk/tasks/123/ws")
        assert url == "wss://app.qirabot.com/api/v1/sdk/tasks/123/ws"

    def test_ws_url_from_http(self):
        t = Transport("http://localhost:8080", "key")
        url = t._build_ws_url("/sdk/tasks/abc/ws")
        assert url == "ws://localhost:8080/api/v1/sdk/tasks/abc/ws"

    def test_trailing_slash_stripped(self):
        t = Transport("https://app.qirabot.com/", "key")
        assert t._base_url == "https://app.qirabot.com"
        assert t._api_url == "https://app.qirabot.com/api/v1"


class TestStepMessage:
    def test_text_message(self):
        msg = StepMessage(data={"type": "step", "stepNumber": 1})
        assert msg.data["type"] == "step"
        assert msg.screenshot is None

    def test_binary_message_with_screenshot(self):
        msg = StepMessage(data={"type": "step"}, screenshot=b"\x89PNG")
        assert msg.screenshot == b"\x89PNG"


class TestWSConnectionBinaryParsing:
    def _make_binary_frame(self, json_data: dict, png_data: bytes) -> bytes:
        json_bytes = json.dumps(json_data).encode()
        buf = struct.pack("!H", len(json_bytes)) + json_bytes + png_data
        return buf

    def test_parse_binary_frame_structure(self):
        json_data = {"type": "step", "stepNumber": 3}
        png_data = b"\x89PNG\r\n\x1a\nfakeimage"
        frame = self._make_binary_frame(json_data, png_data)

        json_len = struct.unpack("!H", frame[:2])[0]
        json_bytes = frame[2:2 + json_len]
        screenshot = frame[2 + json_len:]

        parsed = json.loads(json_bytes)
        assert parsed == json_data
        assert screenshot == png_data
