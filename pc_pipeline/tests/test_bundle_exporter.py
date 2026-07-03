import wave
import zipfile

from tandem_pipeline.bundle_exporter import export_bundle, zip_bundle
from tandem_pipeline.models import (
    MANIFEST_FILENAME,
    SENTENCES_FILENAME,
    TIMING_FILENAME,
    BookMeta,
    ChapterSpan,
    ParsedBook,
    Sentence,
    Timing,
    read_manifest,
)
from tandem_pipeline.tts_generator import ChapterAudio, SentenceSpan


def _make_chapter_audio(tmp_path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    path = audio_dir / "chapter_0001.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 22050)  # 1s silence
    return ChapterAudio(
        chapter_index=0,
        audio_path=path,
        sample_rate=22050,
        spans=[SentenceSpan(0, 0, 500), SentenceSpan(1, 500, 1000)],
    )


def _parsed():
    return ParsedBook(
        meta=BookMeta("Book", "Author", "en", "book.epub"),
        sentences=[Sentence(0, 0, "First."), Sentence(1, 0, "Second.")],
        chapters=[ChapterSpan(0, "Chapter One", 0, 1)],
        warnings=["parse warning"],
    )


def test_export_writes_bundle_contract(tmp_path):
    ca = _make_chapter_audio(tmp_path)
    timings = [
        Timing(0, "audio/chapter_0001.wav", 0, 500, "ok"),
        Timing(1, "audio/chapter_0001.wav", 500, 1000, "ok"),
    ]
    export_bundle(tmp_path, _parsed(), [ca], timings, extra_warnings=["align warning"])

    assert (tmp_path / MANIFEST_FILENAME).exists()
    assert (tmp_path / SENTENCES_FILENAME).exists()
    assert (tmp_path / TIMING_FILENAME).exists()
    assert (tmp_path / "audio" / "chapter_0001.wav").exists()

    manifest = read_manifest(tmp_path / MANIFEST_FILENAME)
    assert manifest.sentence_count == 2
    assert manifest.chapters[0].audio == "audio/chapter_0001.wav"
    # warnings from both parse and align stages are preserved
    assert "parse warning" in manifest.warnings
    assert "align warning" in manifest.warnings


def test_zip_excludes_hidden_work_files(tmp_path):
    ca = _make_chapter_audio(tmp_path)
    export_bundle(tmp_path, _parsed(), [ca], [], extra_warnings=[])
    work = tmp_path / ".work"
    work.mkdir(exist_ok=True)
    (work / "chapters.json").write_text("[]")

    archive = zip_bundle(tmp_path)
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
    assert "manifest.json" in names
    assert "audio/chapter_0001.wav" in names
    assert not any(n.startswith(".work") for n in names)
