package com.tandem.reader.match

import com.tandem.reader.bundle.Book

/** Result of matching on-screen text to the book. [confidence] is 0..1. */
data class MatchResult(val sentenceId: Int, val confidence: Float) {
    companion object {
        val NONE = MatchResult(-1, 0f)
    }
}

/**
 * Fuzzy-matches on-screen text against the book's sentence index using word n-gram
 * offset voting.
 *
 * The whole book is flattened into one token stream. Each k-gram of the visible text
 * votes for an alignment offset into that stream; the winning offset locates the top of
 * the visible page, whose global token position maps back to a sentence id. Non-book
 * text (menus, TOC) produces few matching n-grams and therefore low confidence, which
 * the caller treats as "no match".
 */
class PositionMatcher(book: Book, private val k: Int = 4) {

    private val tokenToSentence: IntArray            // global token index -> sentence id
    // n-gram key -> sorted global token positions. IntArray values (not boxed lists) keep
    // the index compact for large books.
    private val ngramPositions: HashMap<String, IntArray>

    init {
        val tokens = ArrayList<String>()
        val owner = ArrayList<Int>()
        for (sentence in book.sentences) {
            for (t in TextNormalizer.tokens(sentence.text)) {
                tokens.add(t)
                owner.add(sentence.id)
            }
        }
        tokenToSentence = owner.toIntArray()

        val last = tokens.size - k
        val counts = HashMap<String, Int>()
        var i = 0
        while (i <= last) {
            counts.merge(ngramKey(tokens, i), 1) { a, b -> a + b }
            i++
        }
        ngramPositions = HashMap(counts.size)
        for ((key, c) in counts) ngramPositions[key] = IntArray(c)
        val cursor = HashMap<String, Int>(counts.size)
        i = 0
        while (i <= last) {
            val key = ngramKey(tokens, i)
            val at = cursor[key] ?: 0
            ngramPositions[key]!![at] = i
            cursor[key] = at + 1
            i++
        }
    }

    /**
     * @param hintSentenceId the currently-playing sentence, if known. Used only to break
     *   ties between equally-voted alignments (e.g. a refrain that appears verbatim in
     *   several places) toward the occurrence nearest the current position.
     */
    fun match(visibleText: String, hintSentenceId: Int? = null): MatchResult {
        if (tokenToSentence.isEmpty()) return MatchResult.NONE
        val v = TextNormalizer.tokens(visibleText)
        if (v.size < k) return MatchResult.NONE

        // Vote for alignment offset = (global position) - (visible position). Track, per
        // offset, both the vote count and the earliest matching global token position so
        // leading UI chrome doesn't drag the result to an earlier sentence.
        val offsetVotes = HashMap<Int, Int>()
        val offsetMinPos = HashMap<Int, Int>()
        var probeCount = 0
        val last = v.size - k
        var i = 0
        while (i <= last) {
            val positions = ngramPositions[ngramKey(v, i)]
            if (positions != null) {
                for (p in positions) {
                    val offset = p - i
                    offsetVotes[offset] = (offsetVotes[offset] ?: 0) + 1
                    val prev = offsetMinPos[offset]
                    if (prev == null || p < prev) offsetMinPos[offset] = p
                }
            }
            probeCount++
            i++
        }
        if (offsetVotes.isEmpty()) return MatchResult.NONE

        // All alignments tied at the top vote count. Pick deterministically (never rely on
        // HashMap iteration order): toward the hint if given, else the earliest occurrence.
        val topVotes = offsetVotes.values.max()
        val candidates = offsetVotes.entries.filter { it.value == topVotes }.map { it.key }
        val bestOffset = candidates.minWith(
            compareBy(
                { offset ->
                    val sid = tokenToSentence[offsetMinPos[offset]!!.coerceIn(0, tokenToSentence.size - 1)]
                    if (hintSentenceId != null) kotlin.math.abs(sid - hintSentenceId) else sid
                },
                { it }, // stable final tie-break by offset value
            )
        )
        // Sentence of the first book token actually visible under the winning alignment.
        val firstBookToken = offsetMinPos[bestOffset]!!.coerceIn(0, tokenToSentence.size - 1)
        val sentenceId = tokenToSentence[firstBookToken]
        val confidence = (topVotes.toFloat() / probeCount.coerceAtLeast(1)).coerceIn(0f, 1f)
        return MatchResult(sentenceId, confidence)
    }

    private fun ngramKey(tokens: List<String>, start: Int): String {
        val sb = StringBuilder()
        for (j in 0 until k) {
            if (j > 0) sb.append(' ')
            sb.append(tokens[start + j])
        }
        return sb.toString()
    }
}
