"""
TrendSignal — core analysis logic.

Used by:
  - Web API (api.py): POST /analyze runs the full pipeline.
  - MCP server (server.py): each step is exposed as a callable tool.

Flow: screenshot → vision extract → topic detection → strength estimate → creator advice.
All reasoning via OpenAI (vision + chat). Stateless; no DB.
"""
import base64
import json
import re
import os
from typing import Any

from openai import OpenAI

_client: OpenAI | None = None

EMOTIONAL_TONES = ("fear", "curiosity", "confidence", "urgency", "neutral")
TREND_STRENGTHS = ("EARLY", "HEATING_UP", "SATURATED")


# -----------------------------------------------------------------------------
# Helpers: client, image, response parsing
# -----------------------------------------------------------------------------


def _client_get() -> OpenAI:
    global _client
    if _client is None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY is required")
        _client = OpenAI(api_key=key)
    return _client


def _ensure_base64_image(image: str) -> str:
    """Accept base64 string or data URL; return raw base64 for API."""
    if image.startswith("data:"):
        # data:image/png;base64,XXXX
        image = image.split(",", 1)[-1]
    return image


def _message_content_to_text(content: Any) -> str:
    """Extract plain text from OpenAI message content (string or list of blocks)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return (block.get("text") or "").strip()
            if hasattr(block, "text"):
                return (getattr(block, "text") or "").strip()
        return ""
    return str(content).strip()


def _parse_json(text: str) -> dict[str, Any]:
    """Parse JSON from LLM output; fix common issues (trailing commas, markdown)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    text = text.strip()
    # Remove trailing commas before } or ] (invalid in JSON)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try stripping to first { and last }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        # Fix missing comma: } { -> }, {  and  ] { -> ], {
        repaired = re.sub(r"}\s*{", "},{", text)
        repaired = re.sub(r"]\s*{", "],{", repaired)
        # Fix missing comma after number/literal before next key: 0 "key" -> 0, "key"
        repaired = re.sub(r"(\d)\s*\n\s*\"", r"\1,\n\"", repaired)
        repaired = re.sub(r"(true|false|null)\s*\n\s*\"", r"\1,\n\"", repaired)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass
        raise


# -----------------------------------------------------------------------------
# Step 1: Vision — extract video metadata from screenshot
# -----------------------------------------------------------------------------


def vision_extract_youtube_homepage(image: str) -> dict[str, Any]:
    """
    Extract video metadata from a YouTube homepage screenshot.
    image: base64-encoded image or data URL.
    Returns: { "videos": [ { title, creator, views, hours_since_posted, emotional_tone }, ... ] }
    """
    client = _client_get()
    b64 = _ensure_base64_image(image)
    vision_model = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o")

    prompt = """You are analyzing a screenshot of the YouTube homepage (recommended/home feed).
For each visible video thumbnail/card, extract:
- title: exact or best-effort title
- creator: channel or creator name
- views: number if visible, else 0
- hours_since_posted: estimate from "X hours ago" / "X days ago" (convert to hours), else 0
- emotional_tone: one of fear, curiosity, confidence, urgency, neutral (infer from title/thumbnail)

Return a JSON object with a single key "videos" containing an array of such objects.
Only include videos you can clearly see. Be concise. No markdown, raw JSON only."""

    resp = client.chat.completions.create(
        model=vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
        max_tokens=2048,
    )
    text = _message_content_to_text(resp.choices[0].message.content)
    data = _parse_json(text)
    videos_raw = data.get("videos", [])
    if isinstance(videos_raw, dict):
        videos_raw = list(videos_raw.values()) if videos_raw else []
    if not isinstance(videos_raw, list):
        videos_raw = []
    # Normalize each item to a plain dict (primitives only) to avoid unhashable dict issues
    videos: list[dict[str, Any]] = []
    for v in videos_raw:
        if not isinstance(v, dict):
            continue
        tone = (v.get("emotional_tone") or "neutral")
        if isinstance(tone, str):
            tone = tone.lower()
        else:
            tone = "neutral"
        tone = tone if tone in EMOTIONAL_TONES else "neutral"
        videos.append({
            "title": str(v.get("title") or ""),
            "creator": str(v.get("creator") or ""),
            "views": int(v.get("views")) if isinstance(v.get("views"), (int, float)) else 0,
            "hours_since_posted": int(v.get("hours_since_posted")) if isinstance(v.get("hours_since_posted"), (int, float)) else 0,
            "emotional_tone": tone,
        })
    return {"videos": videos}


# -----------------------------------------------------------------------------
# Step 2: Trend — detect dominant topics from video list
# -----------------------------------------------------------------------------


