package com.tandem.reader.core

import com.tandem.reader.bundle.Book
import com.tandem.reader.match.PositionMatcher
import com.tandem.reader.player.PlayerController
import java.util.concurrent.CopyOnWriteArrayList

/** Whether the accessibility loop is currently able to follow the reader. */
enum class TrackingState { IDLE, TRACKING, NO_MATCH }

/**
 * Process-wide bridge between the [com.tandem.reader.player.PlaybackService] (owns the
 * player) and the [com.tandem.reader.service.ReaderAccessibilityService] (produces
 * position matches), plus the current book/matcher. v1 holds a single book.
 *
 * All player interaction happens on the main thread.
 */
object TandemSession {

    @Volatile
    var book: Book? = null
        private set

    @Volatile
    var matcher: PositionMatcher? = null
        private set

    @Volatile
    var controller: PlayerController? = null
        private set

    @Volatile
    var trackingState: TrackingState = TrackingState.IDLE
        private set

    private val trackingListeners = CopyOnWriteArrayList<(TrackingState) -> Unit>()

    /** Observe the tracking indicator. Both the UI and the playback notification listen. */
    fun addTrackingListener(listener: (TrackingState) -> Unit) {
        trackingListeners.add(listener)
        listener(trackingState)
    }

    fun removeTrackingListener(listener: (TrackingState) -> Unit) {
        trackingListeners.remove(listener)
    }

    fun setTracking(state: TrackingState) {
        trackingState = state
        trackingListeners.forEach { it(state) }
    }

    /** Replace the loaded book, releasing any previous player first. */
    fun loadBook(book: Book, matcher: PositionMatcher, controller: PlayerController) {
        this.controller?.release()
        this.book = book
        this.matcher = matcher
        this.controller = controller
        setTracking(TrackingState.IDLE)
    }

    /** Release and clear everything (service teardown). */
    fun clear() {
        controller?.release()
        controller = null
        matcher = null
        book = null
        setTracking(TrackingState.IDLE)
    }

    fun hasBook(): Boolean = book != null && controller != null
}
