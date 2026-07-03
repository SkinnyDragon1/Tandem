package com.tandem.reader.bundle

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Verifies the Android bundle models deserialize the exact snake_case JSON the PC
 * pipeline emits (manifest.json / sentences.json / timing.json), that @SerialName
 * mappings hold, that unknown extra fields are tolerated, and that a Book built from
 * the decoded data answers lookups correctly.
 */
class BundleModelsTest {

    private val json = Json { ignoreUnknownKeys = true }

    // manifest.json exactly as the pipeline emits it, plus an unknown extra field.
    private val manifestJson = """
        {
          "schema_version": 1,
          "book": {
            "title": "The Yellow Wallpaper",
            "author": "Charlotte Perkins Gilman",
            "language": "en",
            "source_epub": "yellow_wallpaper.epub"
          },
          "audio": {
            "format": "wav",
            "sample_rate": 22050
          },
          "chapters": [
            {
              "index": 0,
              "title": "Chapter 1",
              "audio": "audio/chapter_0001.wav",
              "sentence_start_id": 0,
              "sentence_end_id": 2
            },
            {
              "index": 1,
              "title": "Chapter 2",
              "audio": "audio/chapter_0002.wav",
              "sentence_start_id": 3,
              "sentence_end_id": 3
            }
          ],
          "sentence_count": 4,
          "warnings": ["one clip was silent"],
          "generator_version": "0.9.1"
        }
    """.trimIndent()

    // sentences.json: a flat array of sentence objects.
    private val sentencesJson = """
        [
          {"id": 0, "chapter_index": 0, "text": "It is very seldom that mere ordinary people secure ancestral halls."},
          {"id": 1, "chapter_index": 0, "text": "A colonial mansion, a hereditary estate.", "unexpected_field": 42},
          {"id": 2, "chapter_index": 0, "text": "But that would be asking too much of fate!"},
          {"id": 3, "chapter_index": 1, "text": "John laughs at me, of course."}
        ]
    """.trimIndent()

    // timing.json: a flat array of timing objects.
    private val timingJson = """
        [
          {"sentence_id": 0, "audio": "audio/chapter_0001.wav", "start_ms": 0, "end_ms": 3200},
          {"sentence_id": 1, "audio": "audio/chapter_0001.wav", "start_ms": 3200, "end_ms": 6100, "confidence": "low"},
          {"sentence_id": 2, "audio": "audio/chapter_0001.wav", "start_ms": 6100, "end_ms": 9000},
          {"sentence_id": 3, "audio": "audio/chapter_0002.wav", "start_ms": 0, "end_ms": 2500}
        ]
    """.trimIndent()

    @Test
    fun manifestDeserializesWithSerialNameMappings() {
        val manifest = json.decodeFromString(Manifest.serializer(), manifestJson)

        assertEquals(1, manifest.schemaVersion)
        assertEquals(4, manifest.sentenceCount)
        assertEquals(SUPPORTED_SCHEMA_VERSION, manifest.schemaVersion)
        assertEquals(listOf("one clip was silent"), manifest.warnings)

        assertEquals("The Yellow Wallpaper", manifest.book.title)
        assertEquals("Charlotte Perkins Gilman", manifest.book.author)
        assertEquals("en", manifest.book.language)
        assertEquals("yellow_wallpaper.epub", manifest.book.sourceEpub)

        assertEquals("wav", manifest.audio.format)
        assertEquals(22050, manifest.audio.sampleRate)

        assertEquals(2, manifest.chapters.size)
        val ch0 = manifest.chapters[0]
        assertEquals(0, ch0.index)
        assertEquals("Chapter 1", ch0.title)
        assertEquals("audio/chapter_0001.wav", ch0.audio)
        assertEquals(0, ch0.sentenceStartId)
        assertEquals(2, ch0.sentenceEndId)
        assertEquals(3, manifest.chapters[1].sentenceStartId)
        assertEquals(3, manifest.chapters[1].sentenceEndId)
    }

    @Test
    fun sentencesDeserializeAndIgnoreUnknownField() {
        val sentences = json.decodeFromString(
            kotlinx.serialization.builtins.ListSerializer(Sentence.serializer()),
            sentencesJson,
        )

        assertEquals(4, sentences.size)
        assertEquals(0, sentences[0].id)
        assertEquals(0, sentences[0].chapterIndex)
        assertEquals("It is very seldom that mere ordinary people secure ancestral halls.", sentences[0].text)
        // The unknown "unexpected_field" on sentence 1 must be silently ignored.
        assertEquals(1, sentences[1].id)
        assertEquals("A colonial mansion, a hereditary estate.", sentences[1].text)
        assertEquals(1, sentences[3].chapterIndex)
    }

    @Test
    fun timingsDeserializeWithSerialNamesAndDefaults() {
        val timings = json.decodeFromString(
            kotlinx.serialization.builtins.ListSerializer(Timing.serializer()),
            timingJson,
        )

        assertEquals(4, timings.size)
        val t0 = timings[0]
        assertEquals(0, t0.sentenceId)
        assertEquals("audio/chapter_0001.wav", t0.audio)
        assertEquals(0L, t0.startMs)
        assertEquals(3200L, t0.endMs)
        // confidence omitted in JSON -> default "ok".
        assertEquals("ok", t0.confidence)
        // confidence explicitly set on timing 1.
        assertEquals("low", timings[1].confidence)
        assertEquals(2500L, timings[3].endMs)
    }

    @Test
    fun bookFromDecodedJsonAnswersLookups() {
        val manifest = json.decodeFromString(Manifest.serializer(), manifestJson)
        val sentences = json.decodeFromString(
            kotlinx.serialization.builtins.ListSerializer(Sentence.serializer()),
            sentencesJson,
        )
        val timings = json.decodeFromString(
            kotlinx.serialization.builtins.ListSerializer(Timing.serializer()),
            timingJson,
        )
        val dir = File("/tmp/bundle")
        val book = Book.from(manifest, sentences, timings, dir)

        assertEquals("The Yellow Wallpaper", book.title)

        // sentenceOrNull is index-based; ids line up with list positions here.
        assertEquals("But that would be asking too much of fate!", book.sentenceOrNull(2)?.text)
        assertNull(book.sentenceOrNull(4))
        assertNull(book.sentenceOrNull(-1))

        // timingFor is keyed by sentence_id.
        val t3 = book.timingFor(3)
        assertTrue("timing for sentence 3 should exist", t3 != null)
        assertEquals("audio/chapter_0002.wav", t3!!.audio)
        assertEquals(0L, t3.startMs)
        assertEquals(2500L, t3.endMs)
        assertNull(book.timingFor(99))

        // audioFile resolves a bundle-relative path against the bundle dir.
        val expected = File(dir, "audio/chapter_0001.wav")
        assertEquals(expected, book.audioFile("audio/chapter_0001.wav"))
        assertEquals(expected.absolutePath, book.audioFile("audio/chapter_0001.wav").absolutePath)
    }
}
