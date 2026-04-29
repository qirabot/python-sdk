"""HTTP + WebSocket transport layer for Qirabot SDK."""

from __future__ import annotations

import json
import logging
import struct
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
import websockets.sync.client as ws_sync

from qirabot.exceptions import raise_for_error, QirabotTimeoutError

logger = logging.getLogger("qirabot")


@dataclass
class StepMessage:
    """A step event received from WebSocket."""

    data: dict[str, Any]
    screenshot: bytes | None = None


class Transport:
    """HTTP client with WebSocket support."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_url = f"{self._base_url}/api/v1"
        self._api_key = api_key
        self._headers = {"X-API-Key": api_key}
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._client = httpx.Client(
            base_url=self._api_url,
            headers=self._headers,
            timeout=timeout,
            verify=verify_ssl,
        )

    def request(self, method: str, path: str, json_data: dict[str, Any] | None = None) -> Any:
        """Send an HTTP request and return parsed JSON response."""
        response = self._client.request(method, path, json=json_data)
        if response.status_code >= 400:
            try:
                data = response.json()
            except Exception:
                data = {"error": {"message": response.text or "Unknown error"}}
            raise_for_error(response.status_code, data)
        if response.status_code == 204:
            return {}
        try:
            return response.json()
        except Exception:
            return {}

    def post(self, path: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a POST request."""
        result: dict[str, Any] = self.request("POST", path, json_data)
        return result

    def delete(self, path: str) -> dict[str, Any]:
        """Send a DELETE request."""
        result: dict[str, Any] = self.request("DELETE", path)
        return result

    def ws_connect(self, path: str, timeout: float | None = None) -> WSConnection:
        """Open a WebSocket connection.

        Args:
            path: API path (e.g. "/sdk/tasks/{id}/ws").
            timeout: Optional timeout override.

        Returns:
            A WSConnection wrapper.
        """
        connect_timeout = timeout or self._timeout
        ws_url = self._build_ws_url(path)
        additional_headers = {"X-API-Key": self._api_key}
        conn = ws_sync.connect(
            ws_url,
            additional_headers=additional_headers,
            open_timeout=connect_timeout,
            close_timeout=10,
            ping_interval=None,
        )
        return WSConnection(conn)

    def get_bytes(self, path: str) -> bytes:
        """Send a GET request and return raw bytes (for screenshot/image download)."""
        response = self._client.get(path)
        if response.status_code >= 400:
            try:
                data = response.json()
            except Exception:
                data = {"error": {"message": response.text or "Unknown error"}}
            raise_for_error(response.status_code, data)
        return response.content

    def stream_to_file(self, path: str, local_path: str) -> None:
        """Send a GET request and stream the response to a local file."""
        with self._client.stream("GET", path) as response:
            if response.status_code >= 400:
                response.read()
                try:
                    data = response.json()
                except Exception:
                    data = {"error": {"message": response.text or "Unknown error"}}
                raise_for_error(response.status_code, data)
            with open(local_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def _build_ws_url(self, path: str) -> str:
        """Convert HTTP base URL to WebSocket URL."""
        parsed = urlparse(self._api_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        return f"{scheme}://{parsed.netloc}{parsed.path}{path}"


class WSConnection:
    """Wrapper around a WebSocket connection for SDK task action.

    Server protocol:
        - Text frame: JSON message (step event, result event, or error)
        - Binary frame: composite [2-byte JSON length (big-endian)] [JSON] [PNG]
          Used for step events with inline screenshots.
    """

    def __init__(self, conn: ws_sync.ClientConnection):
        self._conn = conn

    def send_action(self, action: dict[str, Any]) -> None:
        """Send an execute_action request."""
        msg = json.dumps({"type": "execute_action", "action": action})
        self._conn.send(msg)

    def receive(self, timeout: float | None = None) -> StepMessage:
        """Receive the next message from the server.

        Returns a StepMessage. For binary frames, the screenshot field is populated.
        """
        self._conn.socket.settimeout(timeout)
        try:
            frame = self._conn.recv()
        except TimeoutError:
            raise QirabotTimeoutError("WebSocket receive timed out")

        if isinstance(frame, str):
            # Text frame: pure JSON
            data = json.loads(frame)
            return StepMessage(data=data)

        # Binary frame: [2-byte JSON length] [JSON] [PNG]
        if len(frame) < 2:
            return StepMessage(data={})
        json_len = struct.unpack("!H", frame[:2])[0]
        json_bytes = frame[2 : 2 + json_len]
        screenshot = frame[2 + json_len :]
        data = json.loads(json_bytes)
        return StepMessage(data=data, screenshot=screenshot if screenshot else None)

    def close(self) -> None:
        """Close the WebSocket connection."""
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self) -> WSConnection:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
