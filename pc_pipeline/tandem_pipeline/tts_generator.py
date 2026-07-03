"""Stage 2 — synthesize chapter audio from sentence text with Piper (local, offline).

Each sentence is synthesized as its own clip so we know its exact sample span, then the
clips are concatenated into one WAV per chapter. The per-sentence spans are returned as
*hints* for the alignment stage (and serve as its fallback timing).
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from piper import PiperVoice, SynthesisConfig

from .models import Sentence, chapter_audio_name

DEFAULT_VOICE = "en_US-lessac-medium"
AUDIO_EXT = "wav"


@dataclass(frozen=True)
class SentenceSpan:
    """Exact sample span of one sentence within its chapter audio."""

    sentence_id: int
    start_ms: int
    end_ms: int


@dataclass
class ChapterAudio:
    """Result of synthesizing one chapter."""

    chapter_index: int
    audio_path: Path
    sample_rate: int
    spans: list[SentenceSpan]


def load_voice(model_dir: str | Path, voice: str = DEFAULT_VOICE) -> PiperVoice:
    model_dir = Path(model_dir)
    model_path = model_dir / f"{voice}.onnx"
    config_path = model_dir / f"{voice}.onnx.json"
    if not model_path.exists():
        raise FileNotFoundError(
            f"Piper voice not found: {model_path}. Download with:\n"
            f"  python -m piper.download_voices {voice} --data-dir {model_dir}"
        )
    return PiperVoice.load(model_path, config_path)


def _synthesize_sentence(voice: PiperVoice, text: str, syn: SynthesisConfig) -> np.ndarray:
    """Return int16 mono samples for one sentence."""
    parts = [chunk.audio_int16_array for chunk in voice.synthesize(text, syn_config=syn)]
    if not parts:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(parts)


def synthesize_chapter(
    voice: PiperVoice,
    chapter_index: int,
    sentences: list[Sentence],
    out_dir: Path,
    gap_ms: int = 350,
) -> ChapterAudio:
    """Synthesize one chapter's sentences into a single WAV, tracking exact spans.

    A short silent ``gap_ms`` is inserted between sentences so playback and alignment
    have clean boundaries.
    """
    sr = voice.config.sample_rate
    syn = SynthesisConfig(normalize_audio=True)
    gap = np.zeros(int(sr * gap_ms / 1000), dtype=np.int16)

    buffer: list[np.ndarray] = []
    spans: list[SentenceSpan] = []
    cursor = 0  # samples written so far

    min_samples = int(sr * 0.2)  # floor so a silent/empty synthesis still has a usable span
    for s in sentences:
        audio = _synthesize_sentence(voice, s.text, syn)
        if len(audio) < min_samples:
            audio = np.zeros(min_samples, dtype=np.int16)
        start_ms = int(cursor * 1000 / sr)
        cursor += len(audio)
        end_ms = int(cursor * 1000 / sr)
        spans.append(SentenceSpan(sentence_id=s.id, start_ms=start_ms, end_ms=end_ms))
        buffer.append(audio)
        buffer.append(gap)
        cursor += len(gap)

    samples = np.concatenate(buffer) if buffer else np.zeros(0, dtype=np.int16)

    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / chapter_audio_name(chapter_index, AUDIO_EXT)
    with wave.open(str(audio_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # int16
        wav.setframerate(sr)
        wav.writeframes(samples.tobytes())

    return ChapterAudio(
        chapter_index=chapter_index,
        audio_path=audio_path,
        sample_rate=sr,
        spans=spans,
    )
