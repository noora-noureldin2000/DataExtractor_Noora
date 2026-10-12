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


def query_muse(
    prompt: str,
    image_paths: Optional[list[str | Path]] = None,
) -> str:
    """Query Muse Spark via the OpenCode Go subscription (Responses API)."""
    import httpx

    if not settings.OPENCODE_API_KEY:
        raise ValueError(
            "OPENCODE_API_KEY must be set (your OpenCode Go subscription key "
            "from the Zen console) to use the muse provider"
        )

    content: list[dict] = [{"type": "input_text", "text": prompt}]
    if image_paths:
        for img_path in image_paths:
            b64 = _encode_image(img_path)
            media_type = _infer_media_type(img_path)
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{media_type};base64,{b64}",
                }
            )

    base = settings.OPENCODE_API_BASE.rstrip("/")
    logger.info(
        f"Querying Muse model: {settings.OPENCODE_MODEL} via OpenCode Go"
    )
    with httpx.Client(timeout=600.0) as client:
        response = client.post(
            f"{base}/responses",
            headers={"Authorization": f"Bearer {settings.OPENCODE_API_KEY}"},
            json={
                "model": settings.OPENCODE_MODEL,
                "input": [{"role": "user", "content": content}],
                "max_output_tokens": 8192,
            },
        )
        response.raise_for_status()
        data = response.json()

    return _parse_responses_output(data)


def _parse_responses_output(data: dict) -> str:
    """Extract text from a Responses API payload (plus gateway fallbacks)."""
    texts: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                for part in item.get("content") or []:
                    if (
                        isinstance(part, dict)
                        and part.get("type") == "output_text"
                        and part.get("text")
                    ):
                        texts.append(part["text"])
            elif isinstance(item.get("text"), str) and item["text"]:
                texts.append(item["text"])
    if texts:
        return "".join(texts)
    if isinstance(data.get("output_text"), str) and data["output_text"]:
        return data["output_text"]
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content:
            return content
        if isinstance(content, list):
            joined = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
            if joined:
                return joined
    raise ValueError(f"Muse response contained no text output: {data}")


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
