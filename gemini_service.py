import os
import re
import base64
import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = "gemini-2.0-flash-preview-image-generation"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)

BOTTLE_PROMPT = (
    "You are a professional product photographer. "
    "I will give you images of perfume bottles. "
    "Create a single clean composite product photo showing all the bottles grouped together, "
    "arranged neatly side by side. "
    "Pure white background. No text, no labels, no shadows, no reflections. "
    "Photorealistic, high quality, studio lighting."
)

BOX_PROMPT = (
    "You are a professional product photographer. "
    "I will give you images of perfume boxes. "
    "Create a single clean composite product photo showing all the boxes grouped together, "
    "arranged neatly side by side. "
    "Pure white background. No text, no labels, no shadows, no reflections. "
    "Photorealistic, high quality, studio lighting."
)


async def _fetch_image_as_base64(session: aiohttp.ClientSession, url: str) -> tuple[str, str]:
    """Download an image URL and return (base64_data, mime_type)."""
    async with session.get(url) as resp:
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        data = await resp.read()
        return base64.b64encode(data).decode("utf-8"), content_type


async def generate_bundle_image(image_urls: list[str], image_type: str) -> bytes:
    """
    Send product images to Gemini and get back a composed bundle image.
    image_type: 'bottles' or 'boxes'
    Returns raw image bytes (JPEG).
    """
    prompt = BOTTLE_PROMPT if image_type == "bottles" else BOX_PROMPT
    logger.info(f"Generating {image_type} image from {len(image_urls)} source images")

    async with aiohttp.ClientSession() as session:
        # Download all source images in parallel
        b64_images = await asyncio.gather(
            *[_fetch_image_as_base64(session, url) for url in image_urls]
        )

        # Build Gemini request parts: images first, then the text prompt
        parts = []
        for b64_data, mime_type in b64_images:
            parts.append({
                "inline_data": {
                    "mime_type": mime_type,
                    "data": b64_data,
                }
            })
        parts.append({"text": prompt})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"],
            },
        }

        async with session.post(GEMINI_URL, json=payload) as resp:
            resp.raise_for_status()
            result = await resp.json()

    # Extract the generated image from the response
    candidates = result.get("candidates", [])
    if not candidates:
        raise ValueError(f"Gemini returned no candidates for {image_type} image")

    for part in candidates[0].get("content", {}).get("parts", []):
        if "inline_data" in part:
            image_b64 = part["inline_data"]["data"]
            return base64.b64decode(image_b64)

    raise ValueError(f"Gemini response contained no image data for {image_type} image")
