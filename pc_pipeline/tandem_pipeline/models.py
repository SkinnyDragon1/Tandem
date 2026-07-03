"""Shared data models and the export-bundle contract.

This module is the single source of truth for the bundle format that connects the
PC pipeline (writer) and the Android app (reader). Every stage produces or consumes
these types, and the JSON they serialize to is documented in docs/bundle-format.md.

A bundle is a directory laid out as::

    <book>.tandem/
    ├── manifest.json      # BookManifest: schema version, metadata, chapter table
    ├── sentences.json     # list[Sentence]: ordered global sentence index
    ├── timing.json        # list[Timing]: sentence_id -> audio file + ms offsets
    └── audio/
        ├── chapter_0001.<ext>
        └── ...
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1

MANIFEST_FILENAME = "manifest.json"
SENTENCES_FILENAME = "sentences.json"
TIMING_FILENAME = "timing.json"
AUDIO_DIRNAME = "audio"


def chapter_audio_name(chapter_index: int, ext: str) -> str:
    """Deterministic audio filename for a chapter, e.g. ``chapter_0001.wav``."""
    return f"chapter_{chapter_index + 1:04d}.{ext.lstrip('.')}"


@dataclass(frozen=True)
class Sentence:
    """One sentence of book text with a globally unique, sequential id.

    ``id`` is the global reading order (0-based). ``chapter_index`` groups sentences
    into chapters. The Android position matcher fuzzy-matches on-screen text against
    ``text`` to recover ``id``.
    """

    id: int
    chapter_index: int
    text: str


@dataclass(frozen=True)
class Timing:
    """Playback location for one sentence within a chapter audio file."""

    sentence_id: int
    audio: str  # bundle-relative path, e.g. "audio/chapter_0001.wav"
    start_ms: int
    end_ms: int
    confidence: str = "ok"  # "ok" | "low"  (low = alignment was uncertain here)


@dataclass(frozen=True)
class ChapterEntry:
    """A chapter's row in the manifest: its audio file and sentence-id span."""

    index: int
    title: str
    audio: str
    sentence_start_id: int  # inclusive
    sentence_end_id: int  # inclusive


@dataclass(frozen=True)
class BookMeta:
    title: str
    author: str
    language: str
    source_epub: str


@dataclass(frozen=True)
class ChapterSpan:
    """A chapter as produced by the parser, before audio exists.

    Becomes a :class:`ChapterEntry` once the TTS stage assigns an audio file.
    """

    index: int
    title: str
    sentence_start_id: int  # inclusive
    sentence_end_id: int  # inclusive


@dataclass
class ParsedBook:
    """Full output of the parse stage: everything except audio and timing."""

    meta: BookMeta
    sentences: list[Sentence]
    chapters: list[ChapterSpan]
    warnings: list[str] = field(default_factory=list)


@dataclass
class BookManifest:
    book: BookMeta
    audio_format: str  # "wav" | "opus"
    sample_rate: int
    chapters: list[ChapterEntry]
    sentence_count: int
    warnings: list[str] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION


# --- serialization helpers -------------------------------------------------

def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_sentences(path: Path, sentences: list[Sentence]) -> None:
    _write_json(path, [asdict(s) for s in sentences])


def read_sentences(path: Path) -> list[Sentence]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Sentence(**d) for d in data]


def write_timings(path: Path, timings: list[Timing]) -> None:
    _write_json(path, [asdict(t) for t in timings])


def read_timings(path: Path) -> list[Timing]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Timing(**d) for d in data]


def write_parsed_book(path: Path, parsed: ParsedBook) -> None:
    """Persist parser output so later stages can run independently."""
    _write_json(
        path,
        {
            "book": asdict(parsed.meta),
            "chapters": [asdict(c) for c in parsed.chapters],
            "warnings": parsed.warnings,
        },
    )


def read_parsed_book(path: Path, sentences: list[Sentence]) -> ParsedBook:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return ParsedBook(
        meta=BookMeta(**d["book"]),
        sentences=sentences,
        chapters=[ChapterSpan(**c) for c in d["chapters"]],
        warnings=d.get("warnings", []),
    )


def write_manifest(path: Path, manifest: BookManifest) -> None:
    obj = {
        "schema_version": manifest.schema_version,
        "book": asdict(manifest.book),
        "audio": {"format": manifest.audio_format, "sample_rate": manifest.sample_rate},
        "chapters": [asdict(c) for c in manifest.chapters],
        "sentence_count": manifest.sentence_count,
        "warnings": manifest.warnings,
    }
    _write_json(path, obj)


def read_manifest(path: Path) -> BookManifest:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return BookManifest(
        book=BookMeta(**d["book"]),
        audio_format=d["audio"]["format"],
        sample_rate=d["audio"]["sample_rate"],
        chapters=[ChapterEntry(**c) for c in d["chapters"]],
        sentence_count=d["sentence_count"],
        warnings=d.get("warnings", []),
        schema_version=d.get("schema_version", SCHEMA_VERSION),
    )
