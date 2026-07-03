package com.tandem.reader.player

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import com.tandem.reader.R
import com.tandem.reader.bundle.BundleLoader
import com.tandem.reader.core.TandemSession
import com.tandem.reader.core.TrackingState
import com.tandem.reader.match.PositionMatcher
import com.tandem.reader.settings.Settings
import com.tandem.reader.ui.MainActivity
import java.util.concurrent.Executors

/**
 * Foreground service that owns audio playback so it continues while the reader app is in
 * the foreground. Loads the imported bundle, builds the matcher and player, registers
 * them in [TandemSession], and reflects the live tracking state in its notification (the
 * only place the "tracking / not tracking" indicator is visible while reading).
 */
class PlaybackService : Service() {

    private val mainHandler = Handler(Looper.getMainLooper())
    private val background = Executors.newSingleThreadExecutor()
    @Volatile private var loading = false

    private val trackingListener: (TrackingState) -> Unit = { updateNotification() }

    override fun onCreate() {
        super.onCreate()
        val notification = buildNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
        TandemSession.addTrackingListener(trackingListener)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_PLAY_PAUSE -> {
                TandemSession.controller?.playPause()
                updateNotification()
            }
            ACTION_RELOAD -> {
                mainHandler.post { TandemSession.clear() }
                ensureLoaded()
            }
            ACTION_STOP -> {
                stopSelf()
                return START_NOT_STICKY
            }
            else -> ensureLoaded()
        }
        return START_STICKY
    }

    private fun ensureLoaded() {
        if (TandemSession.hasBook() || loading) return
        val loader = BundleLoader(applicationContext)
        val dir = loader.currentBundleDir() ?: return
        loading = true
        background.execute {
            val book = try {
                loader.load(dir)
            } catch (e: Exception) {
                loading = false
                return@execute
            }
            val matcher = PositionMatcher(book)
            mainHandler.post {
                // A newer clear()/load may have happened; only publish if still needed.
                val controller = PlayerController(applicationContext, book, Settings(applicationContext))
                TandemSession.loadBook(book, matcher, controller)
                loading = false
                updateNotification()
            }
        }
    }

    private fun updateNotification() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, buildNotification())
    }

    private fun buildNotification(): android.app.Notification {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Playback", NotificationManager.IMPORTANCE_LOW)
            )
        }
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val playPause = PendingIntent.getService(
            this, 1, Intent(this, PlaybackService::class.java).setAction(ACTION_PLAY_PAUSE),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val trackingText = when (TandemSession.trackingState) {
            TrackingState.TRACKING -> getString(R.string.tracking_on)
            TrackingState.NO_MATCH -> getString(R.string.tracking_off)
            TrackingState.IDLE -> getString(R.string.tracking_idle)
        }
        val title = TandemSession.book?.title ?: getString(R.string.no_book)
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(trackingText)
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentIntent(open)
            .addAction(0, getString(R.string.play) + "/" + getString(R.string.pause), playPause)
            .setOngoing(true)
            .build()
    }

    override fun onDestroy() {
        TandemSession.removeTrackingListener(trackingListener)
        background.shutdownNow()
        TandemSession.clear()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        private const val CHANNEL_ID = "tandem_playback"
        private const val NOTIFICATION_ID = 1
        const val ACTION_PLAY_PAUSE = "com.tandem.reader.PLAY_PAUSE"
        const val ACTION_RELOAD = "com.tandem.reader.RELOAD"
        const val ACTION_STOP = "com.tandem.reader.STOP"

        fun start(context: Context, reload: Boolean = false) {
            val intent = Intent(context, PlaybackService::class.java)
            if (reload) intent.action = ACTION_RELOAD
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }
    }
}
