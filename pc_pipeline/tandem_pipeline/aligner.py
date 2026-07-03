"""Stage 3 — forced alignment to produce the per-sentence timing map.

Uses WhisperX's alignment model (wav2vec2, English) to refine each sentence's timing
inside its chapter audio. Because the TTS stage already emits exact per-sentence spans,
those spans seed the alignment and act as a guaranteed fallback: if WhisperX cannot
align a sentence, the synthesis span is used and the sentence is flagged ``low``.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

warnings.filterwarnings("ignore")

import whisperx  # noqa: E402  (import after warning filter; torch stack pinned)

from .models import Sentence, Timing
from .tts_generator import ChapterAudio

WHISPERX_SR = 16000


@dataclass
class AlignModel:
    model: object
    metadata: dict
    device: str
    language: str


def load_align_model(language: str = "en", device: str = "cpu") -> AlignModel:
    model, metadata = whisperx.load_align_model(language_code=language, device=device)
    return AlignModel(model=model, metadata=metadata, device=device, language=language)


def _refine_chapter(
    chapter: ChapterAudio,
    sentences_by_id: dict[int, Sentence],
    align_model: AlignModel,
) -> list[Timing]:
    audio_rel = f"audio/{chapter.audio_path.name}"
    audio = whisperx.load_audio(str(chapter.audio_path))  # 16k float32 mono

    # Seed alignment with the exact synthesis spans (seconds).
    segments = [
        {
            "start": span.start_ms / 1000.0,
            "end": span.end_ms / 1000.0,
            "text": sentences_by_id[span.sentence_id].text,
        }
        for span in chapter.spans
    ]

    refined_by_index: dict[int, tuple[float, float]] = {}
    try:
        result = whisperx.align(
            segments,
            align_model.model,
            align_model.metadata,
            audio,
            align_model.device,
            return_char_alignments=False,
        )
        for i, seg in enumerate(result.get("segments", [])):
            words = seg.get("words", [])
            starts = [w["start"] for w in words if w.get("start") is not None]
            ends = [w["end"] for w in words if w.get("end") is not None]
            if starts and ends:
                refined_by_index[i] = (min(starts), max(ends))
    except Exception:
        # Whole-chapter alignment failed; every sentence falls back below.
        refined_by_index = {}

    timings: list[Timing] = []
    for i, span in enumerate(chapter.spans):
        if i in refined_by_index:
            start_s, end_s = refined_by_index[i]
            timings.append(
                Timing(
                    sentence_id=span.sentence_id,
                    audio=audio_rel,
                    start_ms=int(start_s * 1000),
                    end_ms=int(end_s * 1000),
                    confidence="ok",
                )
            )
        else:
            timings.append(
                Timing(
                    sentence_id=span.sentence_id,
                    audio=audio_rel,
                    start_ms=span.start_ms,
                    end_ms=span.end_ms,
                    confidence="low",
                )
            )
    return timings


def align_chapters(
    chapters: list[ChapterAudio],
    sentences: list[Sentence],
    align_model: AlignModel,
) -> tuple[list[Timing], list[str]]:
    """Align every chapter. Returns (timings ordered by sentence_id, warnings)."""
    sentences_by_id = {s.id: s for s in sentences}
    all_timings: list[Timing] = []
    warnings_out: list[str] = []

    for chapter in chapters:
        timings = _refine_chapter(chapter, sentences_by_id, align_model)
        low = [t.sentence_id for t in timings if t.confidence == "low"]
        if low:
            warnings_out.append(
                f"chapter {chapter.chapter_index}: {len(low)} sentences had "
                f"low-confidence alignment (ids {low[0]}-{low[-1]})"
            )
        all_timings.extend(timings)

    all_timings.sort(key=lambda t: t.sentence_id)
    return all_timings, warnings_out
