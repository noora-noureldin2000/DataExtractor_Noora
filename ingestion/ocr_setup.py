import shutil
import subprocess
from dataclasses import dataclass

from config import settings
from utils.helpers import logger


@dataclass
class OcrPrerequisites:
    tesseract_path: str | None = None
    tesseract_version: str | None = None
    pytesseract_available: bool = False
    docling_ocr_engine: str = "unknown"
    ok: bool = False


def verify_ocr_prerequisites(tesseract_cmd: str | None = None) -> OcrPrerequisites:
    """Verify the local OCR stack and log how it is wired into the pipeline.

    Single source of truth: ``TESSERACT_CMD`` in config. Docling's PDF
    conversion is explicitly wired to ``TesseractOcrOptions`` (converter.py),
    and the figure OCR + scanned-page OCR paths call the same binary through
    pytesseract. This check runs at the start of every ingestion so a broken
    OCR setup is reported up front instead of failing silently mid-pipeline.
    """
    cmd = tesseract_cmd or settings.TESSERACT_CMD
    info = OcrPrerequisites()

    info.tesseract_path = shutil.which(cmd)
    if info.tesseract_path:
        try:
            proc = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            first_line = (proc.stdout or "").splitlines()
            info.tesseract_version = (
                first_line[0].strip() if first_line else "unknown version"
            )
        except Exception as e:
            logger.warning(f"Could not query Tesseract version: {e}")
    else:
        logger.warning(
            f"Tesseract binary '{cmd}' not found on PATH. "
            "Docling OCR, figure OCR and scanned-page OCR will fail. "
            "Install Tesseract (see README) or set TESSERACT_CMD in .env."
        )

    try:
        import pytesseract  # noqa: F401

        info.pytesseract_available = True
    except ImportError:
        logger.warning(
            "pytesseract is not installed (pip install -r requirements.txt). "
            "Figure OCR and scanned-page OCR will be skipped."
        )

    try:
        from docling.datamodel.pipeline_options import TesseractOcrOptions

        info.docling_ocr_engine = TesseractOcrOptions.__name__
    except ImportError:
        logger.warning("Could not confirm Docling's Tesseract OCR wiring.")

    info.ok = bool(info.tesseract_path and info.pytesseract_available)
    logger.info(
        "OCR prerequisites: "
        f"tesseract={info.tesseract_version or 'MISSING'} "
        f"({info.tesseract_path or 'not on PATH'}), "
        f"pytesseract={'yes' if info.pytesseract_available else 'no'}, "
        f"docling_ocr_engine={info.docling_ocr_engine}"
    )
    return info
