# GPT-5.5 Computer Use Agents

OpenAI released GPT-5.5 April 2026 & among its headline capabilities is native computer use...

OpenAI shipped a model that can see your screen, click buttons, type text, and navigate software.

Before physical or embodied autonomy is achieved, digital autonomy must first be achieved.

## In Short

OpenAI released GPT-5.5 on 23 April 2026.

Among its headline capabilities is native computer use.

This means the model can observe screenshots, reason about UI state and emit structured actions.

Structured actions include click, type, scroll, keypress, drag, that an external environment executes on its behalf.

On OSWorld-Verified, which measures autonomous operation of real computer environments, GPT-5.5 scores 78.7%, narrowly ahead of Claude's 78.0%. On Terminal-Bench 2.0, it hits 82.7%.

So the model is impressive...

But the model is not the product.

The product is the loop.

**The model gives you vision. The harness gives you agency.**

## CUA (Computer Using Agent)

[Computer Use API Guide](https://developers.openai.com/api/docs/guides/tools-computer-use)

The CUA (Computer Using Agent) architecture that captures screenshots, sends them to the model, receives structured actions, executes them in a sandboxed environment, captures the next screenshot, and repeats.

The model sees and reasons.

The harness acts and constrains.

This is computer use as a systems engineering problem, not a model capability problem.

And the distinction matters more than the benchmarks.

## The CUA Loop

The Computer Using Agent architecture is deceptively simple. It's a loop with four steps:

```
┌──────────────────────────────────────────────────┐
│                  CUA Loop                        │
│                                                  │
│   1. Capture screenshot of environment           │
│              │                                   │
│              ▼                                   │
│   2. Send screenshot + goal to model             │
│              │                                   │
│              ▼                                   │
│   3. Model returns structured actions            │
│      (click, type, scroll, keypress, drag)       │
│              │                                   │
│              ▼                                   │
│   4. Execute actions in sandboxed environment    │
│              │                                   │
│              └──────── loop ─────────────────┘   │
│                                                  │
│   Exit: model returns no computer_call           │
└──────────────────────────────────────────────────┘
```

The API surface is clean.

You send a task description with `tools: [{"type": "computer"}]`.

The model responds with a `computer_call` containing an array of actions.

Each with a type (`click`, `type`, `scroll`, `keypress`, `drag`, `move`, `wait`, `screenshot`) and coordinates or parameters.

You execute those actions, capture a screenshot, and send it back as a `computer_call_output` with the base64-encoded image.

The model never touches the environment directly.

It sees pixels.

It emits structured instructions.

Everything between...the browser, the VM, the screenshot pipeline, the action execution, the sandbox boundaries...is harness.

## Changes From GPT-5.4

GPT-5.4 introduced computer use in March 2026 and scored 75% on OSWorld, exceeding the human baseline of 72.4%.

GPT-5.5 pushes this to 78.7%.

The delta is meaningful but the real changes are architectural:

### Native multimodality

GPT-5.4 processed images through a stitched-together pipeline, separate vision and language components.

GPT-5.5 handles text, images, audio, and video in a single forward pass.

For computer use, this means the model's understanding of a screenshot is not a translation from visual tokens to language tokens.

It's native visual reasoning.

The practical effect is fewer misidentified UI elements, better spatial reasoning about where things are on screen, more reliable action targeting.

### 1M token context

GPT-5.5 extends the context window to 1,050,000 tokens.

For computer use agents that run multi-step workflows, this means the model can hold the full conversation history.

Every screenshot, every action, every intermediate state, without compaction.

The harness doesn't need to manage context as aggressively.

### Improved image handling

GPT-5.5 preserves screenshot detail up to 10.24 million pixels without resizing when `image_detail` is set to `auto` or `original`.

Previous models downsampled aggressively, losing the fine-grained UI detail that computer use depends on small buttons, dropdown menus, status indicators.

### Reasoning effort control

The `reasoning.effort` parameter now supports five levels: `none`, `low`, `medium` (default), `high`, and `xhigh`.

For routine navigation steps (clicking a known button), you can dial reasoning down.

For complex decisions (choosing between ambiguous UI paths), you can dial it up.

This gives the harness fine-grained control over the cost-latency-accuracy trade-off at each step of the loop.

## Why Computer Use Is a Harness Problem

The model sees a screenshot and emits actions. Everything else is harness:

The model doesn't run in a browser or a VM.

Something does.

That something needs to be provisioned, configured, sandboxed and monitored.

OpenAI's reference implementation uses Playwright for browser environments and Docker containers with Xvfb for desktop environments.

Each has different security properties, different failure modes, and different performance characteristics.

### Action execution

The model says `click(450, 320)`.

Something translates that into an actual mouse event at those coordinates in the right environment.

If the screenshot was captured at one resolution and the environment runs at another, the coordinates are wrong.

If the environment has scrolled since the screenshot was taken, the coordinates are wrong.

If a popup appeared between screenshot capture and action execution, the coordinates target the wrong element.

### Screenshot pipeline

The quality of the screenshot determines the quality of the model's reasoning.

Compression artefacts, resolution mismatches, timing issues (capturing mid-render) and viewport boundaries all affect what the model sees.

The harness controls all of this.

### Error recovery

When the model clicks the wrong thing, the harness decides what happens next.

Does it capture a new screenshot and let the model self-correct?

Does it roll back to a checkpoint?

Does it escalate to a human?

The model has no mechanism for undoing its own actions.

The harness does.

### Safety boundaries

The model might decide to navigate to a website, enter credentials, or execute a shell command.

The harness determines whether those actions are permitted.

A computer use agent without safety constraints is a remote code execution vulnerability with a natural language interface.

This is the pattern I've been writing about, the operational logic that wraps around the model to make it reliable.

Computer use makes the pattern more visible because the gap between "model capability" and "working system" is wider than in any other agent modality.

A text-based agent that hallucinates produces wrong text. A computer use agent that hallucinates clicks the wrong button in your production system.

## The Message to Builders

If you're building computer use agents with GPT-5.5, the model is the easy part.

The hard part is everything around it.

### Invest in environment infrastructure

Browser automation (Playwright) or VM management (Docker + Xvfb) is your foundation.

The reliability of your agent is bounded by the reliability of your screenshot pipeline and action execution.

A flaky environment produces flaky agents regardless of model quality.

### Design safety as a layer, not an afterthought

Computer use agents need explicit boundaries...

Allowed URLs, allowed applications, allowed action types, human-in-the-loop triggers for high-risk actions.

These boundaries must be enforced by the harness, not instructed in the prompt.

### Use reasoning effort strategically

Not every step needs deep reasoning.

Navigation to a known URL is `reasoning.effort: low`.

Deciding which form field to fill requires `medium`.

Interpreting an ambiguous error dialog is `high`.

The harness should modulate reasoning effort per step based on task context.

### Build for self-correction, not perfection

The CUA loop is inherently self-correcting.

The model sees the result of its action in the next screenshot.

Design your harness to take advantage of this...

Capture high-quality screenshots, maintain full conversation history and let the model iterate.

Don't try to make every individual action perfect. Make the loop resilient.

## Demo

The included demo app (`gpt55_computer_use_demo.py`) demonstrates the CUA loop in two modes:

- **Simulated** — No API key needed. Pre-scripted scenarios that make the CUA loop mechanics visible.
- **Live CUA** — Real GPT-5.5 API + Playwright browser. The model sees actual screenshots and controls a real browser.

### Run

```bash
pip install gradio pillow

# Simulated mode (no API key needed)
python gpt55_computer_use_demo.py

# For live mode, also install:
pip install openai playwright
playwright install chromium
export OPENAI_API_KEY=sk-...
```

---

*Chief AI Evangelist @ Kore.ai | I'm passionate about exploring the intersection of AI and language. From Language Models, AI Agents to Agentic Applications, Development Frameworks & Data-Centric Productivity Tools, I share insights and ideas on how these technologies are shaping the future.*
