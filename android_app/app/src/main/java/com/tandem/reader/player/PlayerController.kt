package com.tandem.reader.player

import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import com.tandem.reader.bundle.Book
import com.tandem.reader.bundle.Timing
import com.tandem.reader.settings.Settings

/**
 * Owns ExoPlayer and the mapping between sentence ids and audio timestamps.
 *
 * Chapters become an ordered playlist (one media item each) so playback flows
 * continuously across chapter boundaries. Seeking to a sentence resolves to
 * (chapter media index, start offset). The reverse mapping — current playback position
 * back to a sentence id — powers the min-distance check that suppresses tiny re-seeks.
 *
 * Must be created and driven on the main thread.
 */
class PlayerController(
    context: Context,
    private val book: Book,
    private val settings: Settings,
) {
    val player: ExoPlayer = ExoPlayer.Builder(context).build()

    private val audioToMediaIndex: Map<String, Int>
    private val mediaIndexToAudio: List<String>
    private val timingsByAudio: Map<String, List<Timing>>

    init {
        val orderedAudio = book.manifest.chapters.map { it.audio }
        mediaIndexToAudio = orderedAudio
        audioToMediaIndex = orderedAudio.withIndex().associate { (i, a) -> a to i }
        timingsByAudio = book.sentences
            .mapNotNull { book.timingFor(it.id) }
            .groupBy { it.audio }
            .mapValues { (_, list) -> list.sortedBy { it.startMs } }

        orderedAudio.forEach { rel ->
            val file = book.audioFile(rel)
            if (!file.exists()) {
                Log.w(TAG, "Bundle audio file missing: $rel")
            }
            player.addMediaItem(MediaItem.fromUri(Uri.fromFile(file)))
        }
        // Surface playback/decode/missing-file errors instead of failing silently.
        player.addListener(object : Player.Listener {
            override fun onPlayerError(error: PlaybackException) {
                Log.e(TAG, "Playback error (${error.errorCodeName})", error)
            }
        })
        player.prepare()
    }

    val isPlaying: Boolean get() = player.isPlaying

    fun playPause() {
        if (player.isPlaying) player.pause() else player.play()
    }

    fun pause() = player.pause()

    /** Seek to a sentence's audio position and resume continuous playback. */
    fun seekToSentence(sentenceId: Int) {
        val timing = book.timingFor(sentenceId) ?: return
        val mediaIndex = audioToMediaIndex[timing.audio] ?: return
        player.seekTo(mediaIndex, timing.startMs)
        player.playWhenReady = true
    }

    /**
     * Resync to [matchedSentenceId]. When audio is already playing, small jitters within
     * [Settings.minSentenceDistance] of the current sentence are ignored. When paused or
     * not yet started, always seek so playback begins at the matched position. Returns
     * true if a seek happened.
     */
    fun maybeResync(matchedSentenceId: Int): Boolean {
        val current = currentSentenceId()
        if (player.isPlaying &&
            current != null &&
            kotlin.math.abs(matchedSentenceId - current) < settings.minSentenceDistance
        ) {
            return false
        }
        seekToSentence(matchedSentenceId)
        return true
    }

    /** The sentence whose audio span currently contains the playhead, if resolvable. */
    fun currentSentenceId(): Int? {
        val audio = mediaIndexToAudio.getOrNull(player.currentMediaItemIndex) ?: return null
        val timings = timingsByAudio[audio] ?: return null
        val posMs = player.currentPosition
        // Largest startMs <= posMs (binary search over sorted timings).
        var lo = 0
        var hi = timings.size - 1
        var found = -1
        while (lo <= hi) {
            val mid = (lo + hi) ushr 1
            if (timings[mid].startMs <= posMs) {
                found = mid
                lo = mid + 1
            } else {
                hi = mid - 1
            }
        }
        return if (found >= 0) timings[found].sentenceId else timings.firstOrNull()?.sentenceId
    }

    fun release() {
        player.release()
    }

    private companion object {
        const val TAG = "TandemPlayer"
    }
}
