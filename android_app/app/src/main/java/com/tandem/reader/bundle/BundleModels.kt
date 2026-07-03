package com.tandem.reader.bundle

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Kotlin mirror of the export-bundle contract (see docs/bundle-format.md and the PC
 * pipeline's models.py). These deserialize manifest.json / sentences.json / timing.json.
 */

@Serializable
data class BookMeta(
    val title: String,
    val author: String,
    val language: String,
    @SerialName("source_epub") val sourceEpub: String,
)

@Serializable
data class AudioInfo(
    val format: String,
    @SerialName("sample_rate") val sampleRate: Int,
)

@Serializable
data class ChapterEntry(
    val index: Int,
    val title: String,
    val audio: String,
    @SerialName("sentence_start_id") val sentenceStartId: Int,
    @SerialName("sentence_end_id") val sentenceEndId: Int,
)

@Serializable
data class Manifest(
    @SerialName("schema_version") val schemaVersion: Int,
    val book: BookMeta,
    val audio: AudioInfo,
    val chapters: List<ChapterEntry>,
    @SerialName("sentence_count") val sentenceCount: Int,
    val warnings: List<String> = emptyList(),
)

@Serializable
data class Sentence(
    val id: Int,
    @SerialName("chapter_index") val chapterIndex: Int,
    val text: String,
)

@Serializable
data class Timing(
    @SerialName("sentence_id") val sentenceId: Int,
    val audio: String,
    @SerialName("start_ms") val startMs: Long,
    @SerialName("end_ms") val endMs: Long,
    val confidence: String = "ok",
)

/** Schema version this app understands. */
const val SUPPORTED_SCHEMA_VERSION = 1