def trend_detect_topics(videos: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Group extracted videos into dominant trending topics.
    Returns: { "topics": [ { "topic_name": str, "video_count": int }, ... ] }
    """
    if not videos:
        return {"topics": []}
    client = _client_get()
    chat_model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o")

    videos_summary = [{"title": v.get("title"), "creator": v.get("creator")} for v in videos]
    prompt = f"""Given this list of videos from a YouTube homepage, group them into dominant trending topics.
Videos (title / creator): {json.dumps(videos_summary)}

For each topic that appears multiple times or is clearly dominant, output:
- topic_name: short label (e.g. "AI & Job Insecurity", "Election 2024")
- video_count: number of videos in this topic

Return a JSON object with a single key "topics" containing an array of {{"topic_name": "...", "video_count": N}}.
Sort by video_count descending. No markdown, raw JSON only."""

    resp = client.chat.completions.create(
        model=chat_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    text = _message_content_to_text(resp.choices[0].message.content)
    data = _parse_json(text)
    raw_topics = data.get("topics") or []
    if isinstance(raw_topics, dict):
        raw_topics = list(raw_topics.values()) if raw_topics else []
    if not isinstance(raw_topics, list):
        raw_topics = []
    # Normalize to list of plain dicts (primitives only)
    topics: list[dict[str, Any]] = []
    for t in raw_topics:
        if not isinstance(t, dict):
            continue
        topics.append({
            "topic_name": str(t.get("topic_name") or ""),
            "video_count": int(t.get("video_count")) if isinstance(t.get("video_count"), (int, float)) else 0,
        })
    return {"topics": topics}


def trend_estimate_strength(topic_name: str, videos: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Estimate how trending a topic is: EARLY | HEATING_UP | SATURATED.
    Returns: { "trend_strength": str, "confidence": "low"|"medium"|"high" }
    """
    client = _client_get()
    chat_model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o")

    prompt = f"""Topic: {topic_name}
Videos (sample): {json.dumps(videos[:15])}

Using repetition and velocity heuristics (how many videos, how recent, view patterns), estimate:
- trend_strength: one of EARLY (emerging), HEATING_UP (growing), SATURATED (peak/declining)
- confidence: one of low, medium, high

Return JSON: {{ "trend_strength": "...", "confidence": "..." }}. No markdown, raw JSON only."""

    resp = client.chat.completions.create(
        model=chat_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
    )
    text = _message_content_to_text(resp.choices[0].message.content)
    data = _parse_json(text)
    strength = (data.get("trend_strength") or "HEATING_UP")
    if isinstance(strength, str):
        strength = strength.upper()
    else:
        strength = "HEATING_UP"
    data["trend_strength"] = strength if strength in TREND_STRENGTHS else "HEATING_UP"
    data.setdefault("confidence", "medium")
    return data


# -----------------------------------------------------------------------------
# Step 4: Creator advice — why trending, who's winning, how to post, 5 hooks
# -----------------------------------------------------------------------------


def creator_advice_generator(topic_name: str, trend_strength: str) -> dict[str, Any]:
    """
    Generate why it's trending, who's winning, posting advice, and 5 short-form hooks.
    Returns: { why_trending, who_is_winning, posting_advice, hooks: [str] }
    """
    client = _client_get()
    chat_model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o")

    prompt = f"""Topic: {topic_name}
Trend strength: {trend_strength}

Generate creator-facing insights (speed and clarity over perfection):
1. why_trending: 1–2 sentences on why YouTube is promoting this topic.
2. who_is_winning: who is benefiting (channel size, format).
3. posting_advice: how the user should post about it (format, timing, angle).
4. hooks: exactly 5 short-form viral hooks (one line each), copyable.

Return JSON with keys: why_trending, who_is_winning, posting_advice, hooks (array of 5 strings).
No markdown, raw JSON only."""

    resp = client.chat.completions.create(
        model=chat_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    text = _message_content_to_text(resp.choices[0].message.content)
    data = _parse_json(text)
    hooks = data.get("hooks") or []
    if isinstance(hooks, str):
        hooks = [h.strip() for h in hooks.split("\n") if h.strip()][:5]
    else:
        # Normalize to list of strings (LLM sometimes returns [{"text": "..."}] or list of dicts)
        out_hooks: list[str] = []
        for h in hooks[:5]:
            if isinstance(h, str):
                out_hooks.append(h.strip())
            elif isinstance(h, dict):
                out_hooks.append((h.get("text") or h.get("hook") or str(h)).strip())
            else:
                out_hooks.append(str(h).strip())
        hooks = out_hooks
    data["hooks"] = hooks[:5]
    return data


# -----------------------------------------------------------------------------
# Pipeline — run all steps and return UI-shaped result
# -----------------------------------------------------------------------------


def run_full_pipeline(image_base64: str) -> dict[str, Any]:
    """
    Run the full flow: extract -> detect topics -> pick strongest -> estimate strength -> advice.
    Returns the final UI-shaped object: topic, trend_strength, why_trending, who_is_winning, how_to_post, hooks.
    """
    out = vision_extract_youtube_homepage(image_base64)
    videos = out["videos"]
    if not videos:
        return {
            "topic": "Unknown",
            "trend_strength": "HEATING_UP",
            "why_trending": "No videos detected in the screenshot.",
            "who_is_winning": "N/A",
            "how_to_post": "Upload a clearer YouTube homepage screenshot.",
            "hooks": [],
        }

    topics_out = trend_detect_topics(videos)
    topics = topics_out.get("topics") or []
    if isinstance(topics, dict):
        topics = list(topics.values()) if topics else []
    if not isinstance(topics, list):
        topics = []
    if not topics:
        topic_name = "General feed"
    else:
        first = topics[0]
        if isinstance(first, dict):
            topic_name = first.get("topic_name") or "General feed"
        elif isinstance(first, str):
            topic_name = first
        else:
            topic_name = "General feed"

    strength_out = trend_estimate_strength(topic_name, videos)
    trend_strength = strength_out.get("trend_strength") or "HEATING_UP"

    advice = creator_advice_generator(topic_name, trend_strength)

    hooks_out = advice.get("hooks") or []
    # Ensure hooks are always list of strings (never dicts)
    hooks_final: list[str] = []
    for h in hooks_out[:5]:
        if isinstance(h, str):
            hooks_final.append(h)
        elif isinstance(h, dict):
            hooks_final.append((h.get("text") or h.get("hook") or str(h)).strip())
        else:
            hooks_final.append(str(h).strip())

    return {
        "topic": topic_name,
        "trend_strength": trend_strength,
        "why_trending": advice.get("why_trending", ""),
        "who_is_winning": advice.get("who_is_winning", ""),
        "how_to_post": advice.get("posting_advice", ""),
        "hooks": hooks_final,
    }
