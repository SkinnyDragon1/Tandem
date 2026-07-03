# EPUB-to-Synced-Audiobook — Design Spec (v1)

## Purpose

Turn any EPUB you read into a natural-sounding audiobook where the audio playback position follows where you're currently scrolled to in your reader app (e.g., Aquile Reader) on Android. When you scroll to a new position, the audio seeks to match and resumes continuous playback from there.

This is the first half of a larger goal (bidirectional sync between reading position and audio). The other direction — audio driving auto-scroll — is explicitly deferred to a future iteration.

## Architecture Overview

Two independent pieces connected by a one-time exported bundle, with no live connection required between them at read time:

- **PC Pipeline** (batch, run once per book): takes an EPUB file and produces an export bundle containing generated audio, a sentence-level text index, and a timing map.
- **Android App** (runtime, on-device): a native app with an Accessibility Service that imports an export bundle, plays its audio, watches on-screen text in your reader app, and seeks audio to match your position.

The export bundle is transferred to the phone manually (e.g., USB, file share, cloud folder) after PC-side processing. No cloud service, account, or live PC connection is needed while reading.

## Components

### PC Pipeline (Python CLI tool)

1. **`epub_parser`** — extracts plain text from the EPUB (standard EPUB2/3), preserving chapter structure, splits text into sentences, assigns each a sentence ID.
2. **`tts_generator`** — synthesizes audio from the sentence text using a local, free neural TTS engine (Piper or XTTS), chunked per chapter to manage memory.
3. **`aligner`** — runs forced alignment (e.g., aeneas or whisperx) between the generated audio and the sentence-split text, producing the timing map: `sentence_id → (start_time, end_time)` in the audio.
4. **`bundle_exporter`** — packages audio files, the sentence text index, the timing map, and book metadata into a single export bundle (folder or zip) for transfer to the phone.

### Android App (Kotlin)

1. **Library/Import screen** — select an export bundle from local storage and register it as an available book.
2. **Accessibility Service** — runs in the background while a monitored reader app is in the foreground; captures visible text via the accessibility node tree. Not hardcoded to a single reader app's package name — configurable, with Aquile Reader as the initial reference target.
3. **Position Matcher** — fuzzy-matches captured on-screen text (edit-distance / n-gram based) against the book's sentence text index to determine the current sentence ID. Produces a low-confidence result (treated as "no match") when the visible text doesn't resemble book content (e.g., menus, table of contents, overlays).
4. **Player Controller** — owns audio playback (ExoPlayer), looks up the matched sentence ID in the timing map, seeks to the corresponding timestamp, and resumes continuous playback. Applies debounce logic before triggering a resync.
5. **Settings** — which app(s) to monitor, resync sensitivity (debounce thresholds), playback controls.

## Data Flow

**PC side (one-time, per book):**

```
EPUB file
  → epub_parser → sentence-split text index
  → tts_generator → audio files
  → aligner (audio + text index) → timing map
  → bundle_exporter → export bundle
```

**Phone side (per reading session, continuous loop):**

```
Reader app shows current page/scroll position
  → Accessibility Service captures visible text
  → (settle delay ~300-500ms after last text-change event)
  → Position Matcher fuzzy-matches text against text index → sentence_id
  → if sentence_id is more than N sentences (default ~2-3, configurable)
    from the currently-playing sentence:
      → Player Controller looks up sentence_id in timing map → timestamp
      → seek audio to timestamp, resume continuous playback
  → otherwise: no action, audio keeps playing uninterrupted
```

The settle delay collapses rapid-fire accessibility events during scrolling into a single match attempt. The minimum sentence-distance threshold prevents small jitters or scroll-and-settle-back motions from within the same paragraph from triggering unnecessary re-seeks.

## Error Handling & Edge Cases

- **No confident text match** (cover page, table of contents, an app/screen the parser can't map to book content): audio keeps playing from its current position; no seek occurs. The app shows a subtle "not tracking" indicator so this is visible rather than silent.
- **EPUB with unusual structure** (heavy custom HTML/CSS, embedded images-as-text, DRM-protected content): parser does best-effort extraction; a chapter yielding no usable text is skipped and flagged in the pipeline's output log rather than failing silently. DRM-protected EPUBs are out of scope for v1 (see Scope).
- **Forced alignment failure/low-confidence on a section**: flagged in the pipeline log with the affected sentence range, so degraded timing accuracy in that section is visible rather than hidden.
- **Reader app shows non-book UI** (menu, notification overlay): handled by the same low-confidence "no match" path as above.
- **Minor text extraction noise** (footnote markers, odd whitespace, TTS/EPUB text divergence): tolerated by design, since matching operates at sentence granularity with fuzzy comparison rather than requiring exact/word-level matches.

## Scope (v1)

**In scope:**
- Single user, single Android device, fully local (no cloud sync, no accounts).
- One book loaded on the phone at a time.
- Both paginated and continuous-scroll reader apps, built generically against the Android Accessibility API; Aquile Reader is the initial reference/test target.
- English-language EPUBs.
- Manual bundle transfer from PC to phone.
- "Audio follows scrolling" sync direction only.

**Explicitly out of scope (future work):**
- "Audio drives auto-scroll" (the reverse sync direction).
- DRM-protected EPUBs.
- Non-English languages.
- Cloud sync, multi-device, or companion-device features.
- Play Store distribution (sideloaded APK only for v1).

## Testing Approach

- **PC pipeline:** unit-testable per stage — parser output validated against sample EPUBs; alignment output spot-checked by listening to a sample of sentence timestamp ranges against the generated audio.
- **Android app:** the accessibility-matching loop depends on real reader-app UI behavior and is inherently hard to automate well. Primary acceptance testing is manual, end-to-end, against Aquile Reader on-device — covering page turns, continuous scroll, non-book screens (menus/TOC), and jitter/fling-scroll scenarios to validate debounce behavior.

## Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| TTS engine | Local/open-source (Piper or XTTS) | Free, offline, private; accepted trade-off of somewhat less expressive audio than top cloud voices |
| Timing map generation | Forced alignment (aeneas/whisperx) against generated audio | Well-established technique, portable across TTS engine choice |
| Live position detection | Android Accessibility Service | Reads on-screen text directly and efficiently; risk noted for readers using custom canvas rendering rather than native text views (not currently known to affect Aquile Reader; to be validated during implementation) |
| Position matching | Fuzzy substring/edit-distance matching against sentence text index | Tolerant of accessibility text noise (UI chrome, extraction differences) |
| Compute split | PC does batch audio/alignment generation; phone does live matching fully offline | Expensive one-time work off the phone; no connectivity dependency while reading |
| Phone app form | Native Kotlin app, sideloaded APK | Accessibility Service requires a real installed app; full control and reliability |
