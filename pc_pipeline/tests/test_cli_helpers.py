from tandem_pipeline.cli import _read_chapters, _truncate, _write_chapters
from tandem_pipeline.models import BookMeta, ChapterSpan, ParsedBook, Sentence
from tandem_pipeline.tts_generator import ChapterAudio, SentenceSpan
from pathlib import Path


def _sample_parsed() -> ParsedBook:
    """Three chapters of two sentences each; ids 0..5 in reading order."""
    sents = [
        Sentence(0, 0, "a."),
        Sentence(1, 0, "b."),
        Sentence(2, 1, "c."),
        Sentence(3, 1, "d."),
        Sentence(4, 2, "e."),
        Sentence(5, 2, "f."),
    ]
    chapters = [
        ChapterSpan(0, "Ch0", 0, 1),
        ChapterSpan(1, "Ch1", 2, 3),
        ChapterSpan(2, "Ch2", 4, 5),
    ]
    return ParsedBook(
        meta=BookMeta("T", "A", "en", "b.epub"),
        sentences=sents,
        chapters=chapters,
        warnings=["w1"],
    )


def test_truncate_keeps_first_n_sentences():
    got = _truncate(_sample_parsed(), 3)
    assert [s.id for s in got.sentences] == [0, 1, 2]


def test_truncate_adjusts_partial_chapter_end():
    # cutoff at 3 keeps ids {0,1,2}: Ch1 loses id 3, so its end shrinks 3 -> 2.
    got = _truncate(_sample_parsed(), 3)
    assert got.chapters == [
        ChapterSpan(0, "Ch0", 0, 1),
        ChapterSpan(1, "Ch1", 2, 2),
    ]


def test_truncate_drops_chapters_with_no_kept_sentences():
    got = _truncate(_sample_parsed(), 3)
    # Ch2 (ids 4,5) is fully past the cutoff and dropped entirely.
    assert [c.index for c in got.chapters] == [0, 1]


def test_truncate_preserves_meta_and_warnings():
    parsed = _sample_parsed()
    got = _truncate(parsed, 2)
    assert got.meta == parsed.meta
    assert got.warnings == ["w1"]


def test_truncate_whole_first_chapter_only():
    got = _truncate(_sample_parsed(), 2)
    assert [s.id for s in got.sentences] == [0, 1]
    assert got.chapters == [ChapterSpan(0, "Ch0", 0, 1)]


def test_truncate_more_than_available_is_noop():
    parsed = _sample_parsed()
    got = _truncate(parsed, 100)
    assert [s.id for s in got.sentences] == [0, 1, 2, 3, 4, 5]
    assert got.chapters == parsed.chapters


def test_chapters_round_trip(tmp_path):
    chapters = [
        ChapterAudio(
            chapter_index=0,
            audio_path=Path("audio/chapter_0001.wav"),
            sample_rate=22050,
            spans=[
                SentenceSpan(0, 0, 1200),
                SentenceSpan(1, 1200, 3000),
            ],
        ),
        ChapterAudio(
            chapter_index=1,
            audio_path=Path("audio/chapter_0002.wav"),
            sample_rate=22050,
            spans=[SentenceSpan(2, 0, 900)],
        ),
    ]
    p = tmp_path / "chapters.json"
    _write_chapters(p, chapters)
    assert _read_chapters(p) == chapters


def test_chapters_round_trip_preserves_span_fields(tmp_path):
    chapters = [
        ChapterAudio(
            chapter_index=3,
            audio_path=Path("audio/chapter_0004.wav"),
            sample_rate=16000,
            spans=[SentenceSpan(sentence_id=7, start_ms=500, end_ms=2500)],
        )
    ]
    p = tmp_path / "chapters.json"
    _write_chapters(p, chapters)
    got = _read_chapters(p)
    span = got[0].spans[0]
    assert (span.sentence_id, span.start_ms, span.end_ms) == (7, 500, 2500)
    assert got[0].sample_rate == 16000
    assert got[0].audio_path == Path("audio/chapter_0004.wav")


def test_chapters_round_trip_empty_spans(tmp_path):
    chapters = [
        ChapterAudio(chapter_index=0, audio_path=Path("audio/chapter_0001.wav"), sample_rate=22050, spans=[])
    ]
    p = tmp_path / "chapters.json"
    _write_chapters(p, chapters)
    assert _read_chapters(p) == chapters
