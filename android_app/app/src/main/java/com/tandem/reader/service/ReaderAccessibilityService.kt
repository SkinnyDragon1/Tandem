package com.tandem.reader.service

import android.accessibilityservice.AccessibilityService
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent
import com.tandem.reader.core.TandemSession
import com.tandem.reader.core.TrackingState
import com.tandem.reader.settings.Settings

/**
 * Watches a monitored reader app's on-screen text and keeps the audiobook in sync.
 *
 * Rapid scroll events are collapsed by a settle delay; once the screen settles, the
 * visible text is matched against the book and — if the match is confident and far
 * enough from the current playback position — the player seeks to follow.
 */
class ReaderAccessibilityService : AccessibilityService() {

    private val handler = Handler(Looper.getMainLooper())
    private lateinit var settings: Settings
    private var pending: Runnable? = null

    override fun onServiceConnected() {
        super.onServiceConnected()
        settings = Settings(applicationContext)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        if (!settings.isMonitored(event.packageName)) {
            // Left the reader app (or a non-monitored app is foreground): stop tracking.
            cancelPending()
            if (TandemSession.trackingState != TrackingState.IDLE) {
                TandemSession.setTracking(TrackingState.IDLE)
            }
            return
        }
        scheduleMatch()
    }

    /** Debounce: only the last event within [Settings.settleDelayMs] triggers a match. */
    private fun scheduleMatch() {
        cancelPending()
        val runnable = Runnable { attemptMatch() }
        pending = runnable
        handler.postDelayed(runnable, settings.settleDelayMs)
    }

    private fun attemptMatch() {
        pending = null
        val matcher = TandemSession.matcher ?: return
        val controller = TandemSession.controller ?: return

        val visibleText = VisibleTextExtractor.extract(rootInActiveWindow)
        if (visibleText.isBlank()) {
            TandemSession.setTracking(TrackingState.NO_MATCH)
            return
        }

        val result = matcher.match(visibleText, hintSentenceId = controller.currentSentenceId())
        if (result.sentenceId < 0 || result.confidence < settings.confidenceThreshold) {
            TandemSession.setTracking(TrackingState.NO_MATCH)
            return
        }

        controller.maybeResync(result.sentenceId)
        TandemSession.setTracking(TrackingState.TRACKING)
    }

    private fun cancelPending() {
        pending?.let { handler.removeCallbacks(it) }
        pending = null
    }

    override fun onInterrupt() {
        cancelPending()
    }
}
