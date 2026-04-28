"""
GPT-5.5 Computer Use Agent (CUA) Demo — The Harness Behind the Vision
Based on OpenAI GPT-5.5 Computer Use API (https://developers.openai.com/api/docs/guides/tools-computer-use)

Two modes:
  1. SIMULATED (default) — No API key needed. Demonstrates the full CUA loop
     with simulated screenshots and model responses.
  2. LIVE — Connects to the real OpenAI GPT-5.5 API with a Playwright browser.
     The model sees actual screenshots and controls a real browser.

Requirements:
    pip install gradio pillow

For live mode (optional):
    pip install openai playwright
    playwright install chromium
    export OPENAI_API_KEY=sk-...
"""

import base64
import io
import json
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import gradio as gr

# ---------------------------------------------------------------------------
# Optional imports for live CUA mode
# ---------------------------------------------------------------------------

_openai_available = False
_playwright_available = False

try:
    from openai import OpenAI
    _openai_available = True
except ImportError:
    pass

try:
    from playwright.sync_api import sync_playwright
    _playwright_available = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Simulated Desktop Environment
# ---------------------------------------------------------------------------

VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720


class ElementType(Enum):
    BUTTON = "button"
    TEXT_FIELD = "text_field"
    LINK = "link"
    DROPDOWN = "dropdown"
    MENU_ITEM = "menu_item"
    TAB = "tab"
    CHECKBOX = "checkbox"
    LABEL = "label"
    STATUS_BAR = "status_bar"


@dataclass
class UIElement:
    element_id: str
    element_type: ElementType
    label: str
    x: int
    y: int
    width: int
    height: int
    clickable: bool = True
    value: str = ""
    visible: bool = True

    def contains(self, px: int, py: int) -> bool:
        return (self.x <= px <= self.x + self.width and
                self.y <= py <= self.y + self.height)


@dataclass
class DesktopState:
    """Simulated desktop environment state."""
    current_app: str = "Desktop"
    url: str = ""
    elements: list = field(default_factory=list)
    typed_text: dict = field(default_factory=dict)
    clicked_elements: list = field(default_factory=list)
    status_message: str = ""
    scroll_y: int = 0
    notifications: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Application Screens — What the simulated desktop shows
# ---------------------------------------------------------------------------

APP_SCREENS = {
    "Desktop": {
        "description": "Desktop with taskbar and application icons",
        "elements": [
            UIElement("icon_browser", ElementType.BUTTON, "Chrome", 100, 300, 64, 64),
            UIElement("icon_email", ElementType.BUTTON, "Gmail", 200, 300, 64, 64),
            UIElement("icon_sheets", ElementType.BUTTON, "Google Sheets", 300, 300, 64, 64),
            UIElement("icon_terminal", ElementType.BUTTON, "Terminal", 400, 300, 64, 64),
            UIElement("taskbar", ElementType.STATUS_BAR, "Taskbar", 0, 680, 1280, 40, clickable=False),
        ],
    },
    "Browser - Google": {
        "description": "Chrome browser on Google search page",
        "elements": [
            UIElement("url_bar", ElementType.TEXT_FIELD, "URL Bar", 200, 52, 700, 32),
            UIElement("search_box", ElementType.TEXT_FIELD, "Search", 340, 400, 600, 44),
            UIElement("search_btn", ElementType.BUTTON, "Google Search", 490, 460, 120, 36),
            UIElement("lucky_btn", ElementType.BUTTON, "I'm Feeling Lucky", 620, 460, 140, 36),
            UIElement("tab_1", ElementType.TAB, "New Tab", 10, 8, 180, 28),
            UIElement("close_tab", ElementType.BUTTON, "X", 180, 10, 20, 20),
        ],
    },
    "Browser - Search Results": {
        "description": "Google search results page",
        "elements": [
            UIElement("url_bar", ElementType.TEXT_FIELD, "URL Bar", 200, 52, 700, 32),
            UIElement("result_1", ElementType.LINK, "OpenAI GPT-5.5 — Official Announcement", 140, 160, 500, 24),
            UIElement("result_2", ElementType.LINK, "GPT-5.5 Computer Use Benchmarks — TechCrunch", 140, 230, 500, 24),
            UIElement("result_3", ElementType.LINK, "GPT-5.5 vs Claude — OSWorld Comparison", 140, 300, 500, 24),
            UIElement("result_4", ElementType.LINK, "GPT-5.5 API Pricing and Availability", 140, 370, 500, 24),
            UIElement("next_page", ElementType.BUTTON, "Next", 600, 600, 60, 30),
        ],
    },
    "Browser - Article": {
        "description": "News article about GPT-5.5",
        "elements": [
            UIElement("url_bar", ElementType.TEXT_FIELD, "URL Bar", 200, 52, 700, 32),
            UIElement("article_title", ElementType.LABEL, "OpenAI Releases GPT-5.5 With Computer Use", 100, 120, 600, 36, clickable=False),
            UIElement("article_body", ElementType.LABEL, "Article content...", 100, 180, 600, 400, clickable=False),
            UIElement("copy_btn", ElementType.BUTTON, "Copy Link", 750, 120, 80, 28),
            UIElement("share_btn", ElementType.BUTTON, "Share", 840, 120, 60, 28),
            UIElement("back_btn", ElementType.BUTTON, "Back", 40, 52, 50, 32),
        ],
    },
    "Gmail - Inbox": {
        "description": "Gmail inbox with emails",
        "elements": [
            UIElement("compose_btn", ElementType.BUTTON, "Compose", 20, 80, 120, 40),
            UIElement("email_1", ElementType.LINK, "Re: Q2 Report — Final draft attached", 300, 160, 600, 28),
            UIElement("email_2", ElementType.LINK, "Meeting Tomorrow — Agenda updated", 300, 200, 600, 28),
            UIElement("email_3", ElementType.LINK, "GPT-5.5 Launch — Action items", 300, 240, 600, 28),
            UIElement("search_mail", ElementType.TEXT_FIELD, "Search mail", 300, 30, 500, 36),
            UIElement("inbox_tab", ElementType.TAB, "Inbox (3)", 160, 80, 80, 40),
            UIElement("starred_tab", ElementType.TAB, "Starred", 250, 80, 60, 40),
        ],
    },
    "Gmail - Compose": {
        "description": "Gmail compose window",
        "elements": [
            UIElement("to_field", ElementType.TEXT_FIELD, "To", 320, 120, 600, 32),
            UIElement("subject_field", ElementType.TEXT_FIELD, "Subject", 320, 165, 600, 32),
            UIElement("body_field", ElementType.TEXT_FIELD, "Body", 320, 210, 600, 300),
            UIElement("send_btn", ElementType.BUTTON, "Send", 320, 530, 80, 36),
            UIElement("discard_btn", ElementType.BUTTON, "Discard", 420, 530, 80, 36),
            UIElement("attach_btn", ElementType.BUTTON, "Attach", 520, 530, 80, 36),
        ],
    },
    "Google Sheets": {
        "description": "Google Sheets spreadsheet",
        "elements": [
            UIElement("cell_a1", ElementType.TEXT_FIELD, "A1", 60, 120, 120, 28),
            UIElement("cell_b1", ElementType.TEXT_FIELD, "B1", 180, 120, 120, 28),
            UIElement("cell_c1", ElementType.TEXT_FIELD, "C1", 300, 120, 120, 28),
            UIElement("cell_a2", ElementType.TEXT_FIELD, "A2", 60, 148, 120, 28),
            UIElement("cell_b2", ElementType.TEXT_FIELD, "B2", 180, 148, 120, 28),
            UIElement("cell_c2", ElementType.TEXT_FIELD, "C2", 300, 148, 120, 28),
            UIElement("formula_bar", ElementType.TEXT_FIELD, "Formula", 120, 80, 800, 28),
            UIElement("bold_btn", ElementType.BUTTON, "B", 60, 52, 28, 28),
            UIElement("save_indicator", ElementType.LABEL, "All changes saved", 900, 20, 150, 20, clickable=False),
        ],
    },
    "Terminal": {
        "description": "Terminal window with command prompt",
        "elements": [
            UIElement("terminal_input", ElementType.TEXT_FIELD, "$ ", 20, 600, 1240, 28),
            UIElement("terminal_output", ElementType.LABEL, "user@desktop:~$", 20, 40, 1240, 550, clickable=False),
            UIElement("close_terminal", ElementType.BUTTON, "X", 1240, 8, 24, 24),
        ],
    },
}


