"""Edge-case coverage for the EPUB parser.

Builds tiny in-memory EPUBs (same pattern as conftest.py) and asserts the parser's
actual behavior: entity decoding, inline-tag flattening, <br> as a soft break,
paragraph/block splitting, title resolution order, empty-chapter skipping, and
global sentence-id contiguity.
"""

from __future__ import annotations

from pathlib import Path

from ebooklib import epub

from tandem_pipeline.epub_parser import parse_epub


def _chapter(file_name: str, title: str, body_html: str) -> epub.EpubHtml:
    c = epub.EpubHtml(title=title, file_name=file_name, lang="en")
    c.content = f"<html><body>{body_html}</body></html>"
    return c


def _build_epub(tmp_path: Path, chapters, toc=()) -> Path:
    book = epub.EpubBook()
    book.set_identifier("id-edge-test")
    book.set_title("Edge Book")
    book.set_language("en")
    book.add_author("Ada Tester")
    for c in chapters:
        book.add_item(c)
    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = list(chapters)
    out = tmp_path / "edge.epub"
    epub.write_epub(str(out), book)
    return out


def test_html_entities_are_decoded(tmp_path):
    c = _chapter(
        "c.xhtml",
        "C",
        "<p>Tom &amp; Jerry sailed. Cost 5&mdash;really. She said &#8220;hi&#8221;.</p>",
    )
    pb = parse_epub(_build_epub(tmp_path, [c]))
    joined = " ".join(s.text for s in pb.sentences)
    assert "Tom & Jerry sailed." in joined
    assert "5—really" in joined  # &mdash; -> em dash
    assert "“hi”" in joined  # curly quotes decoded
    # no raw entity markers survive
    assert "&amp;" not in joined and "&#8220;" not in joined


def test_nested_inline_tags_flattened_into_one_sentence(tmp_path):
    c = _chapter(
        "c.xhtml",
        "C",
        "<p>The <em>quick <strong>brown</strong></em> fox jumps.</p>",
    )
    pb = parse_epub(_build_epub(tmp_path, [c]))
    texts = [s.text for s in pb.sentences]
    assert "The quick brown fox jumps." in texts


def test_br_is_a_soft_break_and_does_not_split_the_sentence(tmp_path):
    # A single sentence whose only sentence-ending punctuation is the final period,
    # broken visually by <br>. The <br> must not create a sentence boundary.
    c = _chapter(
        "c.xhtml",
        "C",
        "<p>To be or not to be,<br/>that is the question.</p>",
    )
    pb = parse_epub(_build_epub(tmp_path, [c]))
    texts = [s.text for s in pb.sentences]
    assert "To be or not to be,that is the question." in texts
    # the fragment after the <br> is not emitted as its own sentence
    assert not any(t.startswith("that is the question") for t in texts)


def test_multiple_paragraphs_across_blocks_split_on_block_boundaries(tmp_path):
    c = _chapter(
        "c.xhtml",
        "C",
        "<div><p>First para here</p><p>Second para here</p></div><p>Third block</p>",
    )
    pb = parse_epub(_build_epub(tmp_path, [c]))
    texts = [s.text for s in pb.sentences]
    # Each block becomes its own sentence even without terminal punctuation,
    # because block elements force a newline that pysbd treats as a boundary.
    assert texts == ["First para here", "Second para here", "Third block"]


def test_toc_title_takes_precedence_over_heading(tmp_path):
    c = _chapter(
        "a.xhtml",
        "Ignored Doc Title",
        "<h1>Heading A</h1><p>Alpha one. Alpha two.</p>",
    )
    toc = (epub.Link("a.xhtml", "TOC Title A", "a"),)
    pb = parse_epub(_build_epub(tmp_path, [c], toc=toc))
    assert pb.chapters[0].title == "TOC Title A"


def test_first_heading_used_when_no_toc_entry(tmp_path):
    c = _chapter(
        "b.xhtml",
        "Ignored Doc Title",
        "<h2>Heading B</h2><p>Beta one.</p>",
    )
    pb = parse_epub(_build_epub(tmp_path, [c]))  # no toc
    assert pb.chapters[0].title == "Heading B"


def test_chapter_number_fallback_when_no_toc_or_heading(tmp_path):
    c1 = _chapter("a.xhtml", "A", "<p>Alpha one. Alpha two.</p>")  # no heading
    c2 = _chapter("b.xhtml", "B", "<p>Beta one.</p>")  # no heading
    pb = parse_epub(_build_epub(tmp_path, [c1, c2]))  # no toc
    # fallback numbers are 1-based on the produced-chapter index
    assert pb.chapters[0].title == "Chapter 1"
    assert pb.chapters[1].title == "Chapter 2"


def test_whitespace_only_chapter_skipped_with_warning(tmp_path):
    real = _chapter("real.xhtml", "Real", "<p>Something real here. And more.</p>")
    blank = _chapter("blank.xhtml", "Blank", "<p>   </p><div>\n\t</div>")
    pb = parse_epub(_build_epub(tmp_path, [real, blank]))
    assert len(pb.chapters) == 1
    assert any("blank.xhtml" in w and "no usable text" in w for w in pb.warnings)


def test_global_sentence_ids_are_contiguous_across_chapters(sample_epub):
    pb = parse_epub(sample_epub)
    # ids are a gapless 0..N-1 run in reading order, spanning all chapters
    assert [s.id for s in pb.sentences] == list(range(len(pb.sentences)))
    # chapter spans tile the id range with no gaps or overlaps
    assert pb.chapters[0].sentence_start_id == 0
    for prev, nxt in zip(pb.chapters, pb.chapters[1:]):
        assert nxt.sentence_start_id == prev.sentence_end_id + 1
    assert pb.chapters[-1].sentence_end_id == len(pb.sentences) - 1
    # every sentence's chapter_index matches the chapter whose span contains it
    for ch in pb.chapters:
        for sid in range(ch.sentence_start_id, ch.sentence_end_id + 1):
            assert pb.sentences[sid].chapter_index == ch.index
