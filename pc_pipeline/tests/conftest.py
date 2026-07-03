"""Shared test fixtures: build minimal in-memory EPUBs so parser tests are fast."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore")

from ebooklib import epub


def _chapter(file_name: str, title: str, body_html: str) -> epub.EpubHtml:
    c = epub.EpubHtml(title=title, file_name=file_name, lang="en")
    c.content = f"<html><body>{body_html}</body></html>"
    return c


@pytest.fixture
def sample_epub(tmp_path: Path) -> Path:
    """A 3-document EPUB: two real chapters and one whitespace-only chapter."""
    book = epub.EpubBook()
    book.set_identifier("id-tandem-test")
    book.set_title("Test Book")
    book.set_language("en")
    book.add_author("Ada Tester")

    c1 = _chapter(
        "chap_01.xhtml",
        "Chapter One",
        "<h1>Chapter One</h1><p>The cat sat on the mat. It was a warm day.</p>",
    )
    c2 = _chapter(
        "chap_02.xhtml",
        "Chapter Two",
        "<p>Rain fell all night. The river rose quickly! Would it flood?</p>",
    )
    empty = _chapter("empty.xhtml", "Empty", "<p>   </p>")

    for c in (c1, c2, empty):
        book.add_item(c)
    book.toc = (
        epub.Link("chap_01.xhtml", "Chapter One", "c1"),
        epub.Link("chap_02.xhtml", "Chapter Two", "c2"),
    )
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [c1, c2, empty]

    out = tmp_path / "test.epub"
    epub.write_epub(str(out), book)
    return out
