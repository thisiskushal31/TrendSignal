"""
TrendSignal — Web API and upload UI.

  GET  /           → Upload UI (drag-drop screenshot, Analyze, copy hooks).
  POST /analyze    → Multipart image file → full pipeline → JSON insight.

Uses app.analysis.run_full_pipeline(); stateless; loads .env for OPENAI_API_KEY.
"""
import base64
import json
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from openai import APIError, RateLimitError

from app.analysis import run_full_pipeline

app = FastAPI(title="TrendSignal", description="Upload a YouTube homepage screenshot for AI trend analysis and creator hooks.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Avoid 404 when browser requests favicon."""
    return Response(status_code=204)


@app.get("/")
async def index():
    """Serve the upload UI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "TrendSignal API. POST /analyze with image file. Or add static/index.html for UI."}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """
    Accept a screenshot (image file), run full pipeline, return structured insight.
    Response: topic, trend_strength, why_trending, who_is_winning, how_to_post, hooks.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload an image file (e.g. PNG, JPEG).")
    try:
        body = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}") from e
    if not body:
        raise HTTPException(status_code=400, detail="Empty file.")
    b64 = base64.b64encode(body).decode("utf-8")
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not set.")
    try:
        result = run_full_pipeline(b64)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail="Model returned invalid JSON. Please try again (e.g. upload the screenshot again).",
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RateLimitError as e:
        msg = (
            "OpenAI quota or rate limit exceeded. Check your plan and billing: "
            "https://platform.openai.com/account/billing"
        )
        raise HTTPException(status_code=429, detail=msg) from e
    except APIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI API error: {getattr(e, 'message', str(e))}. See https://platform.openai.com/docs/guides/error-codes",
        ) from e
    except TypeError as e:
        if "unhashable type" in str(e):
            traceback.print_exc()
            raise HTTPException(
                status_code=502,
                detail="Analysis failed (internal error). Check server logs for traceback.",
            ) from e
        raise HTTPException(status_code=502, detail=f"Analysis failed: {e}") from e
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Analysis failed: {e}") from e
    return result


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()
