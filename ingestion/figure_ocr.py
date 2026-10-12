from pathlib import Path

from PIL import Image, ImageOps
import pytesseract

from config import settings
from utils.helpers import logger, save_json

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}

_PSM_CONFIGS = [
    "--oem 3 --psm 6",
    "--oem 3 --psm 11",
    "--oem 3 --psm 3",
]


def _configure_tesseract() -> None:
    if settings.TESSERACT_CMD and settings.TESSERACT_CMD != "tesseract":
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


def _preprocess(image_path: Path, scale: int = 2) -> Image.Image:
    img = Image.open(image_path).convert("L")
    img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    return img


def ocr_figure(image_path: str | Path) -> str:
    _configure_tesseract()
    path = Path(image_path)

    candidates: list[str] = []
    variants: list[Image.Image | str] = [str(path)]
    try:
        variants.append(_preprocess(path))
    except (IOError, OSError, ValueError) as e:
        logger.warning(f"Could not preprocess figure {path.name}: {e}")

    for variant in variants:
        for config in _PSM_CONFIGS:
            try:
                text = pytesseract.image_to_string(variant, config=config)
                if text and text.strip():
                    candidates.append(text.strip())
            except Exception as e:
                logger.debug(f"OCR pass failed for {path.name} ({config}): {e}")

    if not candidates:
        return ""

    best = max(candidates, key=lambda t: len(t))
    return best


def run_figure_ocr(images_dir: str | Path, study_name: str) -> Path | None:
    images_dir = Path(images_dir)
    if not images_dir.exists():
        logger.warning(f"Images directory not found: {images_dir}")
        return None

    figure_files = sorted(
        f for f in images_dir.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not figure_files:
        logger.info(f"No figure images found in {images_dir}")
        return None

    logger.info(f"Running dedicated figure OCR on {len(figure_files)} images...")
    results: dict[str, str] = {}
    for fig in figure_files:
        try:
            text = ocr_figure(fig)
        except Exception as e:
            logger.warning(f"Figure OCR failed for {fig.name}: {e}")
            continue
        if text:
            results[fig.name] = text
            txt_path = fig.with_suffix(".ocr.txt")
            txt_path.write_text(text, encoding="utf-8")

    out_path = images_dir / f"{study_name}_figure_ocr.json"
    if results:
        save_json(results, out_path)
        logger.info(
            f"Figure OCR complete: {len(results)}/{len(figure_files)} figures yielded text -> {out_path}"
        )
        return out_path

    logger.info("Figure OCR yielded no text (figures may be purely graphical)")
    return None
