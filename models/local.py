import base64
from pathlib import Path
from typing import Optional

import ollama

from config import settings
from utils.helpers import logger


def _encode_image(image_path: str | Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def query_ollama_vlm(
    prompt: str,
    image_paths: Optional[list[str | Path]] = None,
) -> str:
    messages = [{"role": "user", "content": prompt}]

    if image_paths:
        images_base64 = []
        for img_path in image_paths:
            b64 = _encode_image(img_path)
            images_base64.append(b64)

        messages[0]["images"] = images_base64

    logger.info(f"Querying Ollama model: {settings.OLLAMA_MODEL}")
    response = ollama.chat(
        model=settings.OLLAMA_MODEL,
        messages=messages,
        options={"temperature": 0.0},
    )

    return response["message"]["content"]
