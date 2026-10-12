import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Settings:
    VISION_MODE: str = os.getenv("VISION_MODE", "local")

    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5vl:3b")
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-pro-exp-03-25")

    OPENCODE_API_KEY: str = os.getenv("OPENCODE_API_KEY", "") or os.getenv(
        "OPENCODE_GO_API_KEY", ""
    )
    OPENCODE_API_BASE: str = os.getenv(
        "OPENCODE_API_BASE", "https://opencode.ai/zen/go/v1"
    )
    OPENCODE_MODEL: str = os.getenv("OPENCODE_MODEL", "muse-spark-1.3-contributor")

    CLOUD_PROVIDER: str = os.getenv("CLOUD_PROVIDER", "anthropic")

    DEFAULT_CORR: float = float(os.getenv("DEFAULT_CORR", "0.5"))

    BASE_DIR: Path = Path(__file__).parent
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "output")))
    MARKDOWN_DIR: Path = Path(os.getenv("MARKDOWN_DIR", str(OUTPUT_DIR / "markdown")))
    IMAGES_DIR: Path = Path(os.getenv("IMAGES_DIR", str(OUTPUT_DIR / "extracted_images")))
    RESULTS_DIR: Path = Path(os.getenv("RESULTS_DIR", str(OUTPUT_DIR / "results")))

    TESSERACT_CMD: str = os.getenv("TESSERACT_CMD", "tesseract")

    TEMPLATE_PATH: Optional[Path] = (
        Path(os.getenv("TEMPLATE_PATH")) if os.getenv("TEMPLATE_PATH") else None
    )

    def __init__(self):
        for d in [self.MARKDOWN_DIR, self.IMAGES_DIR, self.RESULTS_DIR]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
