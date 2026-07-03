package com.tandem.reader.match

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.text.Normalizer

class TextNormalizerTest {

    @Test
    fun nfcAndNfdProduceIdenticalTokens() {
        // "café résumé" with precomposed (NFC) accented characters.
        val nfc = Normalizer.normalize("café résumé", Normalizer.Form.NFC)
        // The same text decomposed into base letter + combining mark (NFD).
        val nfd = Normalizer.normalize("café résumé", Normalizer.Form.NFD)
        // Sanity: the two string forms are genuinely different byte sequences.
        assertTrue("NFC and NFD forms should differ before normalization", nfc != nfd)

        val fromNfc = TextNormalizer.tokens(nfc)
        val fromNfd = TextNormalizer.tokens(nfd)

        assertEquals(fromNfc, fromNfd)
        assertEquals(listOf("café", "résumé"), fromNfc)
    }

    @Test
    fun punctuationAndSymbolsActAsSeparators() {
        assertEquals(
            listOf("hello", "world", "foo", "bar", "baz"),
            TextNormalizer.tokens("hello, world! foo-bar—baz?"),
        )
        assertEquals(
            listOf("a", "b", "c"),
            TextNormalizer.tokens("a @#\$%^&* b () c"),
        )
    }

    @Test
    fun digitsAreRetained() {
        assertEquals(
            listOf("chapter", "12", "page", "3"),
            TextNormalizer.tokens("Chapter 12, page 3"),
        )
        assertEquals(
            listOf("abc123"),
            TextNormalizer.tokens("abc123"),
        )
    }

    @Test
    fun casingIsFolded() {
        assertEquals(
            listOf("hello", "world"),
            TextNormalizer.tokens("HeLLo WORLD"),
        )
        assertEquals(
            TextNormalizer.tokens("The Quick Brown Fox"),
            TextNormalizer.tokens("the quick brown fox"),
        )
    }

    @Test
    fun emptyOrWhitespaceInputYieldsEmptyList() {
        assertEquals(emptyList<String>(), TextNormalizer.tokens(""))
        assertEquals(emptyList<String>(), TextNormalizer.tokens("   \t\n  "))
        assertEquals(emptyList<String>(), TextNormalizer.tokens("  ,.!?-  "))
    }
}
