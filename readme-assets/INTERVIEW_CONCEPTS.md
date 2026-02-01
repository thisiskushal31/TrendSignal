# TrendSignal — Concepts for Interviews

Use this to explain the project in plain language without relying on code.

---

## 1. What it does (elevator pitch)

**"User uploads a screenshot of the YouTube homepage. The system tells them: what topic is trending, why it’s trending, who’s winning that trend, how they should post about it, and five copy-paste hooks for shorts or thumbnails."**

No real YouTube API — we only use the screenshot. The AI “reads” the image and the rest is reasoning from that.

---

## 2. Big picture: how it works

1. **Input:** One image (screenshot of YouTube home/recommended feed).
2. **Step 1 — Vision:** A vision model (e.g. GPT-4o) looks at the image and extracts a list of “videos”: title, channel, views, how old the video is, and a rough emotional tone (fear, curiosity, etc.). We don’t call YouTube; we only use what’s visible in the screenshot.
3. **Step 2 — Topics:** Another model takes that list and groups it into a few main “topics” (e.g. “AI & jobs”, “Business & economics”) and counts how many videos per topic.
4. **Step 3 — Strength:** For the top topic, we ask: is this trend early, heating up, or saturated? That’s a heuristic (repetition, recency), not real view counts.
5. **Step 4 — Advice:** We ask for: why YouTube might be promoting this, who’s winning (channel size/format), how to post, and five short hooks.
6. **Output:** One JSON with topic, trend strength, why trending, who’s winning, how to post, and five hooks.

So: **screenshot → vision extract → topic detection → strength → creator advice → one structured answer.**

---

## 3. Concepts you should be able to explain

### MCP (Model Context Protocol)

- **What:** A standard way for an AI app (e.g. Cursor, Claude) to call “tools” exposed by a server. The server defines tools (name, inputs, outputs); the client calls them.
- **Why we use it:** The same logic (vision → topics → strength → advice) can run as:
  - **Web app:** User uploads image → backend runs all four steps and returns JSON.
  - **Inside Cursor:** User pastes screenshot → the AI in Cursor calls our server’s four tools one by one and then formats the answer. So one codebase, two ways to use it (web + AI chat).
- **Interview line:** “We expose the pipeline as MCP tools so the same analysis can be triggered from a web upload or from an AI chat that calls our server.”

### Stateless

- **What:** No database, no user sessions. Each request: image in → run the four steps → JSON out. Nothing is stored.
- **Why:** Keeps the MVP simple and fast to build; no auth, no DB, no scaling concerns for state.
- **Interview line:** “The service is stateless: every request is independent, we don’t store anything.”

### Pipeline vs tools

- **Pipeline:** One function that does all four steps in order (vision → topics → strength → advice) and returns the final JSON. Used by the web API when you click “Analyze.”
- **Tools:** The same four steps exposed as four separate MCP tools. Used when an AI (e.g. in Cursor) calls the server step by step and then assembles the answer.
- **Interview line:** “The core is a single pipeline; we expose the same steps as MCP tools so an AI orchestrator can call them in sequence.”

### Vision vs chat (LLM)

- **Vision:** The first step needs to “see” the image. We use a model that accepts an image + text (e.g. GPT-4o). It returns structured text (e.g. JSON list of videos).
- **Chat:** Steps 2–4 don’t need the image; they get text (list of videos, topic name, etc.). So we use the same or another model with only text in/out.
- **Interview line:** “Step 1 is vision: image in, structured list of videos out. Steps 2–4 are chat: text in, JSON out.”

### Why two entry points (API + MCP server)

- **API (e.g. FastAPI):** For the web UI. User uploads a file → one HTTP POST → backend runs the full pipeline → returns JSON. Simple for a browser.
- **MCP server:** For AI-first UIs (Cursor, etc.). The AI has the screenshot in the conversation; it calls our tools (e.g. with image as base64), gets back structured data, and then writes the final answer. So the “orchestrator” is the AI; our server just does the four steps.
- **Interview line:** “We have a web API for the upload UI and an MCP server so the same logic can be used from an AI chat that calls our tools.”

---

## 4. Tech choices (short answers)

| Choice | Why |
|--------|-----|
| **OpenAI (vision + chat)** | Vision for screenshot understanding; chat for topic/strength/advice. One provider keeps the MVP simple. |
| **FastAPI** | Simple HTTP API, async, automatic request/response handling; easy to add upload + JSON response. |
| **MCP (Python SDK)** | Standard way to expose tools to AI clients; our four steps map cleanly to four tools. |
| **No database** | Stateless MVP; no user accounts or history. |
| **JSON in/out** | LLMs return text; we ask for JSON and parse it (with simple cleanup for trailing commas, etc.). |

---

## 5. If they ask “Walk me through a request”

**Web (upload UI):**

1. User selects a screenshot and clicks Analyze.
2. Browser sends POST /analyze with the image file.
3. Backend loads the image, runs the full pipeline (vision → topics → strength → advice) using the same core module.
4. Backend returns one JSON object (topic, trend_strength, why_trending, who_is_winning, how_to_post, hooks).
5. UI shows that and lets the user copy hooks.

**MCP (e.g. Cursor):**

1. User pastes or attaches a screenshot in chat and asks for a trend analysis.
2. The AI (orchestrator) has a system prompt that says: call these four tools in order.
3. It calls our server: vision_extract(image) → trend_detect_topics(videos) → trend_estimate_strength(topic, videos) → creator_advice_generator(topic, strength).
4. It gets back four structured responses, then formats them into the final answer (topic, why, who’s winning, how to post, hooks) for the user.

---

## 6. One-paragraph summary you can say out loud

*“This project is a YouTube trend analyzer that works from a single screenshot. The user uploads a screenshot of the YouTube homepage. We use a vision model to extract what videos are visible — titles, channels, rough view counts — then a chat model to group them into topics, estimate how hot the trend is, and generate creator advice: why it’s trending, who’s winning, how to post, and five copyable hooks. The core is a stateless pipeline: same four steps every time. We expose it in two ways: a web API for an upload UI and an MCP server so an AI in Cursor or similar can call the same steps as tools and assemble the answer. No database, no YouTube API — everything is driven by the screenshot and the models.”*

---

## 7. File roles (for “how is the code organized?”)

- **analysis.py** — Core logic: helpers (client, JSON parsing), then the four steps (vision, topic detection, strength, advice), then the full pipeline. Used by both the API and the MCP server.
- **api.py** — Web: serves the upload UI, accepts POST /analyze with an image, calls the pipeline, returns JSON.
- **server.py** — MCP: exposes the four steps as four tools that delegate to the same functions in analysis.
- **SYSTEM_PROMPT.md** — Instructions for the AI when it uses the MCP tools: call the tools in order and return the final shape (topic, why, who, how, hooks).

You don’t need to recite code; knowing these roles is enough to explain the design in an interview.
