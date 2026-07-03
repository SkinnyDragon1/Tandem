from tandem_pipeline.models import (
    BookManifest,
    BookMeta,
    ChapterEntry,
    ChapterSpan,
    ParsedBook,
    Sentence,
    Timing,
    read_manifest,
    read_parsed_book,
    read_sentences,
    read_timings,
    write_manifest,
    write_parsed_book,
    write_sentences,
    write_timings,
    chapter_audio_name,
)


def test_chapter_audio_name_is_one_based_and_padded():
    assert chapter_audio_name(0, "wav") == "chapter_0001.wav"
    assert chapter_audio_name(41, ".opus") == "chapter_0042.opus"


def test_sentences_round_trip(tmp_path):
    sents = [Sentence(0, 0, "Hello world."), Sentence(1, 0, "Second sentence.")]
    p = tmp_path / "sentences.json"
    write_sentences(p, sents)
    assert read_sentences(p) == sents


def test_timings_round_trip(tmp_path):
    timings = [
        Timing(0, "audio/chapter_0001.wav", 0, 1200, "ok"),
        Timing(1, "audio/chapter_0001.wav", 1200, 3000, "low"),
    ]
    p = tmp_path / "timing.json"
    write_timings(p, timings)
    assert read_timings(p) == timings


def test_manifest_round_trip(tmp_path):
    manifest = BookManifest(
        book=BookMeta("T", "A", "en", "b.epub"),
        audio_format="wav",
        sample_rate=22050,
        chapters=[ChapterEntry(0, "Ch1", "audio/chapter_0001.wav", 0, 5)],
        sentence_count=6,
        warnings=["something"],
    )
    p = tmp_path / "manifest.json"
    write_manifest(p, manifest)
    got = read_manifest(p)
    assert got.book == manifest.book
    assert got.chapters == manifest.chapters
    assert got.sentence_count == 6
    assert got.schema_version == 1
    assert got.warnings == ["something"]


def test_parsed_book_round_trip(tmp_path):
    sents = [Sentence(0, 0, "A."), Sentence(1, 0, "B.")]
    parsed = ParsedBook(
        meta=BookMeta("T", "A", "en", "b.epub"),
        sentences=sents,
        chapters=[ChapterSpan(0, "Ch1", 0, 1)],
        warnings=["w"],
    )
    p = tmp_path / "parse.json"
    write_parsed_book(p, parsed)
    got = read_parsed_book(p, sents)
    assert got.meta == parsed.meta
    assert got.chapters == parsed.chapters
    assert got.warnings == ["w"]
