import io
from pathlib import Path
from typing import Optional

from config import settings
from utils.helpers import logger, save_json

SCANNED_PAGE_TEXT_THRESHOLD = 30
OCR_RENDER_DPI = 300


class PageMapper:
    """Builds a per-page text map of a PDF.

    Priority: pdf-inspector (fast Rust classification + per-page markdown with
    needs_ocr flags), falling back to PyMuPDF's text layer. Pages flagged as
    scanned/image-only are rendered at high DPI and OCRed with Tesseract so
    text embedded in scanned sections is captured.
    """

    def __init__(self, pdf_path: str | Path, output_dir: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.out_path = self.output_dir / f"{self.pdf_path.stem}_pagemap.json"

    def build(self) -> Path:
        pdf_type = "unknown"
        confidence = None
        pages: Optional[list[dict]] = None
        engine = "none"

        pages_pi, pdf_type, confidence = self._pages_via_pdf_inspector()
        if pages_pi is not None:
            pages, engine = pages_pi, "pdf-inspector"
        else:
            pages_pymupdf = self._pages_via_pymupdf()
            if pages_pymupdf is not None:
                pages, engine = pages_pymupdf, "pymupdf"

        if pages is None:
            logger.warning(
                "Page mapping unavailable (neither pdf-inspector nor PyMuPDF "
                "usable); extraction will rely on Docling markdown alone."
            )
            raise RuntimeError("No page-text engine available")

        needs_ocr = [p for p in pages if p["needs_ocr"]]
        logger.info(
            f"Page map: {len(pages)} pages via {engine} "
            f"(pdf_type={pdf_type}, confidence={confidence}, "
            f"{len(needs_ocr)} pages need OCR)"
        )

        for page in needs_ocr:
            ocr_text = self._ocr_page(page["page"])
            if ocr_text:
                page["text"] = ocr_text
                page["ocr_applied"] = True
            else:
                page["ocr_applied"] = False

        save_json(
            {
                "pdf_type": pdf_type,
                "confidence": confidence,
                "engine": engine,
                "page_count": len(pages),
                "pages": pages,
            },
            self.out_path,
        )
        logger.info(f"Page map saved: {self.out_path}")
        return self.out_path

    def _pages_via_pdf_inspector(
        self,
    ) -> tuple[Optional[list[dict]], str, Optional[float]]:
        try:
            import pdf_inspector
        except ImportError:
            logger.info("pdf-inspector not installed; using PyMuPDF fallback")
            return None, "unknown", None

        try:
            pdf_type, confidence = "unknown", None
            try:
                classification = pdf_inspector.classify_pdf(str(self.pdf_path))
                pdf_type = classification.pdf_type
                confidence = classification.confidence
            except Exception as e:
                logger.debug(f"pdf-inspector classify_pdf failed: {e}")

            result = pdf_inspector.extract_pages_markdown(str(self.pdf_path))
            pages = [
                {
                    "page": pm.page + 1,
                    "needs_ocr": bool(pm.needs_ocr),
                    "source": "pdf-inspector",
                    "text": "" if pm.needs_ocr else (pm.markdown or ""),
                }
                for pm in result.pages
            ]
            return pages, pdf_type, confidence
        except Exception as e:
            logger.warning(f"pdf-inspector page extraction failed: {e}")
            return None, "unknown", None

    def _pages_via_pymupdf(self) -> Optional[list[dict]]:
        try:
            import fitz
        except ImportError:
            logger.warning("PyMuPDF not installed; page mapping disabled")
            return None

        try:
            doc = fitz.open(str(self.pdf_path))
            pages = []
            for i, page in enumerate(doc):
                text = page.get_text().strip()
                needs_ocr = len(text) < SCANNED_PAGE_TEXT_THRESHOLD
                pages.append(
                    {
                        "page": i + 1,
                        "needs_ocr": needs_ocr,
                        "source": "pymupdf",
                        "text": "" if needs_ocr else text,
                    }
                )
            doc.close()
            return pages
        except Exception as e:
            logger.warning(f"PyMuPDF page mapping failed: {e}")
            return None

    def _ocr_page(self, page_number: int) -> str:
        try:
            import fitz
            import pytesseract
            from PIL import Image
        except ImportError as e:
            logger.warning(f"Scanned-page OCR skipped (missing dependency): {e}")
            return ""

        if settings.TESSERACT_CMD and settings.TESSERACT_CMD != "tesseract":
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

        try:
            doc = fitz.open(str(self.pdf_path))
            page = doc[page_number - 1]
            pix = page.get_pixmap(dpi=OCR_RENDER_DPI)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            doc.close()
            text = pytesseract.image_to_string(img, config="--oem 3 --psm 3")
            return text.strip()
        except Exception as e:
            logger.warning(f"OCR failed for page {page_number}: {e}")
            return ""
