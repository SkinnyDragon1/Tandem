"""Stage 4 — package sentences, audio, timing map, and metadata into a bundle."""

from __future__ import annotations

import zipfile
from pathlib import Path

from .models import (
    AUDIO_DIRNAME,
    MANIFEST_FILENAME,
    SENTENCES_FILENAME,
    TIMING_FILENAME,
    BookManifest,
    ChapterEntry,
    ParsedBook,
    Timing,
    chapter_audio_name,
    write_manifest,
    write_sentences,
    write_timings,
)
from .tts_generator import AUDIO_EXT, ChapterAudio


def export_bundle(
    out_dir: Path,
    parsed: ParsedBook,
    chapter_audios: list[ChapterAudio],
    timings: list[Timing],
    extra_warnings: list[str] | None = None,
) -> BookManifest:
    """Write a complete bundle directory. Audio is expected under ``out_dir/audio``."""
    out_dir = Path(out_dir)
    (out_dir / AUDIO_DIRNAME).mkdir(parents=True, exist_ok=True)

    sample_rate = chapter_audios[0].sample_rate if chapter_audios else 22050

    chapter_entries = [
        ChapterEntry(
            index=span.index,
            title=span.title,
            audio=f"{AUDIO_DIRNAME}/{chapter_audio_name(span.index, AUDIO_EXT)}",
            sentence_start_id=span.sentence_start_id,
            sentence_end_id=span.sentence_end_id,
        )
        for span in parsed.chapters
    ]

    warnings = list(parsed.warnings) + list(extra_warnings or [])
    manifest = BookManifest(
        book=parsed.meta,
        audio_format=AUDIO_EXT,
        sample_rate=sample_rate,
        chapters=chapter_entries,
        sentence_count=len(parsed.sentences),
        warnings=warnings,
    )

    write_sentences(out_dir / SENTENCES_FILENAME, parsed.sentences)
    write_timings(out_dir / TIMING_FILENAME, timings)
    write_manifest(out_dir / MANIFEST_FILENAME, manifest)
    return manifest


def zip_bundle(bundle_dir: Path) -> Path:
    """Zip a bundle directory to ``<dir>.zip`` for transfer, excluding hidden work files."""
    bundle_dir = Path(bundle_dir)
    archive = bundle_dir.with_suffix(bundle_dir.suffix + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(bundle_dir.rglob("*")):
            rel = path.relative_to(bundle_dir)
            if any(part.startswith(".") for part in rel.parts):
                continue  # skip .work/ and other hidden entries
            if path.is_file():
                zf.write(path, rel.as_posix())
    return archive
