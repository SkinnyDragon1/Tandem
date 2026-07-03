# Tandem export-bundle format (schema v1)

The bundle is the **only** contract between the PC pipeline and the Android app. The
PC side writes it; the Android side reads it. Neither side shares code — they share
this document (and its authoritative encoding in
`pc_pipeline/tandem_pipeline/models.py`).

## Layout

```
<book>.tandem/
├── manifest.json
├── sentences.json
├── timing.json
└── audio/
    ├── chapter_0001.wav
    ├── chapter_0002.wav
    └── ...
```

A bundle MAY be distributed as a zip archive with the same internal layout.
Chapter audio filenames are `chapter_%04d.<ext>` using the **1-based** chapter number.

## `manifest.json`

```json
{
  "schema_version": 1,
  "book": {
    "title": "Frankenstein",
    "author": "Mary Shelley",
    "language": "en",
    "source_epub": "frankenstein.epub"
  },
  "audio": { "format": "wav", "sample_rate": 22050 },
  "chapters": [
    {
      "index": 0,
      "title": "Letter 1",
      "audio": "audio/chapter_0001.wav",
      "sentence_start_id": 0,
      "sentence_end_id": 41
    }
  ],
  "sentence_count": 1234,
  "warnings": [
    "chapter 7 ('Notes'): no usable text, skipped",
    "chapter 3: 5 sentences had low-confidence alignment (ids 220-224)"
  ]
}
```

- `chapters[].sentence_start_id` / `sentence_end_id` are **inclusive** global ids.
- `warnings` surfaces skipped chapters and low-confidence alignment ranges so degraded
  sections are visible rather than silent. The Android app may display these; it must
  not treat their presence as a load failure.

## `sentences.json`

Ordered array in global reading order. `id` equals the array index.

```json
[
  { "id": 0, "chapter_index": 0, "text": "You will rejoice to hear that no disaster has accompanied the commencement of an enterprise." },
  { "id": 1, "chapter_index": 0, "text": "I arrived here yesterday." }
]
```

The Android **Position Matcher** fuzzy-matches on-screen text against `text` to recover
the current `id`. Matching is sentence-granular and tolerant of noise (footnote markers,
whitespace, TTS/EPUB divergence) — exact/word-level matching is not required.

## `timing.json`

Array of timing entries, one per sentence, in id order.

```json
[
  { "sentence_id": 0, "audio": "audio/chapter_0001.wav", "start_ms": 0,    "end_ms": 5820, "confidence": "ok" },
  { "sentence_id": 1, "audio": "audio/chapter_0001.wav", "start_ms": 5820, "end_ms": 7010, "confidence": "ok" }
]
```

- `start_ms` / `end_ms` are offsets **within the referenced chapter audio file**.
- `confidence` is `"ok"` or `"low"`. `"low"` marks sentences where forced alignment was
  uncertain; playback still works, timing may be less precise.

## Android read algorithm (informative)

1. Load `manifest.json`, `sentences.json`, `timing.json` once at import.
2. Build an in-memory index from `sentences.json` for fuzzy matching.
3. On a settled position match → `sentence_id`, look up `timing[sentence_id]`, load/seek
   the referenced `audio` file to `start_ms`, and resume continuous playback.

## Versioning

`schema_version` is `1`. Readers must reject bundles whose `schema_version` they do not
understand rather than mis-parsing them.
