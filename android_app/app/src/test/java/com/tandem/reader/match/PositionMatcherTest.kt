package com.tandem.reader.match

import com.tandem.reader.bundle.AudioInfo
import com.tandem.reader.bundle.Book
import com.tandem.reader.bundle.BookMeta
import com.tandem.reader.bundle.Manifest
import com.tandem.reader.bundle.Sentence
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class PositionMatcherTest {

    private val sentenceTexts = listOf(
        "It is very seldom that mere ordinary people like John and myself secure ancestral halls for the summer.",
        "A colonial mansion, a hereditary estate, I would say a haunted house, and reach the height of romantic felicity.",
        "But that would be asking too much of fate!",
        "Still I will proudly declare that there is something queer about it.",
        "Else, why should it be let so cheaply? And why have stood so long untenanted?",
        "John laughs at me, of course, but one expects that in marriage.",
        "John is practical in the extreme, and he has no patience with faith.",
        "He scoffs openly at any talk of things not to be felt and seen and put down in figures.",
    )

    private fun book(): Book {
        val sentences = sentenceTexts.mapIndexed { i, t -> Sentence(i, 0, t) }
        val manifest = Manifest(
            schemaVersion = 1,
            book = BookMeta("Test", "Author", "en", "t.epub"),
            audio = AudioInfo("wav", 22050),
            chapters = emptyList(),
            sentenceCount = sentences.size,
        )
        return Book.from(manifest, sentences, emptyList(), File("."))
    }

    @Test
    fun matchesExactVisiblePage() {
        val matcher = PositionMatcher(book())
        // A "page" starting at sentence 3.
        val visible = sentenceTexts[3] + " " + sentenceTexts[4] + " " + sentenceTexts[5]
        val result = matcher.match(visible)
        assertEquals(3, result.sentenceId)
        assertTrue("confidence should be high", result.confidence > 0.8f)
    }

    @Test
    fun matchesWithSurroundingUiChrome() {
        val matcher = PositionMatcher(book())
        val visible = "12:45  battery 80%  " + sentenceTexts[6] + "  Chapter menu  settings"
        val result = matcher.match(visible)
        assertEquals(6, result.sentenceId)
        assertTrue(result.confidence > 0f)
    }

    @Test
    fun nonBookTextYieldsNoConfidentMatch() {
        val matcher = PositionMatcher(book())
        val visible = "Settings Display Font size Brightness Table of contents Bookmarks Search"
        val result = matcher.match(visible)
        assertTrue("garbage should be low confidence", result.confidence < 0.2f)
    }

    @Test
    fun tooShortTextIsNoMatch() {
        val matcher = PositionMatcher(book())
        val result = matcher.match("the")
        assertEquals(MatchResult.NONE, result)
    }

    @Test
    fun repeatedPassageIsDeterministicAndHintBreaksTies() {
        // Two identical passages at sentence 1 and sentence 5.
        val refrain = "the bell tolled slowly across the empty silent frozen valley below"
        val texts = listOf(
            "Opening line about nothing in particular here at the very start.",
            refrain,
            "Some unrelated middle content that carries the story onward a while.",
            "More filler prose to separate the two identical refrains cleanly here.",
            "Yet more distinct narrative padding between the repeated passages now.",
            refrain,
            "A closing line that wraps everything up at the very end of it all.",
        )
        val sentences = texts.mapIndexed { i, t -> com.tandem.reader.bundle.Sentence(i, 0, t) }
        val manifest = Manifest(1, BookMeta("T", "A", "en", "t.epub"), AudioInfo("wav", 22050), emptyList(), sentences.size)
        val b = Book.from(manifest, sentences, emptyList(), File("."))
        val matcher = PositionMatcher(b)

        // Deterministic across repeated calls (no HashMap-order flakiness); earliest by default.
        val a1 = matcher.match(refrain)
        val a2 = matcher.match(refrain)
        assertEquals(a1.sentenceId, a2.sentenceId)
        assertEquals(1, a1.sentenceId)

        // A hint near the later occurrence resolves the tie toward it.
        assertEquals(5, matcher.match(refrain, hintSentenceId = 5).sentenceId)
    }
}
