"""Stage 1 — extract plain text from an EPUB and split it into sentences.

Handles standard EPUB2/3. Preserves chapter structure (spine order), assigns each
sentence a global sequential id, and flags chapters that yield no usable text rather
than failing. DRM-protected EPUBs are out of scope.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pysbd
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# ebooklib emits noisy Future/UserWarnings about ignoring ncx/opf; silence them.
warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib.epub")
warnings.filterwarnings("ignore", category=FutureWarning, module="ebooklib.epub")
# EPUB documents are XHTML; the lxml HTML parser handles them fine, so quiet the hint.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

import ebooklib  # noqa: E402
from ebooklib import epub  # noqa: E402

from .models import BookMeta, ChapterSpan, ParsedBook, Sentence

_WS = re.compile(r"[ \t ]+")
_MULTINL = re.compile(r"\n{2,}")


def _clean_text(raw: str) -> str:
    """Collapse whitespace while keeping paragraph breaks as single newlines."""
    lines = [_WS.sub(" ", ln).strip() for ln in raw.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    return _MULTINL.sub("\n", text).strip()


def _html_to_text(html_bytes: bytes) -> str:
    soup = BeautifulSoup(html_bytes, "lxml")
    for tag in soup(["script", "style", "sup", "sub"]):
        tag.decompose()
    # Block elements should force line breaks so sentences don't run together.
    # (<br> is a soft in-sentence break, so it is intentionally excluded.)
    for tag in soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
        tag.append("\n")
    return _clean_text(soup.get_text())


def _first_heading(html_bytes: bytes) -> str | None:
    soup = BeautifulSoup(html_bytes, "lxml")
    for level in ("h1", "h2", "h3"):
        h = soup.find(level)
        if h and h.get_text(strip=True):
            return _WS.sub(" ", h.get_text(strip=True))
    return None


def _toc_title_map(book: epub.EpubBook) -> dict[str, str]:
    """Map document href (without anchor) -> TOC title, best effort."""
    titles: dict[str, str] = {}

    def walk(items):
        for entry in items:
            if isinstance(entry, tuple):
                section, children = entry
                walk([section])
                walk(children)
            elif isinstance(entry, epub.Link):
                href = entry.href.split("#", 1)[0]
                if href and entry.title:
                    titles.setdefault(href, entry.title.strip())

    try:
        walk(book.toc)
    except Exception:
        pass
    return titles


def _book_meta(book: epub.EpubBook, source: Path) -> BookMeta:
    def first(name: str, default: str) -> str:
        vals = book.get_metadata("DC", name)
        return vals[0][0].strip() if vals and vals[0][0] else default

    # Normalize to a 2-letter code (ISO 639-1); v1 targets English.
    lang3to1 = {"eng": "en"}
    lang = (first("language", "en") or "en").split("-")[0].lower()
    lang = lang3to1.get(lang, lang[:2])
    return BookMeta(
        title=first("title", source.stem),
        author=first("creator", "Unknown"),
        language=lang,
        source_epub=source.name,
    )


def parse_epub(epub_path: str | Path) -> ParsedBook:
    """Parse an EPUB into a :class:`ParsedBook` (meta, sentences, chapters, warnings)."""
    source = Path(epub_path)
    book = epub.read_epub(str(source))
    meta = _book_meta(book, source)
    toc_titles = _toc_title_map(book)
    segmenter = pysbd.Segmenter(language="en", clean=False)

    sentences: list[Sentence] = []
    chapters: list[ChapterSpan] = []
    warnings_out: list[str] = []
    chapter_index = 0

    # Spine order is the authoritative reading order.
    for spine_id, _ in book.spine:
        item = book.get_item_with_id(spine_id)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        name = item.get_name()
        content = item.get_content()
        text = _html_to_text(content)
        if not text.strip():
            warnings_out.append(f"chapter source '{name}': no usable text, skipped")
            continue

        raw_sents = [s.strip() for s in segmenter.segment(text) if s and s.strip()]
        if not raw_sents:
            warnings_out.append(f"chapter source '{name}': no sentences after split, skipped")
            continue

        title = (
            toc_titles.get(name)
            or _first_heading(content)
            or f"Chapter {chapter_index + 1}"
        )
        start_id = len(sentences)
        for s in raw_sents:
            sentences.append(Sentence(id=len(sentences), chapter_index=chapter_index, text=s))
        chapters.append(
            ChapterSpan(
                index=chapter_index,
                title=title,
                sentence_start_id=start_id,
                sentence_end_id=len(sentences) - 1,
            )
        )
        chapter_index += 1

    if not sentences:
        warnings_out.append("no usable text extracted from any chapter")
    return ParsedBook(meta=meta, sentences=sentences, chapters=chapters, warnings=warnings_out)
