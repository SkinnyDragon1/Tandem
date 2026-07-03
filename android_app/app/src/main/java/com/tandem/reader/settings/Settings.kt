package com.tandem.reader.settings

import android.content.Context

/** Persisted, user-tunable behavior. Backed by SharedPreferences. */
class Settings(context: Context) {

    private val prefs = context.getSharedPreferences("tandem_settings", Context.MODE_PRIVATE)

    /** Package names of reader apps to monitor. Aquile Reader is the reference target. */
    var monitoredPackages: List<String>
        get() = prefs.getString(KEY_PACKAGES, DEFAULT_PACKAGES)!!
            .split(",").map { it.trim() }.filter { it.isNotEmpty() }
        set(value) = prefs.edit().putString(KEY_PACKAGES, value.joinToString(",")).apply()

    /** Delay after the last text-change event before attempting a match (collapses scroll spam). */
    var settleDelayMs: Long
        get() = prefs.getLong(KEY_SETTLE, 400L)
        set(value) = prefs.edit().putLong(KEY_SETTLE, value).apply()

    /** Only resync if the matched sentence is at least this many sentences from the playing one. */
    var minSentenceDistance: Int
        get() = prefs.getInt(KEY_DISTANCE, 3)
        set(value) = prefs.edit().putInt(KEY_DISTANCE, value).apply()

    /** Matches below this confidence (0..1) are treated as "no match". */
    var confidenceThreshold: Float
        get() = prefs.getFloat(KEY_CONFIDENCE, 0.45f)
        set(value) = prefs.edit().putFloat(KEY_CONFIDENCE, value).apply()

    fun isMonitored(packageName: CharSequence?): Boolean =
        packageName != null && monitoredPackages.any { it.equals(packageName.toString(), ignoreCase = true) }

    companion object {
        private const val KEY_PACKAGES = "monitored_packages"
        private const val KEY_SETTLE = "settle_delay_ms"
        private const val KEY_DISTANCE = "min_sentence_distance"
        private const val KEY_CONFIDENCE = "confidence_threshold"
        private const val DEFAULT_PACKAGES = "com.neverland.aquilereader"
    }
}
