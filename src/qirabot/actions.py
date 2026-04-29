"""Action definitions for Qirabot SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ScreenshotMode = Literal["cloud", "inline", "none"]


DEFAULT_AI_MAX_STEPS = 20

@dataclass
class Action:
    """A device action to execute.

    Use the class methods to create actions instead of constructing directly.
    """

    type: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API request."""
        return {"type": self.type, "params": self.params}

    # ── Click ──

    @classmethod
    def click(cls, locate: str) -> Action:
        return cls(type="click", params={"locate": locate})

    @classmethod
    def double_click(cls, locate: str) -> Action:
        return cls(type="double_click", params={"locate": locate})

    @classmethod
    def right_click(cls, locate: str) -> Action:
        return cls(type="right_click", params={"locate": locate})

    @classmethod
    def hover(cls, locate: str) -> Action:
        return cls(type="hover", params={"locate": locate})

    # ── Text Input ──

    @classmethod
    def type_text(
        cls,
        locate: str,
        content: str,
        clear_before_typing: bool = False,
        press_enter: bool = False,
    ) -> Action:
        params: dict[str, Any] = {"locate": locate, "content": content}
        if clear_before_typing:
            params["clearBeforeTyping"] = True
        if press_enter:
            params["pressEnter"] = True
        return cls(type="type_text", params=params)

    @classmethod
    def type_direct(cls, content: str) -> Action:
        return cls(type="type_text_direct", params={"content": content})

    @classmethod
    def clear_text(cls, locate: str) -> Action:
        return cls(type="clear_text", params={"locate": locate})

    @classmethod
    def press_key(cls, key: str) -> Action:
        return cls(type="press_key", params={"key": key})

    # ── Navigation ──

    @classmethod
    def navigate(cls, url: str) -> Action:
        """Navigate to a URL. Chrome and Sandbox only."""
        return cls(type="navigate", params={"url": url})

    @classmethod
    def go_back(cls) -> Action:
        """Go back or close the current tab. Chrome only."""
        return cls(type="go_back")

    @classmethod
    def scroll(cls, direction: str = "down", distance: int | None = None) -> Action:
        params: dict[str, Any] = {"direction": direction}
        if distance is not None:
            params["distance"] = distance
        return cls(type="scroll", params=params)

    @classmethod
    def scroll_at(cls, locate: str, direction: str = "down", distance: int | None = None) -> Action:
        params: dict[str, Any] = {"locate": locate, "direction": direction}
        if distance is not None:
            params["distance"] = distance
        return cls(type="scroll_at", params=params)

    @classmethod
    def swipe(
        cls,
        direction: str,
        locate: str | None = None,
        distance: int | None = None,
        duration_ms: int = 500,
    ) -> Action:
        params: dict[str, Any] = {"direction": direction, "durationMs": duration_ms}
        if locate is not None:
            params["locate"] = locate
        if distance is not None:
            params["distance"] = distance
        return cls(type="swipe", params=params)

    # ── Wait ──

    @classmethod
    def wait(cls, duration_ms: int) -> Action:
        return cls(type="wait", params={"durationMs": duration_ms})

    @classmethod
    def wait_for(
        cls,
        assertion: str,
        timeout_ms: int,
        check_interval_ms: int = 1000,
        model_alias: str | None = None,
    ) -> Action:
        params: dict[str, Any] = {
            "assertion": assertion,
            "timeoutMs": timeout_ms,
            "checkInterval": check_interval_ms,
        }
        if model_alias is not None:
            params["model"] = model_alias
        return cls(type="wait_for", params=params)

    # ── Screenshot ──

    @classmethod
    def take_screenshot(cls) -> Action:
        return cls(type="take_screenshot")

    # ── AI ──

    @classmethod
    def extract(cls, instruction: str, variable: str = "result", model_alias: str | None = None) -> Action:
        params: dict[str, Any] = {"instruction": instruction, "variable": variable}
        if model_alias is not None:
            params["model"] = model_alias
        return cls(type="extract", params=params)

    @classmethod
    def verify(cls, assertion: str, model_alias: str | None = None) -> Action:
        params: dict[str, Any] = {"assertion": assertion}
        if model_alias is not None:
            params["model"] = model_alias
        return cls(type="assert", params=params)

    @classmethod
    def ai(cls, instruction: str, max_steps: int = DEFAULT_AI_MAX_STEPS, model_alias: str | None = None, language: str | None = None) -> Action:
        params: dict[str, Any] = {"instruction": instruction, "maxSteps": max_steps}
        if model_alias is not None:
            params["modelAlias"] = model_alias
        if language is not None:
            params["language"] = language
        return cls(type="ai_decision", params=params)

    # ── Drag ──

    @classmethod
    def drag(cls, from_locate: str, to_locate: str) -> Action:
        """Drag from one element to another."""
        return cls(type="drag", params={"from": from_locate, "to": to_locate})

    # ── App Control ──

    @classmethod
    def start_app(cls, package: str) -> Action:
        return cls(type="start_app", params={"package": package})

    @classmethod
    def stop_app(cls, package: str) -> Action:
        return cls(type="stop_app", params={"package": package})
