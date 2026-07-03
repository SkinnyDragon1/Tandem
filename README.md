# Tandem — EPUB → Synced Audiobook

Turn any EPUB you read into a natural-sounding audiobook whose **playback position
follows where you're scrolled to** in your reader app (e.g. Aquile Reader) on Android.
Scroll to a new spot and the audio seeks to match, then keeps playing continuously
from there.

This is the **"audio follows scrolling"** direction only. The reverse (audio driving
auto-scroll) is deferred to a future iteration.

> Full design: [`docs/superpowers/specs/2026-07-03-epub-audiobook-sync-design.md`](docs/superpowers/specs/2026-07-03-epub-audiobook-sync-design.md)

## How it works

Two independent pieces joined by a one-time **export bundle**. No live PC connection,
cloud service, or account is needed while reading.

```
┌─────────────────────────── PC (batch, once per book) ───────────────────────────┐
│                                                                                  │
│   EPUB ──▶ epub_parser ──▶ tts_generator ──▶ aligner ──▶ bundle_exporter ──▶ 📦  │
│           sentence index    per-chapter WAV   timing map    export bundle        │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────┬─┘
                                                                                 │  manual
                                                              (USB / share / cloud)  transfer
┌────────────────────────── Android (runtime, on device) ───────────────────────┴─┐
│                                                                                  │
│   Import 📦 ──▶ Accessibility Service watches reader app ──▶ Position Matcher ──▶ │
│                (captures visible text)      (fuzzy match → sentence_id)           │
│                                                            │                     │
│                                              Player Controller (ExoPlayer)        │
│                                              seek to timing[sentence_id], play    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Repository layout

```
tandem/
├── README.md
├── docs/superpowers/specs/        # design spec
├── pc_pipeline/                   # Python CLI tool (batch, run on PC)
│   ├── pyproject.toml
│   ├── tandem_pipeline/
│   │   ├── models.py              # shared data models (Sentence, Timing, Manifest)
│   │   ├── epub_parser.py         # EPUB → chapter/sentence text index
│   │   ├── tts_generator.py       # sentence text → per-chapter WAV (Piper)
│   │   ├── aligner.py             # audio + text → sentence timing map (aeneas)
│   │   ├── bundle_exporter.py     # package audio + index + timing → bundle
│   │   └── cli.py                 # `tandem` command orchestrating all stages
│   ├── tests/
│   └── samples/                   # test EPUBs
└── android_app/                   # Kotlin app (runtime, on device)
    └── app/src/main/…             # Import UI, AccessibilityService, Matcher, Player
```

## The export bundle (interface between PC and Android)

A bundle is a folder (optionally zipped as `.tandem`) with this layout:

```
<book>.tandem/
├── manifest.json      # schema version, book metadata, chapter list, audio settings
├── sentences.json     # ordered sentence index: id, chapter, char range, text
├── timing.json        # sentence_id → { audio, start_ms, end_ms } + alignment flags
└── audio/
    ├── chapter_0001.wav
    ├── chapter_0002.wav
    └── …
```

> v1 ships one WAV per chapter (`manifest.audio.format = "wav"`). Opus compression to
> shrink bundle size is a planned optimization; ExoPlayer plays either.

The exact JSON schemas are defined in `pc_pipeline/tandem_pipeline/models.py` and
documented in [`docs/bundle-format.md`](docs/bundle-format.md). Both halves depend on
this contract and nothing else — the PC side writes it, the Android side reads it.

## PC pipeline — usage

Requires Python 3.11, `ffmpeg`, and `espeak`/`espeak-ng` (for aeneas alignment).
Dependencies are managed with [`uv`](https://github.com/astral-sh/uv).

```bash
cd pc_pipeline
uv sync                              # create env + install deps (pinned Python 3.11)
uv run tandem build path/to/book.epub --out ./out/book.tandem
```

Individual stages can also be run on their own for debugging. They share a **work
directory** (the same directory that becomes the bundle); intermediates are kept under
`.work/` and never ship inside the bundle:

```bash
uv run tandem parse book.epub --out ./work   # -> work/sentences.json + chapter metadata
uv run tandem tts   ./work                    # -> work/audio/chapter_*.wav
uv run tandem align ./work                    # -> work/timing.json (forced alignment)
uv run tandem bundle ./work --zip             # -> work/manifest.json (+ work.zip)
```

`--max-sentences N` on `build`/`parse` caps the work for a quick end-to-end test run.

Chapters that yield no usable text, and any sections where forced alignment reports
low confidence, are **flagged in the run log** rather than failing silently.

### Pipeline setup notes

- `uv sync` pins the Torch stack to 2.5.1 (newer `torchaudio` drops
  `AudioMetaData`, which WhisperX/pyannote still import).
- First `build` run downloads the Piper voice (~63 MB, into `pc_pipeline/models/`)
  and the WhisperX wav2vec2 alignment model (~360 MB, cached in `~/.cache`).

## Android app — usage

Sideloaded APK (no Play Store for v1). Requires enabling the app's Accessibility
Service in system settings.

```bash
cd android_app
./gradlew assembleDebug              # build app/build/outputs/apk/debug/app-debug.apk
adb install -r app-debug.apk
```

Build requires a **full JDK 17+ that includes `jlink`** (a JRE alone fails the
`androidJdkImage` transform), the Android SDK (platform 34, build-tools 34), and a
`local.properties` with `sdk.dir=/path/to/android-sdk`.

Then, on device: **Settings → Accessibility → Tandem → On**, open the app, import a
`.tandem` bundle, start playback, and open your reader app. A subtle indicator shows
whether Tandem is currently **tracking** your position or not.

## Scope (v1)

**In scope:** single user / single device, fully local; one book at a time; paginated
*and* continuous-scroll reader apps (built generically against the Android Accessibility
API, with Aquile Reader as the reference target); English EPUBs; manual bundle transfer;
"audio follows scrolling" only.

**Out of scope (future):** audio-drives-auto-scroll; DRM-protected EPUBs; non-English;
cloud/multi-device sync; Play Store distribution.

## Status

Under active development. See the spec for component-level detail and the design
rationale behind each key technical decision (TTS engine, forced alignment, accessibility
based position detection, fuzzy matching).
