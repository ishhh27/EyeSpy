# app.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional, Dict, Any
import io
from PIL import Image, ExifTags, UnidentifiedImageError
import pytesseract
import asyncio
import base64
import os
import random
from datetime import datetime
import logging

# Optional: let user set TESSERACT_CMD via environment (helpful on Windows)
if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eyespy-backend")

app = FastAPI(title="EYESPY OSINT Backend",
              description="A prototype API for image-based intelligence gathering.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production narrow this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>EYESPY Backend</title></head>
    <body>
      <h1>EYESPY Backend is Running!</h1>
      <p>See <a href="/docs">/docs</a> for API docs.</p>
    </body>
    </html>
    """

# ---------------- Helper functions ----------------
def safe_extract_exif(image: Image.Image) -> Dict[str, Any]:
    """Extract a few useful EXIF tags (robust)."""
    exif_data = {"DateTimeOriginal": None, "Make": None, "Model": None}
    try:
        raw_exif = image._getexif()
        if raw_exif:
            for tag, value in raw_exif.items():
                decoded = ExifTags.TAGS.get(tag, tag)
                if decoded in exif_data:
                    exif_data[decoded] = value
    except Exception as e:
        logger.debug("EXIF extraction failed", exc_info=e)
    # Normalise empty strings -> None
    for k, v in exif_data.items():
        if v in ("", "N/A"):
            exif_data[k] = None
    # Provide friendly fallback
    return exif_data

def run_ocr_safe(image: Image.Image) -> str:
    """Ensure image in RGB and run pytesseract, return cleaned text."""
    try:
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        text = pytesseract.image_to_string(image)
        text = text.strip()
        return text if text else "No text detected."
    except Exception as e:
        logger.error("OCR failed", exc_info=e)
        return "OCR processing failed."

def generate_mock_geolocation(exif_data: dict):
    """If EXIF has a DateTimeOriginal pretend to return a location (mock)."""
    if exif_data.get("DateTimeOriginal"):
        return {
            "latitude": "40.7128° N",
            "longitude": "74.0060° W",
            "location_name": "New York, NY"
        }
    return None

def generate_mock_results(image_base64: str):
    """Return 3-5 mock results resembling social platforms."""
    sources = [
        {"name": "Instagram", "icon": "fab fa-instagram"},
        {"name": "Twitter", "icon": "fab fa-twitter"},
        {"name": "Facebook", "icon": "fab fa-facebook"},
        {"name": "Pinterest", "icon": "fab fa-pinterest"},
        {"name": "Reddit", "icon": "fab fa-reddit"},
        {"name": "Flickr", "icon": "fab fa-flickr"},
    ]
    results = []
    num_results = random.randint(3, 5)
    for i in range(num_results):
        source = random.choice(sources)
        results.append({
            "source": source["name"],
            "source_icon": source["icon"],
            "title": f"Image from {source['name']} account",
            "caption": "Sample caption relevant to the image. #hackathon #osint",
            "url": f"https://www.{source['name'].lower()}.com/p/mock-id-{i}",
            "image": image_base64
        })
    return results

# ---------------- Main endpoint ----------------
@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    # Basic validation
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded.")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file is not an image.")

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")

        # Open image safely
        try:
            image = Image.open(io.BytesIO(contents))
        except UnidentifiedImageError:
            raise HTTPException(status_code=400, detail="Cannot identify image file. Corrupted or unsupported format.")
        except Exception as e:
            logger.exception("Unexpected error opening image")
            raise HTTPException(status_code=500, detail="Failed to open image.")

        # Ensure image is loaded (some PIL lazy-load)
        image.load()

        # Base64 used in mock web results / frontend preview
        image_base64 = base64.b64encode(contents).decode("utf-8")
        image_src = f"data:{file.content_type};base64,{image_base64}"

        # Stage 1: quick progress feedback simulation
        await asyncio.sleep(0.5)

        exif_data = safe_extract_exif(image)
        ocr_text = run_ocr_safe(image)

        # Stage 2: simulate web search
        await asyncio.sleep(1.0)
        web_results = generate_mock_results(image_src)

        # Stage 3: compile
        await asyncio.sleep(0.5)
        geolocation = generate_mock_geolocation(exif_data)

        # mock earliest appearance (string ISO)
        earliest_appearance = "2023-01-15T10:00:00Z"

        report = {
            "image_info": {
                "filename": file.filename,
                "file_size_kb": round(len(contents) / 1024, 2),
                "dimensions": f"{getattr(image, 'width', '?')}x{getattr(image, 'height', '?')} pixels",
                "file_type": image.format or file.content_type,
            },
            "exif_data": exif_data,
            "ocr_text": ocr_text,
            "advanced_insights": {
                "earliest_appearance": earliest_appearance,
                "geolocation": geolocation,
                "manipulation_detected": "No",  # mock
                "verification_summary": "Image has been found across multiple social platforms. Origin and spread verified."
            },
            "web_results": web_results,
            "processing_time_estimate_seconds": 2.0  # purely illustrative
        }

        return JSONResponse(content=report)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Analysis error")
        raise HTTPException(status_code=500, detail="Internal Server Error during analysis.")