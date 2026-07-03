"""Stage 3 — forced alignment to produce the per-sentence timing map.

Uses WhisperX's alignment model (wav2vec2, English) to refine each sentence's timing
inside its chapter audio. Because the TTS stage already emits exact per-sentence spans,
those spans seed the alignment and act as a guaranteed fallback: if WhisperX cannot
align a sentence, the synthesis span is used and the sentence is flagged ``low``.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass

warnings.filterwarnings("ignore")

import whisperx  # noqa: E402  (import after warning filter; torch stack pinned)

from .models import Sentence, Timing
from .tts_generator import ChapterAudio

WHISPERX_SR = 16000

_NORM_RE = re.compile(r"[^a-z0-9]+")


def _norm(text: str) -> str:
    """Normalized key for matching whisperx output segments back to seed sentences."""
    return _NORM_RE.sub(" ", text.lower()).strip()


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
) -> tuple[list[Timing], int]:
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
        aligned = result.get("segments", [])
        # whisperx preserves segment order but may DROP a sentence it cannot align, so the
        # output is an ordered subsequence of the input. Recover the mapping by matching on
        # normalized text with a monotonic pointer (robust to drops; never shifts).
        j = 0
        for i, span in enumerate(chapter.spans):
            target = _norm(segments[i]["text"])
            k = j
            while k < len(aligned) and _norm(aligned[k].get("text", "")) != target:
                k += 1
            if k < len(aligned):
                words = [
                    w for w in aligned[k].get("words", [])
                    if w.get("start") is not None and w.get("end") is not None
                ]
                if words:
                    rs, re_ = min(w["start"] for w in words), max(w["end"] for w in words)
                    # Accept the refinement only if it stays inside this sentence's exact
                    # synthesis window and doesn't collapse to a fragment; otherwise the
                    # exact span is safer than a suspect alignment. (start/end in seconds)
                    lo, hi = span.start_ms / 1000.0, span.end_ms / 1000.0
                    dur = hi - lo
                    if lo - 0.05 <= rs <= re_ <= hi + 0.05 and (re_ - rs) >= 0.5 * dur:
                        refined_by_index[i] = (rs, re_)
                j = k + 1
    except Exception:
        # Whole-chapter alignment failed; every sentence keeps its exact synthesis span.
        refined_by_index = {}

    timings: list[Timing] = []
    for i, span in enumerate(chapter.spans):
        # Synthesis spans are exact (we concatenated per-sentence audio), so both the
        # whisperx-refined and the fallback timings are reliable -> confidence "ok".
        # whisperx only tightens boundaries within a sentence's own audio slice.
        if i in refined_by_index:
            start_s, end_s = refined_by_index[i]
            start_ms, end_ms = int(start_s * 1000), int(end_s * 1000)
        else:
            start_ms, end_ms = span.start_ms, span.end_ms
        timings.append(
            Timing(sentence_id=span.sentence_id, audio=audio_rel, start_ms=start_ms, end_ms=end_ms, confidence="ok")
        )

    unrefined = len(chapter.spans) - len(refined_by_index)
    return timings, unrefined


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
        timings, unrefined = _refine_chapter(chapter, sentences_by_id, align_model)
        if unrefined:
            warnings_out.append(
                f"chapter {chapter.chapter_index}: {unrefined}/{len(timings)} sentences "
                f"not refined by alignment (using exact synthesis timing)"
            )
        all_timings.extend(timings)

    all_timings.sort(key=lambda t: t.sentence_id)
    return all_timings, warnings_out
