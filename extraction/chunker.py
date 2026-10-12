import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

HEADING_SPLIT_RE = re.compile(r"(?=^#{1,6}\s)", re.MULTILINE)
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")

DEFAULT_CHUNK_CHARS = 35000
DEFAULT_OVERLAP_CHARS = 2000


@dataclass
class Chunk:
    index: int
    total: int
    text: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    supplement: bool = False

    @property
    def context_label(self) -> str:
        label = f"{self.index} of {self.total}"
        if self.page_start is not None:
            if self.page_end is not None and self.page_end != self.page_start:
                label += f" (source pages {self.page_start}-{self.page_end})"
            else:
                label += f" (source page {self.page_start})"
        if self.supplement:
            label += " [scanned-page OCR supplement]"
        return label


def _split_blocks(text: str) -> list[str]:
    blocks = [b for b in HEADING_SPLIT_RE.split(text) if b and b.strip()]
    if blocks:
        return blocks
    stripped = text.strip()
    return [stripped] if stripped else []


def _tail_with_overlap(text: str, overlap_chars: int) -> str:
    if overlap_chars <= 0 or len(text) <= overlap_chars:
        return text
    tail = text[-overlap_chars:]
    newline = tail.find("\n")
    if newline != -1:
        tail = tail[newline + 1 :]
    return tail


def _split_long_block(
    block: str, target_chars: int, overlap_chars: int
) -> list[str]:
    parts = [p for p in PARAGRAPH_SPLIT_RE.split(block) if p and p.strip()]
    if not parts:
        return [block]

    if max(len(p) for p in parts) <= target_chars:
        chunks: list[str] = []
        current = ""
        for part in parts:
            if current and len(current) + len(part) > target_chars:
                chunks.append(current)
                current = _tail_with_overlap(current, overlap_chars)
            current += ("\n\n" if current else "") + part
        if current:
            chunks.append(current)
        return chunks

    chunks = []
    pos = 0
    while pos < len(block):
        end = min(pos + target_chars, len(block))
        if end < len(block):
            boundary = block.rfind("\n", pos + target_chars // 2, end)
            if boundary > pos:
                end = boundary
        chunks.append(block[pos:end].strip())
        if end >= len(block):
            break
        pos = max(end - overlap_chars, pos + 1)
    return [c for c in chunks if c]


def _pack_blocks(
    blocks: list[str], target_chars: int, overlap_chars: int
) -> list[str]:
    chunks: list[str] = []
    current = ""
    for block in blocks:
        if len(block) > target_chars:
            if current.strip():
                chunks.append(current)
            chunks.extend(_split_long_block(block, target_chars, overlap_chars))
            current = ""
            continue
        if current.strip() and len(current) + len(block) > target_chars:
            chunks.append(current)
            current = _tail_with_overlap(current, overlap_chars)
        current += ("\n\n" if current else "") + block
    if current.strip():
        chunks.append(current)
    return [c for c in chunks if c.strip()]


def build_chunks(
    doc_text: str,
    target_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    pagemap_path: Optional[str | Path] = None,
) -> list[Chunk]:
    """Split a document into overlapping chunks that always cover the full text.

    Docling markdown is split structurally at heading boundaries and packed to
    ~target_chars with overlap, so no part of the document is skipped. If a page
    map (from ingestion.page_mapper) is available, pages that required OCR are
    appended as page-labeled supplement chunks so scanned sections are covered
    even when their text was missed by the primary conversion.
    """
    chunks: list[dict] = [
        {"text": t, "page_start": None, "page_end": None, "supplement": False}
        for t in _pack_blocks(_split_blocks(doc_text), target_chars, overlap_chars)
    ]

    if pagemap_path is not None:
        from utils.helpers import load_json

        pagemap_path = Path(pagemap_path)
        if pagemap_path.exists():
            try:
                pagemap = load_json(pagemap_path)
                for page in pagemap.get("pages", []):
                    if not page.get("needs_ocr"):
                        continue
                    text = (page.get("text") or "").strip()
                    if not text:
                        continue
                    header = (
                        f"<!-- Scanned-page OCR supplement: page {page['page']} -->"
                    )
                    chunks.append(
                        {
                            "text": f"{header}\n\n{text}",
                            "page_start": page["page"],
                            "page_end": page["page"],
                            "supplement": True,
                        }
                    )
            except Exception as e:
                from utils.helpers import logger

                logger.warning(f"Could not read page map {pagemap_path}: {e}")

    total = len(chunks)
    return [
        Chunk(
            index=i + 1,
            total=total,
            text=c["text"],
            page_start=c["page_start"],
            page_end=c["page_end"],
            supplement=c["supplement"],
        )
        for i, c in enumerate(chunks)
    ]
