"""Tests for Action class."""

from qirabot.actions import Action, DEFAULT_AI_MAX_STEPS


class TestActionFactories:
    def test_click(self):
        a = Action.click("Login button")
        assert a.type == "click"
        assert a.params == {"locate": "Login button"}

    def test_double_click(self):
        a = Action.double_click("icon")
        assert a.type == "double_click"
        assert a.params == {"locate": "icon"}

    def test_right_click(self):
        a = Action.right_click("menu")
        assert a.type == "right_click"
        assert a.params == {"locate": "menu"}

    def test_hover(self):
        a = Action.hover("tooltip trigger")
        assert a.type == "hover"
        assert a.params == {"locate": "tooltip trigger"}

    def test_type_text(self):
        a = Action.type_text("username field", "admin")
        assert a.type == "type_text"
        assert a.params == {"locate": "username field", "content": "admin"}

    def test_type_direct(self):
        a = Action.type_direct("hello")
        assert a.type == "type_text_direct"
        assert a.params == {"content": "hello"}

    def test_clear_text(self):
        a = Action.clear_text("input")
        assert a.type == "clear_text"
        assert a.params == {"locate": "input"}

    def test_press_key(self):
        a = Action.press_key("Enter")
        assert a.type == "press_key"
        assert a.params == {"key": "Enter"}

    def test_navigate(self):
        a = Action.navigate("https://example.com")
        assert a.type == "navigate"
        assert a.params == {"url": "https://example.com"}

    def test_go_back(self):
        a = Action.go_back()
        assert a.type == "go_back"
        assert a.params == {}

    def test_scroll_default(self):
        a = Action.scroll()
        assert a.type == "scroll"
        assert a.params == {"direction": "down"}

    def test_scroll_with_distance(self):
        a = Action.scroll("up", distance=500)
        assert a.params == {"direction": "up", "distance": 500}

    def test_scroll_at(self):
        a = Action.scroll_at("list area", "down", distance=300)
        assert a.type == "scroll_at"
        assert a.params == {"locate": "list area", "direction": "down", "distance": 300}

    def test_swipe(self):
        a = Action.swipe("left", locate="card", distance=200, duration_ms=300)
        assert a.type == "swipe"
        assert a.params == {"direction": "left", "locate": "card", "distance": 200, "durationMs": 300}

    def test_swipe_minimal(self):
        a = Action.swipe("right")
        assert a.params == {"direction": "right", "durationMs": 500}

    def test_wait(self):
        a = Action.wait(2000)
        assert a.type == "wait"
        assert a.params == {"durationMs": 2000}

    def test_wait_for(self):
        a = Action.wait_for("page loaded", 5000, check_interval_ms=500)
        assert a.type == "wait_for"
        assert a.params == {"assertion": "page loaded", "timeoutMs": 5000, "checkInterval": 500}

    def test_take_screenshot(self):
        a = Action.take_screenshot()
        assert a.type == "take_screenshot"

    def test_extract(self):
        a = Action.extract("get the price", variable="price")
        assert a.type == "extract"
        assert a.params == {"instruction": "get the price", "variable": "price"}

    def test_verify(self):
        a = Action.verify("page shows success")
        assert a.type == "assert"
        assert a.params == {"assertion": "page shows success"}

    def test_type_text_with_clear_and_enter(self):
        a = Action.type_text("search box", "query", clear_before_typing=True, press_enter=True)
        assert a.type == "type_text"
        assert a.params == {"locate": "search box", "content": "query", "clearBeforeTyping": True, "pressEnter": True}

    def test_drag(self):
        a = Action.drag("item A", "drop zone")
        assert a.type == "drag"
        assert a.params == {"from": "item A", "to": "drop zone"}

    def test_start_app(self):
        a = Action.start_app("com.example.app")
        assert a.type == "start_app"
        assert a.params == {"package": "com.example.app"}

    def test_stop_app(self):
        a = Action.stop_app("com.example.app")
        assert a.type == "stop_app"
        assert a.params == {"package": "com.example.app"}


class TestActionAI:
    def test_default_max_steps(self):
        a = Action.ai("do something")
        assert a.type == "ai_decision"
        assert a.params["maxSteps"] == DEFAULT_AI_MAX_STEPS
        assert a.params["instruction"] == "do something"

    def test_custom_max_steps(self):
        a = Action.ai("do something", max_steps=5)
        assert a.params["maxSteps"] == 5

    def test_with_model_alias(self):
        a = Action.ai("do something", model_alias="fast")
        assert a.params["modelAlias"] == "fast"

    def test_with_language(self):
        a = Action.ai("do something", language="zh")
        assert a.params["language"] == "zh"

    def test_none_optionals_omitted(self):
        a = Action.ai("do something")
        assert "modelAlias" not in a.params
        assert "language" not in a.params


class TestActionToDict:
    def test_serialization(self):
        a = Action.click("button")
        d = a.to_dict()
        assert d == {"type": "click", "params": {"locate": "button"}}

    def test_empty_params(self):
        a = Action.go_back()
        d = a.to_dict()
        assert d == {"type": "go_back", "params": {}}
