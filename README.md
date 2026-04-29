# Qirabot Python SDK

Official Python SDK for [Qirabot](https://qirabot.com) - AI-powered device automation platform.

Automate mobile and web devices with natural language or structured actions. Let AI see the screen, click, type, extract data, and verify results.

## Installation

```bash
pip install qirabot
```

Requires Python 3.10+.

## Configuration

1. Sign up at [qirabot.com](https://qirabot.com) and get your API key from the dashboard.
2. Set it as an environment variable:

```bash
export QIRA_API_KEY="qk_your_api_key"
```

```python
import os
from qirabot import Qirabot

bot = Qirabot(os.environ["QIRA_API_KEY"])
```

## Two Modes

The SDK offers two execution modes:

| | Interactive Mode | Submit Mode |
|---|---|---|
| **How** | `bot.tasks.session()` | `bot.tasks.submit()` |
| **Connection** | WebSocket — real-time step events | REST — fire and poll |
| **Control** | Run Python logic between steps | Define all actions upfront |
| **Best for** | Conditional workflows, debugging, data pipelines | Background jobs, CI/CD, simple automations |

## Quick Start

### Interactive Mode

Step-by-step control with real-time feedback via WebSocket:

```python
import os
from qirabot import Qirabot

bot = Qirabot(os.environ["QIRA_API_KEY"])

with bot.tasks.session("device-id", name="wiki-extract") as s:
    s.navigate("https://en.wikipedia.org")
    s.type_text("Search Wikipedia input", "Artificial intelligence")
    s.click("Search button")
    s.wait_for("Wikipedia article page is visible", timeout_ms=10000)

    summary = s.extract("Get the first paragraph of the article")
    print(f"Summary: {summary}")

    s.verify("The article title contains 'Artificial intelligence'")
```

### Submit Mode

Fire-and-forget execution with polling:

```python
import os
from qirabot import Qirabot, Action

bot = Qirabot(os.environ["QIRA_API_KEY"])

# Single AI instruction — let AI handle the entire workflow
task_id = bot.tasks.submit(
    "device-id",
    name="hn-top-stories",
    instruction="Go to news.ycombinator.com, extract the top 3 story titles and their scores",
)
result = bot.tasks.wait(task_id, timeout=120)
print(f"Status: {result.status}, Steps: {len(result.steps)}")

# Composed actions — precise control over each step
task_id = bot.tasks.submit("device-id", name="github-trending", actions=[
    Action.navigate("https://github.com/trending"),
    Action.wait_for("Trending repositories page is loaded"),
    Action.extract("Get the names and descriptions of the top 5 trending repositories", variable="repos"),
    Action.take_screenshot(),
])
result = bot.tasks.wait(task_id)
for step in result.steps:
    if step.output:
        print(step.output)
```

### Screenshot Mode

Control how screenshots are stored and returned via `screenshot_mode`:

| Mode | Description |
|---|---|
| `"cloud"` | Store to cloud, return URL path (default) |
| `"inline"` | No cloud storage, return binary data via WebSocket |
| `"none"` | No screenshots stored or returned |

```python
# Submit mode
task_id = bot.tasks.submit(
    "device-id",
    instruction="Open the homepage",
    screenshot_mode="inline",
)

# Interactive mode
with bot.tasks.session("device-id", screenshot_mode="none") as s:
    s.click("Login button")
```

### Download Screenshots

Download screenshots from completed tasks (only available with `"cloud"` mode):

```python
# Download a single step screenshot
bot.tasks.screenshot(task_id, step=1, path="step_1.png")

# Get screenshot bytes without saving to file
img_bytes = bot.tasks.screenshot(task_id, step=1)

# Download all screenshots as a ZIP archive
bot.tasks.screenshots(task_id, path="task_images.zip")
```

## Device Management

List connected devices:

```python
# List all devices
devices = bot.devices.list()
for d in devices:
    print(f"{d.name} ({d.id}): {d.platform}, online={d.online}")

# List online devices only
active = bot.devices.list_active()
```

## Sandbox Management

List, inspect, wake, and sleep cloud sandboxes:

```python
# List all sandboxes
sandboxes = bot.sandboxes.list()
for sb in sandboxes:
    print(f"{sb.name} ({sb.id}): {sb.status}, device={sb.device_id}")

# Get sandbox status
sb = bot.sandboxes.get("sandbox-id")
print(f"Status: {sb.status}")

# Wake a sleeping sandbox before running tasks
sb = bot.sandboxes.wake("sandbox-id")

# Put a sandbox to sleep to save resources
sb = bot.sandboxes.sleep("sandbox-id")
```

## Actions

For the full list of actions and platform support, see the [Actions Reference](https://qirabot.com/docs/ai/actions).

## Events

Listen for real-time step and screenshot events in interactive mode:

```python
from qirabot import StepEvent, ScreenshotEvent

with bot.tasks.session("device-id") as s:
    s.on("step", lambda s: print(f"Step {s.number}: {s.action} -> {s.status}"))
    s.on("screenshot", lambda s: s.save(f"screenshots/step_{s.number}.png"))

    s.click("Login button")
```

## Workflow Integration

Interactive mode keeps the device connection alive across steps. You can run your own Python code between any two device actions — read files, validate data, branch on results, write reports:

```python
import json
import os
from qirabot import Qirabot

bot = Qirabot(os.environ["QIRA_API_KEY"])

# Test data — ready to run, no extra files needed
test_cases = [
    {"url": "https://github.com",       "expect_keyword": "GitHub"},
    {"url": "https://www.wikipedia.org", "expect_keyword": "Wikipedia"},
    {"url": "https://news.ycombinator.com", "expect_keyword": "Hacker News"},
]

results = []

with bot.tasks.session("device-id", name="heading-check") as s:
    for case in test_cases:
        # Device: navigate to the page
        s.navigate(case["url"])
        s.wait_for("Page has finished loading", timeout_ms=15000)

        # Device: extract the page heading
        heading = s.extract("Get the main heading or site title text")

        # Your code: validate between steps
        passed = case["expect_keyword"].lower() in heading.lower()
        results.append({"url": case["url"], "heading": heading, "passed": passed})
        print(f"{'PASS' if passed else 'FAIL'} {case['url']} -> {heading}")

        # Conditional: screenshot only on failure
        if not passed:
            s.take_screenshot(path=f"{case['expect_keyword']}_fail.png")

print(json.dumps(results, indent=2, ensure_ascii=False))
```

Submit mode returns structured step results for post-processing:

```python
import csv

task_id = bot.tasks.submit(
    "device-id",
    name="product-hunt-scrape",
    instruction="Go to producthunt.com, extract the top 5 products with their names and taglines",
)
result = bot.tasks.wait(task_id)

with open("steps.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["step", "action", "status", "duration_ms"])
    writer.writeheader()
    for step in result.steps:
        writer.writerow({
            "step": step.number,
            "action": step.action,
            "status": step.status,
            "duration_ms": step.step_duration_ms,
        })
```

## Error Handling

```python
from qirabot import ActionError, QirabotTimeoutError, DeviceOfflineError

try:
    with bot.tasks.session("device-id", name="error-demo") as s:
        s.navigate("https://httpstat.us/500")
        s.verify("Page shows a success message")
except ActionError as e:
    print(f"Action failed: {e}")
except DeviceOfflineError:
    print("Device is offline")
except QirabotTimeoutError:
    print("Operation timed out")
```

## License

MIT
