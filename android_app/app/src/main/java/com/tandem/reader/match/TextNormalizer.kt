package com.tandem.reader.match

import java.text.Normalizer

/** Normalizes text for fuzzy matching: Unicode NFC, lowercase, strip non-alphanumerics, tokenize. */
object TextNormalizer {

    private val nonWord = Regex("[^\\p{L}\\p{Nd}]+")

    fun tokens(text: String): List<String> {
        // NFC so precomposed vs decomposed accented text (book side vs accessibility-tree
        // side) tokenizes identically; otherwise combining marks split words apart.
        val nfc = Normalizer.normalize(text, Normalizer.Form.NFC)
        return nonWord.split(nfc.lowercase()).filter { it.isNotEmpty() }
    }
}
