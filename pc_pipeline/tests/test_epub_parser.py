from tandem_pipeline.epub_parser import parse_epub


def test_parses_metadata(sample_epub):
    pb = parse_epub(sample_epub)
    assert pb.meta.title == "Test Book"
    assert pb.meta.author == "Ada Tester"
    assert pb.meta.language == "en"
    assert pb.meta.source_epub == sample_epub.name


def test_splits_sentences_with_sequential_ids(sample_epub):
    pb = parse_epub(sample_epub)
    texts = [s.text for s in pb.sentences]
    assert "The cat sat on the mat." in texts
    assert "It was a warm day." in texts
    assert "Would it flood?" in texts
    # ids are the array index, in reading order
    assert [s.id for s in pb.sentences] == list(range(len(pb.sentences)))


def test_groups_sentences_into_chapters(sample_epub):
    pb = parse_epub(sample_epub)
    assert len(pb.chapters) == 2
    assert pb.chapters[0].title == "Chapter One"
    assert pb.chapters[1].title == "Chapter Two"
    # spans are contiguous and non-overlapping
    assert pb.chapters[0].sentence_start_id == 0
    assert pb.chapters[1].sentence_start_id == pb.chapters[0].sentence_end_id + 1


def test_skips_empty_chapter_with_warning(sample_epub):
    pb = parse_epub(sample_epub)
    assert any("no usable text" in w for w in pb.warnings)
    # the empty document did not produce a chapter
    assert all(c.title != "Empty" for c in pb.chapters)