# ---------------------------------------------------------------------------
# CUA Action Types — Mirrors OpenAI's computer use action schema
# ---------------------------------------------------------------------------


class ActionType(Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    TYPE = "type"
    KEYPRESS = "keypress"
    SCROLL = "scroll"
    DRAG = "drag"
    MOVE = "move"
    WAIT = "wait"
    SCREENSHOT = "screenshot"


@dataclass
class CUAAction:
    """A single action in the CUA loop."""
    action_type: ActionType
    x: int = 0
    y: int = 0
    text: str = ""
    keys: list = field(default_factory=list)
    scroll_x: int = 0
    scroll_y: int = 0
    button: str = "left"
    duration_ms: int = 0


@dataclass
class CUAStep:
    """A complete step in the CUA loop: screenshot -> inference -> actions."""
    step_number: int
    screenshot_description: str
    model_reasoning: str
    actions: list  # list of CUAAction
    reasoning_effort: str  # none, low, medium, high, xhigh
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    safety_check: str = "PASS"
    safety_detail: str = ""
    self_correction: bool = False
    correction_detail: str = ""


# ---------------------------------------------------------------------------
# Safety Policy Engine — Harness-level boundary enforcement
# ---------------------------------------------------------------------------

@dataclass
class SafetyPolicy:
    allowed_apps: list = field(default_factory=lambda: [
        "Desktop", "Browser - Google", "Browser - Search Results",
        "Browser - Article", "Gmail - Inbox", "Gmail - Compose",
        "Google Sheets", "Terminal"
    ])
    allowed_urls: list = field(default_factory=lambda: [
        "google.com", "gmail.com", "docs.google.com",
        "sheets.google.com", "techcrunch.com", "openai.com"
    ])
    blocked_urls: list = field(default_factory=lambda: [
        "evil-site.com", "phishing-login.com", "crypto-miner.io",
        "data-exfil.xyz"
    ])
    allow_terminal_commands: bool = False
    allow_send_email: bool = True
    require_human_approval: list = field(default_factory=lambda: [
        "send_email", "delete_file", "run_command", "share_document"
    ])
    max_steps: int = 30


def check_safety(action: CUAAction, desktop: DesktopState, policy: SafetyPolicy) -> tuple[bool, str]:
    """Check if an action is permitted by the safety policy."""
    # Check URL navigation
    if action.action_type == ActionType.TYPE and "url_bar" in str(desktop.clicked_elements):
        text_lower = action.text.lower()
        for blocked in policy.blocked_urls:
            if blocked in text_lower:
                return False, f"BLOCKED: Navigation to '{action.text}' denied — URL in blocklist"

    # Check terminal access
    if desktop.current_app == "Terminal" and not policy.allow_terminal_commands:
        if action.action_type == ActionType.TYPE:
            return False, f"BLOCKED: Terminal command execution denied by policy"

    # Check email sending
    if desktop.current_app == "Gmail - Compose":
        for elem_id in desktop.clicked_elements:
            if elem_id == "send_btn" and not policy.allow_send_email:
                return False, "BLOCKED: Email sending denied by policy"

    return True, "PASS"


# ---------------------------------------------------------------------------
# Simulated Model Inference — What GPT-5.5 would return
# ---------------------------------------------------------------------------

WORKFLOW_SCENARIOS = {
    "Research and Email Summary": {
        "description": "Search for GPT-5.5 news, read an article, compose an email summary to a colleague.",
        "steps": [
            {
                "screen": "Desktop",
                "reasoning": "I need to open a browser to search for GPT-5.5 information. I'll click the Chrome icon on the desktop.",
                "actions": [CUAAction(ActionType.CLICK, 132, 332)],
                "effort": "low",
                "next_screen": "Browser - Google",
            },
            {
                "screen": "Browser - Google",
                "reasoning": "I'm on Google's search page. I need to click the search box and type my query about GPT-5.5.",
                "actions": [
                    CUAAction(ActionType.CLICK, 640, 422),
                    CUAAction(ActionType.TYPE, text="GPT-5.5 computer use capabilities"),
                ],
                "effort": "low",
                "next_screen": "Browser - Google",
            },
            {
                "screen": "Browser - Google",
                "reasoning": "I've typed my search query. Now I'll press Enter to submit the search.",
                "actions": [CUAAction(ActionType.KEYPRESS, keys=["Enter"])],
                "effort": "low",
                "next_screen": "Browser - Search Results",
            },
            {
                "screen": "Browser - Search Results",
                "reasoning": "Search results are showing. The first result 'OpenAI GPT-5.5 — Official Announcement' looks most relevant. I'll click it.",
                "actions": [CUAAction(ActionType.CLICK, 390, 160)],
                "effort": "medium",
                "next_screen": "Browser - Article",
            },
            {
                "screen": "Browser - Article",
                "reasoning": "I'm reading the article about GPT-5.5. Key points: native multimodality, 78.7% OSWorld score, 1M token context, computer use support. I have enough information to compose the email summary. I'll navigate to Gmail.",
                "actions": [
                    CUAAction(ActionType.KEYPRESS, keys=["Ctrl", "t"]),
                ],
                "effort": "high",
                "next_screen": "Browser - Google",
            },
            {
                "screen": "Browser - Google",
                "reasoning": "New tab opened. I need to navigate to Gmail to compose the summary email.",
                "actions": [
                    CUAAction(ActionType.CLICK, 550, 52),
                    CUAAction(ActionType.TYPE, text="gmail.com"),
                    CUAAction(ActionType.KEYPRESS, keys=["Enter"]),
                ],
                "effort": "low",
                "next_screen": "Gmail - Inbox",
            },
            {
                "screen": "Gmail - Inbox",
                "reasoning": "I'm in Gmail inbox. I need to compose a new email with the GPT-5.5 summary. I'll click the Compose button.",
                "actions": [CUAAction(ActionType.CLICK, 80, 100)],
                "effort": "low",
                "next_screen": "Gmail - Compose",
            },
            {
                "screen": "Gmail - Compose",
                "reasoning": "Compose window is open. I'll fill in the recipient, subject, and body with the GPT-5.5 summary.",
                "actions": [
                    CUAAction(ActionType.CLICK, 620, 120),
                    CUAAction(ActionType.TYPE, text="team@company.com"),
                    CUAAction(ActionType.CLICK, 620, 165),
                    CUAAction(ActionType.TYPE, text="GPT-5.5 Launch Summary — Key Capabilities"),
                    CUAAction(ActionType.CLICK, 620, 300),
                    CUAAction(ActionType.TYPE, text="Hi team,\n\nQuick summary of the GPT-5.5 launch:\n\n- Native multimodal: text, images, audio, video in single forward pass\n- Computer use: 78.7% on OSWorld (vs Claude 78.0%)\n- 1M token context window\n- Terminal-Bench 2.0: 82.7% on complex CLI workflows\n- Pricing: $5/M input, $30/M output\n\nKey takeaway: computer use is now production-viable for structured workflows (98% on Tau2-bench).\n\nBest,\nCobus"),
                ],
                "effort": "high",
                "next_screen": "Gmail - Compose",
            },
            {
                "screen": "Gmail - Compose",
                "reasoning": "Email is composed with all the key information. I'll review it once more... looks good. Clicking Send.",
                "actions": [CUAAction(ActionType.CLICK, 360, 530)],
                "effort": "medium",
                "next_screen": "Gmail - Inbox",
            },
        ],
    },
    "Spreadsheet Data Entry": {
        "description": "Open Google Sheets, enter benchmark comparison data, and format it.",
        "steps": [
            {
                "screen": "Desktop",
                "reasoning": "I need to open Google Sheets to enter benchmark data. I'll click the Sheets icon.",
                "actions": [CUAAction(ActionType.CLICK, 332, 332)],
                "effort": "low",
                "next_screen": "Google Sheets",
            },
            {
                "screen": "Google Sheets",
                "reasoning": "Spreadsheet is open. I'll start by entering column headers in row 1: Benchmark, GPT-5.5, GPT-5.4.",
                "actions": [
                    CUAAction(ActionType.CLICK, 120, 120),
                    CUAAction(ActionType.TYPE, text="Benchmark"),
                    CUAAction(ActionType.KEYPRESS, keys=["Tab"]),
                    CUAAction(ActionType.TYPE, text="GPT-5.5"),
                    CUAAction(ActionType.KEYPRESS, keys=["Tab"]),
                    CUAAction(ActionType.TYPE, text="GPT-5.4"),
                ],
                "effort": "low",
                "next_screen": "Google Sheets",
            },
            {
                "screen": "Google Sheets",
                "reasoning": "Headers entered. Now I'll move to row 2 and enter the OSWorld benchmark data.",
                "actions": [
                    CUAAction(ActionType.CLICK, 120, 148),
                    CUAAction(ActionType.TYPE, text="OSWorld-Verified"),
                    CUAAction(ActionType.KEYPRESS, keys=["Tab"]),
                    CUAAction(ActionType.TYPE, text="78.7%"),
                    CUAAction(ActionType.KEYPRESS, keys=["Tab"]),
                    CUAAction(ActionType.TYPE, text="75.0%"),
                ],
                "effort": "low",
                "next_screen": "Google Sheets",
            },
            {
                "screen": "Google Sheets",
                "reasoning": "OSWorld data entered. I'll move down to add Terminal-Bench data.",
                "actions": [
                    CUAAction(ActionType.KEYPRESS, keys=["Enter"]),
                    CUAAction(ActionType.TYPE, text="Terminal-Bench 2.0"),
                    CUAAction(ActionType.KEYPRESS, keys=["Tab"]),
                    CUAAction(ActionType.TYPE, text="82.7%"),
                    CUAAction(ActionType.KEYPRESS, keys=["Tab"]),
                    CUAAction(ActionType.TYPE, text="75.1%"),
                ],
                "effort": "low",
                "next_screen": "Google Sheets",
            },
            {
                "screen": "Google Sheets",
                "reasoning": "Now I'll bold the header row for readability. I'll select row 1 and click Bold.",
                "actions": [
                    CUAAction(ActionType.CLICK, 120, 120),
                    CUAAction(ActionType.KEYPRESS, keys=["Shift", "Ctrl", "Right", "Right"]),
                    CUAAction(ActionType.CLICK, 74, 66),
                ],
                "effort": "medium",
                "next_screen": "Google Sheets",
            },
        ],
    },
    "Terminal Workflow (Blocked)": {
        "description": "Attempt to open terminal and run commands — blocked by safety policy.",
        "steps": [
            {
                "screen": "Desktop",
                "reasoning": "I'll open the terminal to check system information.",
                "actions": [CUAAction(ActionType.CLICK, 432, 332)],
                "effort": "low",
                "next_screen": "Terminal",
            },
            {
                "screen": "Terminal",
                "reasoning": "Terminal is open. I'll run 'ls -la' to list directory contents.",
                "actions": [
                    CUAAction(ActionType.CLICK, 640, 614),
                    CUAAction(ActionType.TYPE, text="ls -la /etc/passwd"),
                ],
                "effort": "low",
                "next_screen": "Terminal",
                "safety_block": True,
            },
            {
                "screen": "Terminal",
                "reasoning": "My terminal command was blocked by the safety policy. Terminal command execution is not permitted in this sandbox. I'll close the terminal and use allowed applications instead.",
                "actions": [CUAAction(ActionType.CLICK, 1252, 20)],
                "effort": "medium",
                "next_screen": "Desktop",
                "self_correction": True,
                "correction_detail": "Model recognised safety policy block and adapted — closed terminal and will use permitted applications.",
            },
        ],
    },
    "Self-Correcting Navigation": {
        "description": "Demonstrate the CUA loop's self-correction when the model clicks the wrong element.",
        "steps": [
            {
                "screen": "Desktop",
                "reasoning": "I need to check my email. I'll click the Gmail icon on the desktop.",
                "actions": [CUAAction(ActionType.CLICK, 232, 332)],
                "effort": "low",
                "next_screen": "Gmail - Inbox",
            },
            {
                "screen": "Gmail - Inbox",
                "reasoning": "I'm in the inbox. I need to find the GPT-5.5 action items email. I see it as the third email. I'll click it.",
                "actions": [CUAAction(ActionType.CLICK, 600, 240)],
                "effort": "medium",
                "next_screen": "Gmail - Inbox",
            },
            {
                "screen": "Gmail - Inbox",
                "reasoning": "Hmm, the email didn't open — it looks like my click may have landed on the checkbox next to it instead of the email link. I can see the email is now selected/checked but not opened. Let me click directly on the email subject text this time.",
                "actions": [CUAAction(ActionType.CLICK, 500, 240)],
                "effort": "medium",
                "next_screen": "Gmail - Inbox",
                "self_correction": True,
                "correction_detail": "Model detected that its first click hit the checkbox instead of the email link. Visual feedback from the next screenshot revealed the error, and the model adjusted coordinates.",
            },
            {
                "screen": "Gmail - Inbox",
                "reasoning": "The email is now open. I can read the GPT-5.5 action items. Task complete.",
                "actions": [],
                "effort": "low",
                "next_screen": "Gmail - Inbox",
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# CUA Loop Engine — The harness that drives everything
# ---------------------------------------------------------------------------

def simulate_screenshot(screen_name: str) -> str:
    """Simulate capturing a screenshot (returns description, not actual image)."""
    screen = APP_SCREENS.get(screen_name, APP_SCREENS["Desktop"])
    elements_desc = []
    for elem in screen["elements"]:
        elements_desc.append(
            f"  [{elem.element_type.value}] '{elem.label}' at ({elem.x},{elem.y}) "
            f"size {elem.width}x{elem.height}"
        )
    return (
        f"Screen: {screen_name}\n"
        f"Description: {screen['description']}\n"
        f"Viewport: {VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}\n"
        f"Visible elements:\n" + "\n".join(elements_desc)
    )


def estimate_tokens(screenshot_desc: str, reasoning: str, actions: list) -> tuple[int, int]:
    """Estimate input and output tokens for a CUA step."""
    # Screenshot as base64 image would be ~1500-3000 tokens
    # Conversation history grows with each step
    input_tokens = 2000 + len(screenshot_desc) * 2 + random.randint(500, 1500)
    # Actions + reasoning output
    output_tokens = 200 + len(reasoning) * 2 + len(actions) * 50 + random.randint(50, 200)
    return input_tokens, output_tokens


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate cost at GPT-5.5 pricing."""
    # $5.00 per 1M input, $30.00 per 1M output
    input_cost = (input_tokens / 1_000_000) * 5.00
    output_cost = (output_tokens / 1_000_000) * 30.00
    return round(input_cost + output_cost, 6)


def estimate_latency(effort: str, num_actions: int) -> int:
    """Estimate latency based on reasoning effort."""
    base_latency = {
        "none": 200, "low": 400, "medium": 800,
        "high": 1500, "xhigh": 3000,
    }
    base = base_latency.get(effort, 800)
    action_latency = num_actions * random.randint(50, 150)
    return base + action_latency + random.randint(100, 500)


def run_cua_workflow(scenario_name: str, policy: SafetyPolicy) -> list[CUAStep]:
    """Execute a full CUA workflow and return all steps."""
    scenario = WORKFLOW_SCENARIOS.get(scenario_name)
    if not scenario:
        return []

    steps = []
    desktop = DesktopState()

    for i, step_def in enumerate(scenario["steps"]):
        desktop.current_app = step_def["screen"]

        # Step 1: Capture screenshot
        screenshot_desc = simulate_screenshot(step_def["screen"])

        # Step 2: Model inference (simulated)
        reasoning = step_def["reasoning"]
        actions = step_def["actions"]
        effort = step_def["effort"]

        # Step 3: Safety check
        safety_passed = True
        safety_detail = "All actions within policy boundaries"
        is_blocked = step_def.get("safety_block", False)

        if is_blocked:
            safety_passed = False
            for action in actions:
                passed, detail = check_safety(action, desktop, policy)
                if not passed:
                    safety_detail = detail
                    break
            if safety_passed:
                safety_passed = False
                safety_detail = "BLOCKED: Terminal command execution denied by policy"

        # Step 4: Token and cost estimation
        input_tokens, output_tokens = estimate_tokens(screenshot_desc, reasoning, actions)
        cost = estimate_cost(input_tokens, output_tokens)
        latency = estimate_latency(effort, len(actions))

        # Self-correction detection
        is_correction = step_def.get("self_correction", False)
        correction_detail = step_def.get("correction_detail", "")

        cua_step = CUAStep(
            step_number=i + 1,
            screenshot_description=screenshot_desc,
            model_reasoning=reasoning,
            actions=actions,
            reasoning_effort=effort,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency,
            cost_usd=cost,
            safety_check="BLOCKED" if not safety_passed else "PASS",
            safety_detail=safety_detail,
            self_correction=is_correction,
            correction_detail=correction_detail,
        )
        steps.append(cua_step)

        # Track clicked elements
        for action in actions:
            if action.action_type in (ActionType.CLICK, ActionType.DOUBLE_CLICK):
                screen = APP_SCREENS.get(step_def["screen"], {})
                for elem in screen.get("elements", []):
                    if elem.contains(action.x, action.y):
                        desktop.clicked_elements.append(elem.element_id)

    return steps


# ---------------------------------------------------------------------------
# Live CUA Loop — Real GPT-5.5 API + Playwright browser
# ---------------------------------------------------------------------------


def _take_browser_screenshot(page) -> str:
    """Capture a Playwright page screenshot as base64."""
    png_bytes = page.screenshot(type="png")
    return base64.b64encode(png_bytes).decode("utf-8")


def _parse_live_actions(computer_call) -> list[dict]:
    """Parse actions from a live API computer_call response item."""
    actions = []
    if hasattr(computer_call, "actions"):
        for act in computer_call.actions:
            actions.append({
                "type": getattr(act, "type", "unknown"),
                "x": getattr(act, "x", 0),
                "y": getattr(act, "y", 0),
                "text": getattr(act, "text", ""),
                "keys": getattr(act, "keys", []),
                "button": getattr(act, "button", "left"),
                "scroll_x": getattr(act, "scroll_x", 0),
                "scroll_y": getattr(act, "scroll_y", 0),
            })
    return actions


def _execute_browser_action(page, action: dict):
    """Execute a single CUA action in the Playwright browser."""
    atype = action["type"]
    x, y = action.get("x", 0), action.get("y", 0)

    if atype == "click":
        button = action.get("button", "left")
        page.mouse.click(x, y, button=button)
    elif atype == "double_click":
        page.mouse.dblclick(x, y)
    elif atype == "type":
        page.keyboard.type(action.get("text", ""))
    elif atype == "keypress":
        keys = action.get("keys", [])
        if len(keys) == 1:
            page.keyboard.press(keys[0])
        elif len(keys) > 1:
            # Modifier combos like Ctrl+C
            combo = "+".join(keys)
            page.keyboard.press(combo)
    elif atype == "scroll":
        page.mouse.wheel(action.get("scroll_x", 0), action.get("scroll_y", 0))
    elif atype == "move":
        page.mouse.move(x, y)
    elif atype == "drag":
        page.mouse.move(x, y)
        page.mouse.down()
        # If there's an end position, move there
        page.mouse.up()
    elif atype == "wait":
        time.sleep(0.5)

    # Small delay between actions for stability
    time.sleep(0.3)


def _format_live_action(action: dict) -> str:
    """Format a live action dict for display."""
    atype = action["type"]
    if atype == "click":
        return f"click({action['x']}, {action['y']}) [{action.get('button', 'left')}]"
    elif atype == "double_click":
        return f"double_click({action['x']}, {action['y']})"
    elif atype == "type":
        text = action.get("text", "")
        display = text[:60] + "..." if len(text) > 60 else text
        return f'type("{display}")'
    elif atype == "keypress":
        return f"keypress({'+'.join(action.get('keys', []))})"
    elif atype == "scroll":
        return f"scroll(dx={action.get('scroll_x', 0)}, dy={action.get('scroll_y', 0)})"
    elif atype == "move":
        return f"move({action['x']}, {action['y']})"
    elif atype == "wait":
        return "wait()"
    return atype


def run_live_cua(
    task: str,
    start_url: str,
    api_key: str,
    reasoning_effort: str = "medium",
    max_steps: int = 15,
    blocked_urls: str = "",
) -> tuple[str, list]:
    """
    Run a real CUA loop: Playwright browser + GPT-5.5 API.
    Returns (log_text, list_of_screenshot_b64).
    """
    if not _openai_available:
        return "ERROR: openai package not installed. Run: pip install openai", []
    if not _playwright_available:
        return "ERROR: playwright not installed. Run: pip install playwright && playwright install chromium", []

    key = api_key.strip() or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return "ERROR: No API key provided. Enter a key or set OPENAI_API_KEY.", []

    blocked = [u.strip() for u in blocked_urls.split(",") if u.strip()]

    client = OpenAI(api_key=key)
    lines = []
    screenshots = []
    total_input = 0
    total_output = 0

    lines.append(f"LIVE CUA SESSION")
    lines.append(f"Task: {task}")
    lines.append(f"Start URL: {start_url}")
    lines.append(f"Reasoning effort: {reasoning_effort}")
    lines.append(f"Max steps: {max_steps}")
    if blocked:
        lines.append(f"Blocked URLs: {', '.join(blocked)}")
    lines.append("=" * 70)

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=["--disable-extensions", "--disable-file-system"],
    )
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()

    try:
        # Navigate to start URL
        page.goto(start_url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1)

        # Take initial screenshot
        screenshot_b64 = _take_browser_screenshot(page)
        screenshots.append(screenshot_b64)

        # Initial API call
        lines.append(f"\n--- Step 1: Initial request ---")
        t0 = time.time()
        response = client.responses.create(
            model="gpt-5.5",
            tools=[{"type": "computer"}],
            reasoning={"effort": reasoning_effort},
            input=[
                {"role": "user", "content": [
                    {"type": "input_text", "text": task},
                    {"type": "input_image", "image_url": f"data:image/png;base64,{screenshot_b64}"},
                ]},
            ],
        )
        latency = int((time.time() - t0) * 1000)

        if hasattr(response, "usage") and response.usage:
            total_input += getattr(response.usage, "input_tokens", 0)
            total_output += getattr(response.usage, "output_tokens", 0)

        lines.append(f"  Latency: {latency}ms")

        # CUA loop
        for step in range(2, max_steps + 1):
            # Find computer_call in response output
            computer_calls = [
                item for item in response.output
                if getattr(item, "type", "") == "computer_call"
            ]
            if not computer_calls:
                lines.append(f"\n--- Loop complete: no computer_call returned ---")
                # Collect any text output
                for item in response.output:
                    if getattr(item, "type", "") == "message":
                        for block in getattr(item, "content", []):
                            if getattr(block, "type", "") == "text":
                                lines.append(f"  Model says: {block.text[:300]}")
                break

            call = computer_calls[0]
            actions = _parse_live_actions(call)
            call_id = getattr(call, "call_id", "unknown")

            lines.append(f"\n--- Step {step}: {len(actions)} action(s) ---")
            for j, action in enumerate(actions):
                # Safety: check for blocked URLs in type actions
                if action["type"] == "type" and blocked:
                    text_lower = action.get("text", "").lower()
                    is_blocked = any(b.lower() in text_lower for b in blocked)
                    if is_blocked:
                        lines.append(f"  {j+1}. BLOCKED by harness: {_format_live_action(action)}")
                        continue

                lines.append(f"  {j+1}. {_format_live_action(action)}")
                _execute_browser_action(page, action)

            # Capture new screenshot
            time.sleep(0.5)
            screenshot_b64 = _take_browser_screenshot(page)
            screenshots.append(screenshot_b64)

            # Send screenshot back to model
            t0 = time.time()
            response = client.responses.create(
                model="gpt-5.5",
                tools=[{"type": "computer"}],
                reasoning={"effort": reasoning_effort},
                previous_response_id=response.id,
                input=[{
                    "type": "computer_call_output",
                    "call_id": call_id,
                    "output": {
                        "type": "computer_screenshot",
                        "image_url": f"data:image/png;base64,{screenshot_b64}",
                        "detail": "original",
                    },
                }],
            )
            latency = int((time.time() - t0) * 1000)

            if hasattr(response, "usage") and response.usage:
                total_input += getattr(response.usage, "input_tokens", 0)
                total_output += getattr(response.usage, "output_tokens", 0)

            lines.append(f"  Latency: {latency}ms")
        else:
            lines.append(f"\n--- Max steps ({max_steps}) reached ---")

    except Exception as e:
        lines.append(f"\nERROR: {type(e).__name__}: {e}")
    finally:
        context.close()
        browser.close()
        pw.stop()

    # Summary
    total_cost = (total_input / 1_000_000) * 5.0 + (total_output / 1_000_000) * 30.0
    lines.append(f"\n{'=' * 70}")
    lines.append(f"SUMMARY")
    lines.append(f"  Screenshots captured: {len(screenshots)}")
    lines.append(f"  Input tokens:  {total_input:,}")
    lines.append(f"  Output tokens: {total_output:,}")
    lines.append(f"  Estimated cost: ${total_cost:.4f}")

    return "\n".join(lines), screenshots


# ---------------------------------------------------------------------------
# Formatting — Make the CUA loop visible
# ---------------------------------------------------------------------------

def format_action(action: CUAAction) -> str:
    """Format a single CUA action for display."""
    if action.action_type == ActionType.CLICK:
        return f"click({action.x}, {action.y}) [{action.button}]"
    elif action.action_type == ActionType.DOUBLE_CLICK:
        return f"double_click({action.x}, {action.y})"
    elif action.action_type == ActionType.TYPE:
        display_text = action.text[:60] + "..." if len(action.text) > 60 else action.text
        return f'type("{display_text}")'
    elif action.action_type == ActionType.KEYPRESS:
        return f"keypress({'+'.join(action.keys)})"
    elif action.action_type == ActionType.SCROLL:
        return f"scroll(dx={action.scroll_x}, dy={action.scroll_y})"
    elif action.action_type == ActionType.DRAG:
        return f"drag({action.x}, {action.y})"
    elif action.action_type == ActionType.MOVE:
        return f"move({action.x}, {action.y})"
    elif action.action_type == ActionType.WAIT:
        return f"wait({action.duration_ms}ms)"
    elif action.action_type == ActionType.SCREENSHOT:
        return "screenshot()"
    return str(action.action_type.value)


def format_step_log(steps: list[CUAStep]) -> str:
    """Format the full CUA loop execution log."""
    if not steps:
        return "No steps executed."

    lines = []
    total_cost = 0.0
    total_input = 0
    total_output = 0
    total_latency = 0

    for step in steps:
        total_cost += step.cost_usd
        total_input += step.input_tokens
        total_output += step.output_tokens
        total_latency += step.latency_ms

        lines.append(f"{'=' * 80}")
        lines.append(f"STEP {step.step_number}  |  reasoning_effort: {step.reasoning_effort}  |  "
                      f"latency: {step.latency_ms}ms  |  cost: ${step.cost_usd:.4f}")
        lines.append(f"{'=' * 80}")

        # Screenshot
        lines.append(f"\n[SCREENSHOT CAPTURED]")
        for line in step.screenshot_description.split("\n")[:3]:
            lines.append(f"  {line}")
        lines.append(f"  ...")

        # Model reasoning
        lines.append(f"\n[MODEL REASONING]")
        lines.append(f"  {step.model_reasoning}")

        # Safety check
        if step.safety_check != "PASS":
            lines.append(f"\n[SAFETY] {step.safety_detail}")

        # Self-correction
        if step.self_correction:
            lines.append(f"\n[SELF-CORRECTION] {step.correction_detail}")

        # Actions
        if step.actions:
            lines.append(f"\n[ACTIONS] ({len(step.actions)} action{'s' if len(step.actions) != 1 else ''})")
            for j, action in enumerate(step.actions):
                lines.append(f"  {j+1}. {format_action(action)}")
        else:
            lines.append(f"\n[ACTIONS] No actions — task complete")

        # Token usage
        lines.append(f"\n[TOKENS] input: {step.input_tokens:,}  output: {step.output_tokens:,}")

        lines.append("")

    # Summary
    lines.append(f"{'=' * 80}")
    lines.append(f"WORKFLOW SUMMARY")
    lines.append(f"{'=' * 80}")
    lines.append(f"  Steps:          {len(steps)}")
    lines.append(f"  Total tokens:   {total_input + total_output:,} (input: {total_input:,}, output: {total_output:,})")
    lines.append(f"  Total latency:  {total_latency:,}ms ({total_latency/1000:.1f}s)")
    lines.append(f"  Total cost:     ${total_cost:.4f}")
    lines.append(f"  Safety blocks:  {sum(1 for s in steps if s.safety_check != 'PASS')}")
    lines.append(f"  Self-corrections: {sum(1 for s in steps if s.self_correction)}")

    avg_cost_per_step = total_cost / len(steps) if steps else 0
    lines.append(f"  Avg cost/step:  ${avg_cost_per_step:.4f}")

    return "\n".join(lines)


def format_harness_analysis(steps: list[CUAStep]) -> str:
    """Analyse what the harness does vs what the model does."""
    if not steps:
        return "Run a workflow first."

    total_actions = sum(len(s.actions) for s in steps)
    safety_blocks = sum(1 for s in steps if s.safety_check != "PASS")
    corrections = sum(1 for s in steps if s.self_correction)

    lines = []
    lines.append("HARNESS vs MODEL — Who Does What?")
    lines.append("=" * 60)

    lines.append("\nMODEL RESPONSIBILITIES:")
    lines.append(f"  - Interpret {len(steps)} screenshots (visual reasoning)")
    lines.append(f"  - Generate {total_actions} structured actions")
    lines.append(f"  - Reason about UI state at each step")
    if corrections > 0:
        lines.append(f"  - Self-correct {corrections} time(s) from visual feedback")

    lines.append("\nHARNESS RESPONSIBILITIES:")
    lines.append(f"  - Provision and manage sandbox environment")
    lines.append(f"  - Capture {len(steps)} high-fidelity screenshots")
    lines.append(f"  - Execute {total_actions} actions in the environment")
    lines.append(f"  - Enforce safety policy ({safety_blocks} action(s) blocked)")
    lines.append(f"  - Modulate reasoning effort across {len(steps)} steps")
    lines.append(f"  - Track token usage and cost (${sum(s.cost_usd for s in steps):.4f})")
    lines.append(f"  - Manage conversation history (previous_response_id chain)")
    lines.append(f"  - Convert screenshots to base64 at correct resolution")
    lines.append(f"  - Translate model actions to environment-specific events")
    lines.append(f"  - Monitor for stuck loops and escalation triggers")

    model_count = 3 + (1 if corrections > 0 else 0)
    harness_count = 10
    lines.append(f"\nRESPONSIBILITY RATIO: Model {model_count} / Harness {harness_count}")
    lines.append(f"The model sees and decides. The harness does everything else.")

    # Effort distribution
    lines.append(f"\nREASONING EFFORT DISTRIBUTION:")
    effort_counts = {}
    for s in steps:
        effort_counts[s.reasoning_effort] = effort_counts.get(s.reasoning_effort, 0) + 1
    for effort, count in sorted(effort_counts.items()):
        bar = "#" * (count * 4)
        lines.append(f"  {effort:<8} {bar} ({count} step{'s' if count != 1 else ''})")

    lines.append(f"\nCOST OPTIMISATION INSIGHT:")
    low_effort = sum(1 for s in steps if s.reasoning_effort in ("none", "low"))
    high_effort = sum(1 for s in steps if s.reasoning_effort in ("high", "xhigh"))
    lines.append(f"  {low_effort}/{len(steps)} steps use low/no reasoning (navigation, routine clicks)")
    lines.append(f"  {high_effort}/{len(steps)} steps use high reasoning (decisions, content creation)")
    lines.append(f"  The harness modulates effort per step — the model cannot do this itself.")

    return "\n".join(lines)


def format_api_trace(steps: list[CUAStep], scenario_name: str) -> str:
    """Show the equivalent API calls for each step."""
    if not steps:
        return "Run a workflow first."

    lines = []
    lines.append("API CALL TRACE — What the harness sends to OpenAI")
    lines.append("=" * 60)

    # Initial call
    lines.append(f'\n# Step 1: Initial request')
    lines.append(f'response = client.responses.create(')
    lines.append(f'    model="gpt-5.5",')
    lines.append(f'    tools=[{{"type": "computer"}}],')
    lines.append(f'    reasoning={{"effort": "{steps[0].reasoning_effort}"}},')
    lines.append(f'    input="{WORKFLOW_SCENARIOS[scenario_name]["description"]}"')
    lines.append(f')')

    # Continuation calls
    for i, step in enumerate(steps[1:], 2):
        lines.append(f'\n# Step {i}: Send screenshot, receive next actions')
        lines.append(f'response = client.responses.create(')
        lines.append(f'    model="gpt-5.5",')
        lines.append(f'    tools=[{{"type": "computer"}}],')
        lines.append(f'    reasoning={{"effort": "{step.reasoning_effort}"}},')
        lines.append(f'    previous_response_id=response.id,')
        lines.append(f'    input=[{{')
        lines.append(f'        "type": "computer_call_output",')
        lines.append(f'        "call_id": computer_call.call_id,')
        lines.append(f'        "output": {{')
        lines.append(f'            "type": "computer_screenshot",')
        lines.append(f'            "image_url": "data:image/png;base64,<screenshot>",')
        lines.append(f'            "detail": "original"')
        lines.append(f'        }}')
        lines.append(f'    }}]')
        lines.append(f')')

        if step.safety_check != "PASS":
            lines.append(f'# HARNESS INTERCEPT: {step.safety_detail}')
            lines.append(f'# Action NOT executed — harness blocks before environment')

        if step.actions:
            lines.append(f'# Model returns {len(step.actions)} action(s):')
            for action in step.actions[:3]:
                lines.append(f'#   {format_action(action)}')
            if len(step.actions) > 3:
                lines.append(f'#   ... and {len(step.actions) - 3} more')

    lines.append(f'\n# Loop exits when response contains no computer_call')
    lines.append(f'# Total API calls: {len(steps)}')

    return "\n".join(lines)


def format_cost_breakdown(steps: list[CUAStep]) -> str:
    """Detailed cost analysis."""
    if not steps:
        return "Run a workflow first."

    lines = []
    lines.append("COST BREAKDOWN — GPT-5.5 Pricing ($5/M input, $30/M output)")
    lines.append("=" * 60)
    lines.append(f"\n{'Step':<6} {'Effort':<10} {'Input Tok':<12} {'Output Tok':<12} {'Cost':<10} {'Latency':<10}")
    lines.append("-" * 60)

    for step in steps:
        lines.append(
            f"{step.step_number:<6} {step.reasoning_effort:<10} "
            f"{step.input_tokens:<12,} {step.output_tokens:<12,} "
            f"${step.cost_usd:<9.4f} {step.latency_ms}ms"
        )

    total_input = sum(s.input_tokens for s in steps)
    total_output = sum(s.output_tokens for s in steps)
    total_cost = sum(s.cost_usd for s in steps)
    total_latency = sum(s.latency_ms for s in steps)

    lines.append("-" * 60)
    lines.append(
        f"{'TOTAL':<6} {'—':<10} "
        f"{total_input:<12,} {total_output:<12,} "
        f"${total_cost:<9.4f} {total_latency}ms"
    )

    lines.append(f"\nCOST COMPARISON:")
    lines.append(f"  This workflow via computer use:    ${total_cost:.4f}")
    lines.append(f"  Same workflow via structured API:  ~$0.0010 (estimated)")
    lines.append(f"  Cost ratio:                        {total_cost/0.001:.0f}x more expensive")
    lines.append(f"\n  Computer use is the universal fallback — it works with")
    lines.append(f"  any visual interface, including legacy systems with no API.")
    lines.append(f"  The cost is the price of universality.")

    # Reasoning effort impact
    lines.append(f"\nREASONING EFFORT IMPACT ON COST:")
    for effort in ["low", "medium", "high"]:
        effort_steps = [s for s in steps if s.reasoning_effort == effort]
        if effort_steps:
            avg_cost = sum(s.cost_usd for s in effort_steps) / len(effort_steps)
            avg_latency = sum(s.latency_ms for s in effort_steps) / len(effort_steps)
            lines.append(f"  {effort:<8}: avg ${avg_cost:.4f}/step, avg {avg_latency:.0f}ms latency")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

def create_cost_chart(steps: list[CUAStep]):
    """Create a cost-per-step bar chart."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not steps:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Run a workflow first", ha="center", va="center", fontsize=14)
        return fig

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    # Cost per step
    step_nums = [s.step_number for s in steps]
    costs = [s.cost_usd for s in steps]
    colors = []
    for s in steps:
        if s.safety_check != "PASS":
            colors.append("#F44336")
        elif s.self_correction:
            colors.append("#FF9800")
        else:
            colors.append("#4CAF50")

    ax1.bar(step_nums, costs, color=colors, edgecolor="white")
    ax1.set_xlabel("Step")
    ax1.set_ylabel("Cost (USD)")
    ax1.set_title("Cost per CUA Step")
    ax1.set_xticks(step_nums)
    ax1.grid(axis="y", alpha=0.3)

    # Latency per step by reasoning effort
    effort_colors = {
        "none": "#E0E0E0", "low": "#4CAF50", "medium": "#2196F3",
        "high": "#FF9800", "xhigh": "#F44336"
    }
    latencies = [s.latency_ms for s in steps]
    bar_colors = [effort_colors.get(s.reasoning_effort, "#9E9E9E") for s in steps]

    ax2.bar(step_nums, latencies, color=bar_colors, edgecolor="white")
    ax2.set_xlabel("Step")
    ax2.set_ylabel("Latency (ms)")
    ax2.set_title("Latency by Reasoning Effort")
    ax2.set_xticks(step_nums)
    ax2.grid(axis="y", alpha=0.3)

    # Legend for effort levels
    from matplotlib.patches import Patch
    used_efforts = set(s.reasoning_effort for s in steps)
    legend_elements = [
        Patch(facecolor=effort_colors.get(e, "#9E9E9E"), label=e)
        for e in ["low", "medium", "high", "xhigh"] if e in used_efforts
    ]
    ax2.legend(handles=legend_elements, loc="upper right", fontsize=8)

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Gradio Interface
# ---------------------------------------------------------------------------

DESCRIPTION = """
## Computer Use Is the Harness Problem Nobody Is Talking About

**Two modes:**
- **Simulated** — No API key needed. Pre-scripted scenarios that make the CUA
  loop mechanics visible.
- **Live CUA** — Real GPT-5.5 API + Playwright browser. The model sees actual
  screenshots and controls a real browser. Requires `openai` + `playwright`.

**The model sees pixels. The harness controls the world.**

The demo makes visible what production CUA systems actually do:
- **Screenshot capture** and encoding pipeline
- **Model inference** with structured action output
- **Safety boundary enforcement** at the harness level
- **Reasoning effort modulation** per step (low for navigation, high for decisions)
- **Self-correction** through visual feedback
- **Cost tracking** across the full workflow
"""


def run_workflow_handler(scenario_name: str, allow_terminal: bool, allow_email: bool):
    """Run a CUA workflow with the specified safety policy."""
    policy = SafetyPolicy(
        allow_terminal_commands=allow_terminal,
        allow_send_email=allow_email,
    )
    steps = run_cua_workflow(scenario_name, policy)

    log = format_step_log(steps)
    harness = format_harness_analysis(steps)
    api_trace = format_api_trace(steps, scenario_name)
    cost = format_cost_breakdown(steps)
    chart = create_cost_chart(steps)

    return log, harness, api_trace, cost, chart


def build_app():
    with gr.Blocks(title="GPT-5.5 Computer Use Agent Demo") as app:
        gr.Markdown(DESCRIPTION)

        with gr.Tab("CUA Loop Simulator"):
            gr.Markdown(
                "### Run a Computer Use Workflow\n"
                "Select a scenario and watch the CUA loop execute step-by-step — "
                "screenshot, inference, actions, safety checks, repeat."
            )

            with gr.Row():
                with gr.Column(scale=1):
                    scenario_select = gr.Dropdown(
                        label="Workflow Scenario",
                        choices=list(WORKFLOW_SCENARIOS.keys()),
                        value="Research and Email Summary",
                        info="Each scenario demonstrates different CUA loop behaviours.",
                    )

                    gr.Markdown("#### Safety Policy (Harness-Level)")
                    allow_terminal = gr.Checkbox(
                        label="Allow terminal commands",
                        value=False,
                        info="If unchecked, terminal actions are blocked by the harness.",
                    )
                    allow_email = gr.Checkbox(
                        label="Allow sending email",
                        value=True,
                        info="If unchecked, email send actions are blocked.",
                    )

                    run_btn = gr.Button(
                        "Run CUA Workflow",
                        variant="primary",
                        size="lg",
                    )

                    gr.Markdown(
                        "**Scenarios:**\n"
                        "- **Research and Email Summary** — Full multi-app workflow\n"
                        "- **Spreadsheet Data Entry** — Structured data input\n"
                        "- **Terminal Workflow (Blocked)** — Safety policy in action\n"
                        "- **Self-Correcting Navigation** — Error recovery via visual feedback"
                    )

                with gr.Column(scale=2):
                    log_box = gr.Textbox(
                        label="CUA Loop Execution Log",
                        lines=30,
                        interactive=False,
                    )

            chart_plot = gr.Plot(label="Cost and Latency Analysis")

        with gr.Tab("Live CUA (Real API)"):
            live_available = _openai_available and _playwright_available
            status_parts = []
            if not _openai_available:
                status_parts.append("openai (pip install openai)")
            if not _playwright_available:
                status_parts.append("playwright (pip install playwright && playwright install chromium)")
            missing_msg = f"Missing: {', '.join(status_parts)}" if status_parts else ""

            gr.Markdown(
                "### Live Computer Use — Real GPT-5.5 API + Playwright Browser\n"
                "The model sees **actual browser screenshots** and emits actions that are "
                "executed in a real headless Chromium instance. This is the full CUA loop.\n\n"
                + (f"**{missing_msg}** — install to enable live mode." if missing_msg else
                   "All dependencies installed. Ready to run.")
            )

            with gr.Row():
                with gr.Column(scale=1):
                    live_api_key = gr.Textbox(
                        label="OpenAI API Key",
                        type="password",
                        placeholder="sk-... (or set OPENAI_API_KEY env var)",
                        info="Key is used for this session only and never stored.",
                    )
                    live_task = gr.Textbox(
                        label="Task",
                        value="Search for 'GPT-5.5 computer use benchmarks', click the first result, and summarise what you see.",
                        lines=3,
                        info="Natural language instruction for the CUA agent.",
                    )
                    live_url = gr.Textbox(
                        label="Start URL",
                        value="https://www.google.com",
                        info="The browser navigates here before the CUA loop starts.",
                    )
                    live_effort = gr.Dropdown(
                        label="Reasoning Effort",
                        choices=["low", "medium", "high"],
                        value="medium",
                        info="Controls depth of model reasoning per step.",
                    )
                    live_max_steps = gr.Slider(
                        label="Max Steps",
                        minimum=3,
                        maximum=30,
                        value=10,
                        step=1,
                        info="Safety limit — loop exits after this many steps.",
                    )
                    live_blocked = gr.Textbox(
                        label="Blocked URLs (comma-separated)",
                        value="evil-site.com, phishing-login.com",
                        info="Harness-level URL blocklist. Typed URLs matching these are blocked before execution.",
                    )
                    live_run_btn = gr.Button(
                        "Run Live CUA",
                        variant="primary",
                        size="lg",
                        interactive=live_available,
                    )

                with gr.Column(scale=2):
                    live_log = gr.Textbox(
                        label="Live CUA Execution Log",
                        lines=30,
                        interactive=False,
                    )

            gr.Markdown("#### Browser Screenshots (captured at each step)")
            live_gallery = gr.Gallery(
                label="Screenshots",
                columns=3,
                height="auto",
            )

            def run_live_handler(api_key, task, url, effort, max_steps, blocked):
                log, screenshot_b64s = run_live_cua(
                    task=task,
                    start_url=url,
                    api_key=api_key,
                    reasoning_effort=effort,
                    max_steps=int(max_steps),
                    blocked_urls=blocked,
                )
                # Convert base64 screenshots to PIL images for gallery
                images = []
                try:
                    from PIL import Image
                    for i, b64 in enumerate(screenshot_b64s):
                        img_bytes = base64.b64decode(b64)
                        img = Image.open(io.BytesIO(img_bytes))
                        images.append((img, f"Step {i + 1}"))
                except ImportError:
                    pass  # No PIL — gallery will be empty
                return log, images

            live_run_btn.click(
                fn=run_live_handler,
                inputs=[live_api_key, live_task, live_url, live_effort, live_max_steps, live_blocked],
                outputs=[live_log, live_gallery],
            )

        with gr.Tab("Harness Analysis"):
            gr.Markdown(
                "### Model vs Harness — Who Does What?\n"
                "See the division of responsibilities between the model (vision + reasoning) "
                "and the harness (everything else)."
            )
            harness_box = gr.Textbox(
                label="Harness vs Model Analysis",
                lines=35,
                interactive=False,
            )

        with gr.Tab("API Trace"):
            gr.Markdown(
                "### Equivalent API Calls\n"
                "The actual `client.responses.create()` calls the harness would make "
                "to OpenAI's API at each step of the loop."
            )
            api_box = gr.Textbox(
                label="API Call Trace",
                lines=40,
                interactive=False,
            )

        with gr.Tab("Cost Analysis"):
            gr.Markdown(
                "### Cost Breakdown\n"
                "Token usage, cost per step, and the economic case for computer use vs structured APIs."
            )
            cost_box = gr.Textbox(
                label="Cost Breakdown",
                lines=35,
                interactive=False,
            )

        with gr.Tab("How CUA Works"):
            gr.Markdown("""
### The CUA Loop Architecture

```
                YOUR APPLICATION
                      │
         ┌────────────▼────────────────┐
         │      HARNESS (Your Code)     │
         │                              │
         │  ┌──────────────────────┐   │
         │  │  1. Capture Screenshot│   │
         │  │     (PNG → base64)   │   │
         │  └──────────┬───────────┘   │
         │             │               │
         │  ┌──────────▼───────────┐   │
         │  │  2. Safety Check     │   │
         │  │     (URL, app, action │   │
         │  │      policy check)   │   │
         │  └──────────┬───────────┘   │
         │             │               │
         │  ┌──────────▼───────────┐   │
         │  │  3. Send to GPT-5.5  │───┼──► OpenAI API
         │  │     (screenshot +    │   │    model="gpt-5.5"
         │  │      history)        │◄──┼─── computer_call response
         │  └──────────┬───────────┘   │
         │             │               │
         │  ┌──────────▼───────────┐   │
         │  │  4. Execute Actions  │   │
         │  │     click(x,y)       │   │
         │  │     type("text")     │   │
         │  │     keypress(Enter)  │   │
         │  │     scroll(dx,dy)    │   │
         │  └──────────┬───────────┘   │
         │             │               │
         │             └───── loop ────┘
         │                              │
         │  Exit: no computer_call      │
         └──────────────────────────────┘
```

### Action Types

| Action | Parameters | Example |
|--------|-----------|---------|
| `click` | x, y, button | `click(450, 320)` — left click at coordinates |
| `double_click` | x, y | `double_click(450, 320)` |
| `type` | text | `type("hello world")` |
| `keypress` | keys[] | `keypress(["Ctrl", "c"])` |
| `scroll` | scrollX, scrollY | `scroll(0, -300)` — scroll up |
| `drag` | path[] | `drag([(100,100), (200,200)])` |
| `move` | x, y | `move(450, 320)` |
| `wait` | duration_ms | `wait(1000)` |
| `screenshot` | — | Capture current state |

### API Call Pattern

```python
from openai import OpenAI
client = OpenAI()

# Initial request
response = client.responses.create(
    model="gpt-5.5",
    tools=[{"type": "computer"}],
    reasoning={"effort": "medium"},
    input="Search for GPT-5.5 news and email a summary"
)

# CUA loop
while True:
    computer_calls = [
        item for item in response.output
        if item.type == "computer_call"
    ]
    if not computer_calls:
        break  # Task complete

    for call in computer_calls:
        # Execute actions in your environment
        for action in call.actions:
            execute_action(action)  # Your harness code

        # Capture screenshot
        screenshot_b64 = capture_screenshot()

        # Send back to model
        response = client.responses.create(
            model="gpt-5.5",
            tools=[{"type": "computer"}],
            previous_response_id=response.id,
            input=[{
                "type": "computer_call_output",
                "call_id": call.call_id,
                "output": {
                    "type": "computer_screenshot",
                    "image_url": f"data:image/png;base64,{screenshot_b64}",
                    "detail": "original"
                }
            }]
        )
```

### Key Design Decisions (All Harness-Level)

**Environment:** Browser (Playwright) vs VM (Docker + Xvfb)
- Browser: lighter, faster, limited to web apps
- VM: heavier, slower, works with any desktop application

**Screenshot quality:** `detail: "original"` preserves up to 10.24M pixels
- Higher resolution = better UI element recognition
- Higher resolution = more tokens = higher cost

**Reasoning effort:** Modulate per step
- `low` for known navigation (clicking a familiar button)
- `medium` for standard decisions (selecting a search result)
- `high` for complex reasoning (composing content, interpreting errors)

**Safety:** Enforce at the harness, not in the prompt
- URL allowlists enforced before action execution
- Application boundaries enforced by sandbox configuration
- Human-in-the-loop triggers for high-risk actions (send, delete, share)

### GPT-5.5 vs GPT-5.5 Pro

| Feature | GPT-5.5 | GPT-5.5 Pro |
|---------|---------|-------------|
| Computer use | Yes | **No** |
| Context window | 1M tokens | 1M tokens |
| Input pricing | $5/M | Higher |
| Speed | Faster | Slower (deeper reasoning) |
| Best for | CUA loops, real-time | Complex analysis, research |

GPT-5.5 Pro does **not** support computer use — the extended reasoning
adds latency that breaks the CUA loop's responsiveness requirements.

### The Model Sees Pixels. The Harness Controls the World.
""")

        # Wire up the run button to all output tabs
        run_btn.click(
            fn=run_workflow_handler,
            inputs=[scenario_select, allow_terminal, allow_email],
            outputs=[log_box, harness_box, api_box, cost_box, chart_plot],
        )

    return app


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = build_app()
    app.launch(theme=gr.themes.Default())
