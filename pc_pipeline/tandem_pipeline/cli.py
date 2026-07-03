"""``tandem`` command line — orchestrates parse -> tts -> align -> bundle.

The full pipeline is ``tandem build book.epub --out ./book.tandem``. Each stage can
also be run on its own against a work directory (the same directory that becomes the
bundle) for debugging: ``parse``, ``tts``, ``align``, ``bundle``.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from . import epub_parser
from .aligner import align_chapters, load_align_model
from .bundle_exporter import export_bundle, zip_bundle
from .models import (
    SENTENCES_FILENAME,
    Sentence,
    read_parsed_book,
    read_sentences,
    read_timings,
    write_parsed_book,
    write_sentences,
)
from .tts_generator import (
    DEFAULT_VOICE,
    ChapterAudio,
    SentenceSpan,
    load_voice,
    synthesize_chapter,
)

# Intermediates live under .work/ so they never ship inside the bundle.
PARSE_FILE = ".work/parse.json"
CHAPTERS_FILE = ".work/chapters.json"
DEFAULT_MODELS = str(Path(__file__).resolve().parent.parent / "models")


# --- intermediate serialization for the tts -> align handoff ---------------

def _write_chapters(path: Path, chapters: list[ChapterAudio]) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "chapter_index": c.chapter_index,
                    "audio_path": str(c.audio_path),
                    "sample_rate": c.sample_rate,
                    "spans": [
                        {"sentence_id": s.sentence_id, "start_ms": s.start_ms, "end_ms": s.end_ms}
                        for s in c.spans
                    ],
                }
                for c in chapters
            ],
            indent=2,
        ),
        encoding="utf-8",
    )


def _read_chapters(path: Path) -> list[ChapterAudio]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        ChapterAudio(
            chapter_index=c["chapter_index"],
            audio_path=Path(c["audio_path"]),
            sample_rate=c["sample_rate"],
            spans=[SentenceSpan(**s) for s in c["spans"]],
        )
        for c in data
    ]


# --- stage helpers (shared by `build` and the standalone subcommands) -------

def _run_parse(epub_path: Path, workdir: Path, max_sentences: int | None) -> None:
    parsed = epub_parser.parse_epub(epub_path)
    if max_sentences is not None:
        parsed = _truncate(parsed, max_sentences)
    (workdir / ".work").mkdir(parents=True, exist_ok=True)
    write_sentences(workdir / SENTENCES_FILENAME, parsed.sentences)
    write_parsed_book(workdir / PARSE_FILE, parsed)
    click.echo(
        f"  parsed: {len(parsed.chapters)} chapters, {len(parsed.sentences)} sentences"
        + (f", {len(parsed.warnings)} warning(s)" if parsed.warnings else "")
    )


def _truncate(parsed, max_sentences: int):
    """Keep only the first ``max_sentences`` sentences (and affected chapters)."""
    from .models import ChapterSpan, ParsedBook

    sents = parsed.sentences[:max_sentences]
    keep_ids = {s.id for s in sents}
    chapters = []
    for c in parsed.chapters:
        ids = [i for i in range(c.sentence_start_id, c.sentence_end_id + 1) if i in keep_ids]
        if ids:
            chapters.append(ChapterSpan(c.index, c.title, ids[0], ids[-1]))
    return ParsedBook(parsed.meta, sents, chapters, parsed.warnings)


def _run_tts(workdir: Path, models_dir: str, voice_name: str) -> None:
    sentences = read_sentences(workdir / SENTENCES_FILENAME)
    parsed = read_parsed_book(workdir / PARSE_FILE, sentences)
    by_id = {s.id: s for s in sentences}
    voice = load_voice(models_dir, voice_name)

    chapters: list[ChapterAudio] = []
    with click.progressbar(parsed.chapters, label="  synthesizing") as bar:
        for span in bar:
            ch_sents = [by_id[i] for i in range(span.sentence_start_id, span.sentence_end_id + 1)]
            chapters.append(synthesize_chapter(voice, span.index, ch_sents, workdir / "audio"))
    (workdir / ".work").mkdir(parents=True, exist_ok=True)
    _write_chapters(workdir / CHAPTERS_FILE, chapters)


def _run_align(workdir: Path) -> list[str]:
    sentences = read_sentences(workdir / SENTENCES_FILENAME)
    chapters = _read_chapters(workdir / CHAPTERS_FILE)
    click.echo("  loading alignment model...")
    model = load_align_model("en", "cpu")
    timings, warns = align_chapters(chapters, sentences, model)
    from .models import TIMING_FILENAME, write_timings

    write_timings(workdir / TIMING_FILENAME, timings)
    click.echo(f"  aligned: {len(timings)} sentences" + (f", {len(warns)} warning(s)" if warns else ""))
    return warns


def _run_bundle(workdir: Path, do_zip: bool, extra_warnings: list[str]) -> None:
    from .models import TIMING_FILENAME

    sentences = read_sentences(workdir / SENTENCES_FILENAME)
    parsed = read_parsed_book(workdir / PARSE_FILE, sentences)
    chapters = _read_chapters(workdir / CHAPTERS_FILE)
    timings = read_timings(workdir / TIMING_FILENAME)
    manifest = export_bundle(workdir, parsed, chapters, timings, extra_warnings)
    click.echo(f"  bundle: {workdir}  ({manifest.sentence_count} sentences)")
    if manifest.warnings:
        click.echo("  warnings:")
        for w in manifest.warnings:
            click.echo(f"    - {w}")
    if do_zip:
        archive = zip_bundle(workdir)
        click.echo(f"  zipped: {archive}")


# --- commands ---------------------------------------------------------------

@click.group()
def cli() -> None:
    """Tandem: turn an EPUB into a synced-audiobook export bundle."""


@cli.command()
@click.argument("epub_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--out", "out_dir", required=True, type=click.Path(path_type=Path), help="Bundle output directory.")
@click.option("--models", "models_dir", default=DEFAULT_MODELS, show_default=False, help="Directory holding the Piper voice.")
@click.option("--voice", default=DEFAULT_VOICE, show_default=True, help="Piper voice name.")
@click.option("--zip", "do_zip", is_flag=True, help="Also produce a .zip of the bundle.")
@click.option("--max-sentences", type=int, default=None, help="Cap sentences (for quick test runs).")
def build(epub_path, out_dir, models_dir, voice, do_zip, max_sentences) -> None:
    """Run the full pipeline: EPUB -> export bundle."""
    click.echo(f"[1/4] parse   {epub_path}")
    _run_parse(epub_path, out_dir, max_sentences)
    click.echo("[2/4] tts")
    _run_tts(out_dir, models_dir, voice)
    click.echo("[3/4] align")
    align_warns = _run_align(out_dir)
    click.echo("[4/4] bundle")
    _run_bundle(out_dir, do_zip, align_warns)
    click.echo("done.")


@cli.command()
@click.argument("epub_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--out", "workdir", required=True, type=click.Path(path_type=Path))
@click.option("--max-sentences", type=int, default=None)
def parse(epub_path, workdir, max_sentences) -> None:
    """Stage 1: EPUB -> sentences.json (+ chapter metadata) in a work directory."""
    _run_parse(epub_path, workdir, max_sentences)


@cli.command()
@click.argument("workdir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--models", "models_dir", default=DEFAULT_MODELS)
@click.option("--voice", default=DEFAULT_VOICE)
def tts(workdir, models_dir, voice) -> None:
    """Stage 2: synthesize chapter audio into the work directory."""
    _run_tts(workdir, models_dir, voice)


@cli.command()
@click.argument("workdir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def align(workdir) -> None:
    """Stage 3: build timing.json via forced alignment."""
    _run_align(workdir)


@cli.command()
@click.argument("workdir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--zip", "do_zip", is_flag=True)
def bundle(workdir, do_zip) -> None:
    """Stage 4: assemble manifest.json and finalize the bundle."""
    _run_bundle(workdir, do_zip, extra_warnings=[])


if __name__ == "__main__":
    cli()
