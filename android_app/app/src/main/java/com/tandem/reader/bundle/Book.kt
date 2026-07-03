package com.tandem.reader.bundle

import java.io.File

/**
 * A fully loaded book: the parsed manifest plus sentences and timings indexed by id
 * for O(1) lookup, and the on-disk directory holding the audio files.
 */
class Book(
    val manifest: Manifest,
    val sentences: List<Sentence>,
    private val timingById: Map<Int, Timing>,
    val bundleDir: File,
) {
    val title: String get() = manifest.book.title

    fun timingFor(sentenceId: Int): Timing? = timingById[sentenceId]

    fun sentenceOrNull(sentenceId: Int): Sentence? = sentences.getOrNull(sentenceId)

    /** Absolute file for a bundle-relative audio path such as "audio/chapter_0001.wav". */
    fun audioFile(relativePath: String): File = File(bundleDir, relativePath)

    companion object {
        fun from(manifest: Manifest, sentences: List<Sentence>, timings: List<Timing>, dir: File): Book =
            Book(manifest, sentences, timings.associateBy { it.sentenceId }, dir)
    }
}
