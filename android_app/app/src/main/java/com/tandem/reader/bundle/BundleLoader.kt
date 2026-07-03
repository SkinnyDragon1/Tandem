package com.tandem.reader.bundle

import android.content.Context
import android.net.Uri
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import java.io.InputStream
import java.util.zip.ZipInputStream

/**
 * Imports an export bundle (a folder tree copied in, or a .zip) into app-private storage
 * and loads it into a [Book]. Only one book is kept at a time (v1 scope).
 */
class BundleLoader(private val context: Context) {

    private val json = Json { ignoreUnknownKeys = true }

    private val booksRoot: File
        get() = File(context.filesDir, "book").apply { mkdirs() }

    private val stagingRoot: File
        get() = File(context.filesDir, "book_import_tmp")

    /**
     * Import a picked .zip bundle. Unzips and fully validates into a staging directory
     * first, and only swaps it in on success — a failed import leaves the previously
     * working book untouched. Returns the loaded [Book] or throws [BundleException].
     */
    fun importZip(uri: Uri): Book {
        val staging = stagingRoot
        staging.deleteRecursively()
        staging.mkdirs()
        try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                unzipInto(input, staging)
            } ?: throw BundleException("Could not open the selected file.")
            val stagedRoot = locateBundleRoot(staging)
            load(stagedRoot)  // validate before touching the existing book

            booksRoot.deleteRecursively()
            if (!stagedRoot.renameTo(booksRoot)) {
                stagedRoot.copyRecursively(booksRoot, overwrite = true)
            }
            return load(booksRoot)
        } finally {
            staging.deleteRecursively()
        }
    }

    /** Load a bundle already present at [dir] (e.g. re-loading the imported book). */
    fun load(dir: File): Book {
        val manifestText = readRequired(dir, "manifest.json")

        // Check the schema version before a full decode so a future/incompatible bundle
        // fails with a clear message rather than a cryptic deserialization error.
        val schemaVersion = try {
            Json.parseToJsonElement(manifestText).jsonObject["schema_version"]?.jsonPrimitive?.int
        } catch (e: Exception) {
            throw BundleException("manifest.json is not valid JSON.")
        }
        if (schemaVersion != SUPPORTED_SCHEMA_VERSION) {
            throw BundleException(
                "Unsupported bundle schema v$schemaVersion (this app supports v$SUPPORTED_SCHEMA_VERSION)."
            )
        }

        return try {
            val manifest = json.decodeFromString<Manifest>(manifestText)
            val sentences = json.decodeFromString<List<Sentence>>(readRequired(dir, "sentences.json"))
            val timings = json.decodeFromString<List<Timing>>(readRequired(dir, "timing.json"))
            Book.from(manifest, sentences, timings, dir)
        } catch (e: BundleException) {
            throw e
        } catch (e: Exception) {
            throw BundleException("Bundle contains malformed JSON: ${e.message}")
        }
    }

    private fun readRequired(dir: File, name: String): String {
        val f = File(dir, name)
        if (!f.exists()) throw BundleException("$name not found in bundle.")
        return f.readText()
    }

    /** The directory of the currently imported book, if any. */
    fun currentBundleDir(): File? =
        booksRoot.takeIf { File(it, "manifest.json").exists() }
            ?: locateBundleRootOrNull(booksRoot)

    private fun unzipInto(input: InputStream, destRoot: File) {
        ZipInputStream(input.buffered()).use { zis ->
            var entry = zis.nextEntry
            while (entry != null) {
                val outFile = File(destRoot, entry.name)
                // Guard against zip-slip path traversal.
                if (!outFile.canonicalPath.startsWith(destRoot.canonicalPath + File.separator)) {
                    throw BundleException("Bundle contains an invalid path: ${entry.name}")
                }
                if (entry.isDirectory) {
                    outFile.mkdirs()
                } else {
                    outFile.parentFile?.mkdirs()
                    outFile.outputStream().use { zis.copyTo(it) }
                }
                zis.closeEntry()
                entry = zis.nextEntry
            }
        }
    }

    /** A zip may contain the bundle at its root or nested one level under a folder. */
    private fun locateBundleRoot(root: File): File =
        locateBundleRootOrNull(root) ?: throw BundleException("No manifest.json found in bundle.")

    private fun locateBundleRootOrNull(root: File): File? {
        if (File(root, "manifest.json").exists()) return root
        return root.listFiles()?.firstOrNull { it.isDirectory && File(it, "manifest.json").exists() }
    }
}

class BundleException(message: String) : Exception(message)
