package com.tandem.reader.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings as AndroidSettings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.tandem.reader.R
import com.tandem.reader.bundle.BundleException
import com.tandem.reader.bundle.BundleLoader
import com.tandem.reader.core.TandemSession
import com.tandem.reader.core.TrackingState
import com.tandem.reader.databinding.ActivityMainBinding
import com.tandem.reader.player.PlaybackService
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val io = Executors.newSingleThreadExecutor()
    private val trackingListener: (TrackingState) -> Unit = { state ->
        runOnUiThread { renderTracking(state) }
    }

    private val pickBundle = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) importBundle(uri)
    }

    private val requestNotifications =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.importButton.setOnClickListener {
            pickBundle.launch(arrayOf("application/zip", "application/octet-stream", "*/*"))
        }
        binding.playPauseButton.setOnClickListener { onPlayPause() }
        binding.accessibilityButton.setOnClickListener {
            startActivity(Intent(AndroidSettings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        binding.settingsButton.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        maybeRequestNotifications()
        // If a book was imported previously, spin the service back up.
        if (BundleLoader(this).currentBundleDir() != null) {
            PlaybackService.start(this)
        }
    }

    override fun onResume() {
        super.onResume()
        TandemSession.addTrackingListener(trackingListener)
        renderBook()
    }

    override fun onPause() {
        super.onPause()
        TandemSession.removeTrackingListener(trackingListener)
    }

    private fun onPlayPause() {
        val controller = TandemSession.controller
        if (controller == null) {
            if (BundleLoader(this).currentBundleDir() == null) {
                toast("Import a bundle first.")
            } else {
                PlaybackService.start(this)
                toast("Starting playback service…")
            }
            return
        }
        controller.playPause()
        binding.playPauseButton.text =
            getString(if (controller.isPlaying) R.string.pause else R.string.play)
    }

    private fun importBundle(uri: Uri) {
        toast("Importing…")
        io.execute {
            try {
                BundleLoader(this).importZip(uri)
                runOnUiThread {
                    // Reload so the service drops the previous book and loads the new one.
                    PlaybackService.start(this, reload = true)
                    renderBook()
                    toast("Imported.")
                }
            } catch (e: BundleException) {
                runOnUiThread { toast("Import failed: ${e.message}") }
            } catch (e: Exception) {
                runOnUiThread { toast("Import failed: ${e.message}") }
            }
        }
    }

    private fun renderBook() {
        val book = TandemSession.book
        if (book != null) {
            binding.bookTitle.text = book.title
            binding.bookMeta.text = "${book.manifest.book.author} · ${book.manifest.sentenceCount} sentences"
            binding.warningsView.text = book.manifest.warnings.joinToString("\n") { "⚠ $it" }
        } else {
            binding.bookTitle.setText(R.string.no_book)
            binding.bookMeta.text = ""
            binding.warningsView.text = ""
        }
    }

    private fun renderTracking(state: TrackingState) {
        val (textRes, colorRes) = when (state) {
            TrackingState.TRACKING -> R.string.tracking_on to R.color.tracking_on
            TrackingState.NO_MATCH -> R.string.tracking_off to R.color.tracking_off
            TrackingState.IDLE -> R.string.tracking_idle to R.color.tracking_idle
        }
        binding.trackingIndicator.setText(textRes)
        binding.trackingIndicator.setBackgroundColor(ContextCompat.getColor(this, colorRes))
    }

    private fun maybeRequestNotifications() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            requestNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
}
