"""
TrendSignal — MCP server.

Exposes 4 tools (same steps as the pipeline):
  vision_extract_youtube_homepage → trend_detect_topics → trend_estimate_strength → creator_advice_generator

Run: python -m app.server  →  http://localhost:8000/mcp (streamable HTTP).
Add this URL in Cursor (or any MCP client) to call tools from chat.
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP

from app import analysis

mcp = FastMCP(
    "TrendSignal",
    instructions="Analyze YouTube homepage screenshots for trending topics and creator advice. Use vision_extract_youtube_homepage first, then trend_detect_topics, trend_estimate_strength, creator_advice_generator.",
    json_response=True,
    stateless_http=True,
)


@mcp.tool()
def vision_extract_youtube_homepage(image: str) -> dict:
    """
    Extract video metadata from a YouTube homepage screenshot.
    image: Base64-encoded image string or data URL (e.g. data:image/png;base64,...).
    Returns: { "videos": [ { "title", "creator", "views", "hours_since_posted", "emotional_tone" }, ... ] }
    """
    return analysis.vision_extract_youtube_homepage(image)


@mcp.tool()
def trend_detect_topics(videos: list[dict]) -> dict:
    """
    Group extracted videos into dominant trending topics.
    videos: Array of video objects from vision_extract_youtube_homepage.
    Returns: { "topics": [ { "topic_name": str, "video_count": int }, ... ] }
    """
    return analysis.trend_detect_topics(videos)


@mcp.tool()
def trend_estimate_strength(topic_name: str, videos: list[dict]) -> dict:
    """
    Estimate how trending a topic is using repetition and velocity heuristics.
    topic_name: Name of the topic. videos: Array of video objects.
    Returns: { "trend_strength": "EARLY"|"HEATING_UP"|"SATURATED", "confidence": "low"|"medium"|"high" }
    """
    return analysis.trend_estimate_strength(topic_name, videos)


@mcp.tool()
def creator_advice_generator(topic_name: str, trend_strength: str) -> dict:
    """
    Generate insights and posting advice for creators.
    topic_name: Name of the topic. trend_strength: EARLY, HEATING_UP, or SATURATED.
    Returns: { "why_trending", "who_is_winning", "posting_advice", "hooks": [5 strings] }
    """
    return analysis.creator_advice_generator(topic_name, trend_strength)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
