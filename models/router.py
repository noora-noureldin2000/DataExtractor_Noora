from enum import Enum
from pathlib import Path
from typing import Optional

from config import settings
from models.exceptions import ModelQueryError
from utils.helpers import logger


class ModelBackend(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class CloudProvider(str, Enum):
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


def get_available_backends() -> list[ModelBackend]:
    backends = [ModelBackend.LOCAL]
    if settings.ANTHROPIC_API_KEY or settings.GOOGLE_API_KEY:
        backends.append(ModelBackend.CLOUD)
    return backends


def query_vision_model(
    prompt: str,
    image_paths: Optional[list[str | Path]] = None,
    backend: Optional[ModelBackend] = None,
) -> str:
    if backend is None:
        backend = ModelBackend(settings.VISION_MODE)

    if backend == ModelBackend.LOCAL:
        return _query_local(prompt, image_paths)
    return _query_cloud(prompt, image_paths)


def _query_local(prompt: str, image_paths: Optional[list[str | Path]]) -> str:
    from models.local import query_ollama_vlm

    try:
        return query_ollama_vlm(prompt, image_paths)
    except Exception as e:
        logger.error(f"Local model query failed: {e}")
        raise ModelQueryError(str(e)) from e


def _query_cloud(prompt: str, image_paths: Optional[list[str | Path]]) -> str:
    provider = CloudProvider(settings.CLOUD_PROVIDER)
    from models.cloud import query_claude, query_gemini

    try:
        if provider == CloudProvider.ANTHROPIC:
            return query_claude(prompt, image_paths)
        return query_gemini(prompt, image_paths)
    except Exception as e:
        logger.error(f"Cloud model ({provider.value}) query failed: {e}")
        raise ModelQueryError(str(e)) from e
