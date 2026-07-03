package com.tandem.reader.bundle

import android.content.Context
import android.net.Uri
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
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

    /**
     * Copy a picked .zip bundle into storage, replacing any existing book. Returns the
     * loaded [Book], or throws [BundleException] if the archive is malformed/unsupported.
     */
    fun importZip(uri: Uri): Book {
        clearExisting()
        context.contentResolver.openInputStream(uri)?.use { input ->
            unzipInto(input, booksRoot)
        } ?: throw BundleException("Could not open the selected file.")
        val dir = locateBundleRoot(booksRoot)
        return load(dir)
    }

    /** Load a bundle already present at [dir] (e.g. re-loading the imported book). */
    fun load(dir: File): Book {
        val manifestFile = File(dir, "manifest.json")
        if (!manifestFile.exists()) throw BundleException("manifest.json not found in bundle.")

        val manifest = json.decodeFromString<Manifest>(manifestFile.readText())
        if (manifest.schemaVersion != SUPPORTED_SCHEMA_VERSION) {
            throw BundleException(
                "Unsupported bundle schema v${manifest.schemaVersion} " +
                    "(this app supports v$SUPPORTED_SCHEMA_VERSION)."
            )
        }
        val sentences = json.decodeFromString<List<Sentence>>(File(dir, "sentences.json").readText())
        val timings = json.decodeFromString<List<Timing>>(File(dir, "timing.json").readText())
        return Book.from(manifest, sentences, timings, dir)
    }

    /** The directory of the currently imported book, if any. */
    fun currentBundleDir(): File? =
        booksRoot.takeIf { File(it, "manifest.json").exists() }
            ?: locateBundleRootOrNull(booksRoot)

    private fun clearExisting() {
        booksRoot.deleteRecursively()
        booksRoot.mkdirs()
    }

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
