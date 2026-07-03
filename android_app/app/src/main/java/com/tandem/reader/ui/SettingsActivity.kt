package com.tandem.reader.ui

import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.tandem.reader.databinding.ActivitySettingsBinding
import com.tandem.reader.settings.Settings

class SettingsActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySettingsBinding
    private lateinit var settings: Settings

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        settings = Settings(this)

        binding.packagesInput.setText(settings.monitoredPackages.joinToString(", "))
        binding.settleInput.setText(settings.settleDelayMs.toString())
        binding.distanceInput.setText(settings.minSentenceDistance.toString())
        binding.confidenceInput.setText((settings.confidenceThreshold * 100).toInt().toString())

        binding.saveButton.setOnClickListener { save() }
    }

    private fun save() {
        settings.monitoredPackages = binding.packagesInput.text.toString()
            .split(",").map { it.trim() }.filter { it.isNotEmpty() }
        binding.settleInput.text.toString().toLongOrNull()?.let { settings.settleDelayMs = it }
        binding.distanceInput.text.toString().toIntOrNull()?.let { settings.minSentenceDistance = it }
        binding.confidenceInput.text.toString().toIntOrNull()?.let {
            settings.confidenceThreshold = (it.coerceIn(0, 100)) / 100f
        }
        Toast.makeText(this, "Saved.", Toast.LENGTH_SHORT).show()
        finish()
    }
}
