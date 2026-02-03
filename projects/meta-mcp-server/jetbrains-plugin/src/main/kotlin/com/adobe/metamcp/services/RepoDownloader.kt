package com.adobe.metamcp.services

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.Logger
import io.ktor.client.*
import io.ktor.client.engine.cio.*
import io.ktor.client.request.*
import io.ktor.client.statement.*
import io.ktor.http.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipInputStream

/**
 * Download progress callback
 */
data class DownloadProgress(
    val stage: DownloadStage,
    val message: String,
    val percent: Int? = null
)

enum class DownloadStage {
    AUTHENTICATING,
    DOWNLOADING,
    EXTRACTING,
    COMPLETE,
    ERROR
}

typealias ProgressCallback = (DownloadProgress) -> Unit

/**
 * Repository Downloader - Downloads GitHub repositories for local server installation
 * Port of extension/src/services/GitHubRepoDownloader.ts
 */
@Service(Service.Level.APP)
class RepoDownloader {
    private val log = Logger.getInstance(RepoDownloader::class.java)

    private val client = HttpClient(CIO) {
        engine {
            requestTimeout = 120000 // 2 minutes for large repos
        }
        followRedirects = true
    }

    private val reposDir: String by lazy {
        val homeDir = System.getProperty("user.home")
        File(homeDir, ".meta-mcp/repos").absolutePath
    }

    companion object {
        fun getInstance(): RepoDownloader =
            ApplicationManager.getApplication().getService(RepoDownloader::class.java)
    }

    /**
     * Download and extract a GitHub repository
     */
    suspend fun downloadRepository(
        repoOwner: String,
        repoName: String,
        branch: String = "main",
        token: String? = null,
        onProgress: ProgressCallback? = null
    ): String = withContext(Dispatchers.IO) {
        // Ensure repos directory exists
        val reposDirFile = File(reposDir)
        if (!reposDirFile.exists()) {
            reposDirFile.mkdirs()
        }

        val targetDir = File(reposDir, repoName)

        // If already exists, return it
        if (targetDir.exists()) {
            onProgress?.invoke(DownloadProgress(DownloadStage.COMPLETE, "Repository already downloaded", 100))
            return@withContext targetDir.absolutePath
        }

        try {
            onProgress?.invoke(DownloadProgress(DownloadStage.DOWNLOADING, "Downloading $repoOwner/$repoName...", 30))

            // Download the repository as a zip archive
            val zipUrl = "https://github.com/$repoOwner/$repoName/archive/refs/heads/$branch.zip"
            log.info("Downloading from: $zipUrl")

            val response = client.get(zipUrl) {
                token?.let {
                    header(HttpHeaders.Authorization, "token $it")
                }
                header(HttpHeaders.UserAgent, "Meta-MCP-JetBrains-Plugin")
            }

            if (!response.status.isSuccess()) {
                throw Exception("Failed to download: ${response.status}")
            }

            val zipData = response.readBytes()

            onProgress?.invoke(DownloadProgress(DownloadStage.EXTRACTING, "Extracting repository...", 60))

            // Create temp directory for extraction
            val tempDir = File(System.getProperty("java.io.tmpdir"), "$repoName-extract-${System.currentTimeMillis()}")
            tempDir.mkdirs()

            // Extract zip
            ZipInputStream(zipData.inputStream()).use { zipIn ->
                var entry = zipIn.nextEntry
                while (entry != null) {
                    val entryFile = File(tempDir, entry.name)
                    if (entry.isDirectory) {
                        entryFile.mkdirs()
                    } else {
                        entryFile.parentFile?.mkdirs()
                        FileOutputStream(entryFile).use { output ->
                            zipIn.copyTo(output)
                        }
                    }
                    zipIn.closeEntry()
                    entry = zipIn.nextEntry
                }
            }

            // GitHub zip contains a folder like "repo-branch", find and rename it
            val extractedFolder = tempDir.listFiles()?.firstOrNull { it.isDirectory }
                ?: throw Exception("Could not find extracted repository folder")

            // Move to final location
            extractedFolder.renameTo(targetDir)

            // Cleanup temp directory
            tempDir.deleteRecursively()

            onProgress?.invoke(DownloadProgress(DownloadStage.COMPLETE, "Repository downloaded successfully", 100))

            targetDir.absolutePath
        } catch (e: Exception) {
            val errorMsg = e.message ?: "Unknown error"
            log.error("Failed to download repository", e)
            onProgress?.invoke(DownloadProgress(DownloadStage.ERROR, errorMsg))
            throw Exception("Failed to download repository: $errorMsg")
        }
    }

    /**
     * Check if a repository is already downloaded
     */
    fun isRepositoryDownloaded(repoName: String): Boolean {
        return File(reposDir, repoName).exists()
    }

    /**
     * Get the local path for a downloaded repository
     */
    fun getRepositoryPath(repoName: String): String? {
        val targetDir = File(reposDir, repoName)
        return if (targetDir.exists()) targetDir.absolutePath else null
    }

    /**
     * Delete a downloaded repository
     */
    fun deleteRepository(repoName: String) {
        File(reposDir, repoName).deleteRecursively()
    }

    /**
     * Parse repo owner and name from a GitHub URL or repo_hint
     */
    fun parseRepoIdentifier(identifier: String): Pair<String, String>? {
        // Try "owner/repo" format first
        val simpleMatch = Regex("^([^/]+)/([^/]+)$").find(identifier)
        if (simpleMatch != null) {
            return Pair(simpleMatch.groupValues[1], simpleMatch.groupValues[2])
        }

        // Try GitHub URL format
        val urlMatch = Regex("github\\.com[/:]([^/]+)/([^/.]+)").find(identifier)
        if (urlMatch != null) {
            return Pair(urlMatch.groupValues[1], urlMatch.groupValues[2])
        }

        return null
    }
}
