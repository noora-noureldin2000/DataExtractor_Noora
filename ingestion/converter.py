from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TesseractOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRef

from config import settings
from utils.helpers import logger


class DoclingConverter:
    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")

        self.doc_name = self.pdf_path.stem
        self.markdown_dir = settings.MARKDOWN_DIR / self.doc_name
        self.images_dir = settings.IMAGES_DIR / self.doc_name
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

        pipeline_opts = PdfPipelineOptions(
            do_ocr=True,
            do_table_structure=True,
            table_structure_options={
                "do_cell_matching": True,
                "include_headers": True,
            },
        )
        pipeline_opts.ocr_options = TesseractOcrOptions(
            tesseract_cmd=settings.TESSERACT_CMD,
            lang="eng",
        )
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_opts,
                ),
            },
        )

    def convert(self) -> str:
        logger.info(f"Converting PDF: {self.pdf_path}")
        result = self.converter.convert(self.pdf_path)
        doc = result.document

        markdown_text = doc.export_to_markdown()
        image_map = self._extract_images(doc)
        markdown_text = self._rewrite_image_refs(markdown_text, image_map)

        md_path = self.markdown_dir / f"{self.doc_name}.md"
        md_path.write_text(markdown_text, encoding="utf-8")
        logger.info(f"Markdown saved: {md_path}")
        logger.info(f"Images extracted: {len(image_map)} to {self.images_dir}")
        return str(md_path)

    def _extract_images(self, doc) -> dict[str, str]:
        image_counter = 0
        image_map: dict[str, str] = {}
        for element, _level in doc.iterate_items():
            image_ref = getattr(element, "image", None)
            if image_ref is None or not image_ref.uri:
                continue
            try:
                pil_image = image_ref.get_image(doc)
                if pil_image is None:
                    continue
                image_counter += 1
                filename = f"fig_{image_counter:04d}.png"
                filepath = self.images_dir / filename
                pil_image.save(str(filepath))
                image_map[image_ref.uri] = (
                    f"../extracted_images/{self.doc_name}/{filename}"
                )
            except (IOError, OSError, ValueError) as e:
                logger.warning(f"Failed to extract image at element {element}: {e}")
        return image_map

    @staticmethod
    def _rewrite_image_refs(markdown: str, image_map: dict[str, str]) -> str:
        for original_uri, local_path in image_map.items():
            markdown = markdown.replace(original_uri, local_path)
        return markdown
