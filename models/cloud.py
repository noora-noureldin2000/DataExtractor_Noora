import base64
from pathlib import Path
from typing import Optional

from config import settings
from utils.helpers import logger


def _encode_image(image_path: str | Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def query_claude(
    prompt: str,
    image_paths: Optional[list[str | Path]] = None,
) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    content_blocks: list[dict] = [{"type": "text", "text": prompt}]

    if image_paths:
        for img_path in image_paths:
            b64 = _encode_image(img_path)
            media_type = _infer_media_type(img_path)
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64,
                },
            })

    logger.info(f"Querying Claude model: {settings.CLAUDE_MODEL}")
    response = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": content_blocks}],
    )
    return response.content[0].text


def query_gemini(
    prompt: str,
    image_paths: Optional[list[str | Path]] = None,
) -> str:
    from google import genai

    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    contents: list[str | Path] = [prompt]

    if image_paths:
        contents.extend(image_paths)

    logger.info(f"Querying Gemini model: {settings.GEMINI_MODEL}")
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=contents,
    )
    return response.text


def _infer_media_type(path: str | Path) -> str:
    ext = Path(path).suffix.lower()
    mapping = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mapping.get(ext, "image/png")
