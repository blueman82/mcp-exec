package com.adobe.metamcp.services

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.project.ProjectManager
import java.io.File
import java.util.concurrent.TimeUnit

private val isMac = System.getProperty("os.name").lowercase().contains("mac")
private val isWindows = System.getProperty("os.name").lowercase().contains("win")
private val homeDir = System.getProperty("user.home")

/**
 * Repository Detector - Auto-detects local repository clones
 * Port of extension/src/services/RepoDetector.ts
 */
@Service(Service.Level.APP)
class RepoDetector {
    private val log = Logger.getInstance(RepoDetector::class.java)

    companion object {
        fun getInstance(): RepoDetector =
            ApplicationManager.getApplication().getService(RepoDetector::class.java)
    }

    /**
     * Auto-detect the location of a repository (e.g., adobe-mcp-servers)
     * Uses multiple strategies: IntelliJ open projects, Spotlight (macOS), find command
     */
    fun findRepository(repoName: String): String? {
        // 1. Check currently open projects in IntelliJ
        val projectManager = ProjectManager.getInstance()
        for (project in projectManager.openProjects) {
            val basePath = project.basePath
            if (basePath != null) {
                if (basePath.contains(repoName)) {
                    return basePath
                }
                // Also check if it's a subfolder
                val subPath = File(basePath, repoName)
                if (subPath.exists()) {
                    return subPath.absolutePath
                }
            }
        }

        // 2. Check downloaded repos directory
        val downloadedPath = RepoDownloader.getInstance().getRepositoryPath(repoName)
        if (downloadedPath != null) {
            return downloadedPath
        }

        // 3. macOS Spotlight search (instant, indexed)
        if (isMac) {
            findWithSpotlight(repoName)?.let { return it }
        }

        // 4. Fast find with depth limit (works on all platforms)
        findWithSystemSearch(repoName)?.let { return it }

        return null
    }

    /**
     * Use macOS Spotlight for fast indexed search
     */
    private fun findWithSpotlight(repoName: String): String? {
        return try {
            val process = ProcessBuilder("mdfind", "-name", repoName, "-onlyin", homeDir)
                .redirectErrorStream(true)
                .start()

            val result = process.inputStream.bufferedReader().readText().trim()
            process.waitFor(3, TimeUnit.SECONDS)

            result.lines()
                .firstOrNull { it.endsWith("/$repoName") && File(it).exists() }
        } catch (e: Exception) {
            log.warn("Spotlight search failed: ${e.message}")
            null
        }
    }

    /**
     * Use system find/dir command for directory search
     */
    private fun findWithSystemSearch(repoName: String): String? {
        return try {
            val command = if (isWindows) {
                listOf("cmd", "/c", "dir", "/s", "/b", "/ad", homeDir, "|", "findstr", repoName)
            } else {
                listOf("find", homeDir, "-maxdepth", "5", "-type", "d", "-name", repoName)
            }

            val process = ProcessBuilder(command)
                .redirectErrorStream(true)
                .start()

            val result = process.inputStream.bufferedReader().readText().trim()
            process.waitFor(10, TimeUnit.SECONDS)

            result.lines()
                .firstOrNull { it.isNotEmpty() && File(it).exists() }
        } catch (e: Exception) {
            log.warn("Find command failed: ${e.message}")
            null
        }
    }

    /**
     * Validate that a path contains the expected package
     */
    fun validatePackagePath(repoPath: String, packagePath: String): Boolean {
        val fullPath = File(repoPath, packagePath)
        return fullPath.exists()
    }

    /**
     * Find a local server within a repository
     * Checks common locations: src/{id}, packages/{id}
     */
    fun findLocalServer(repoPath: String, serverId: String): String? {
        val candidates = listOf(
            File(repoPath, "src/$serverId"),
            File(repoPath, "packages/$serverId"),
            File(repoPath, serverId)
        )

        return candidates.firstOrNull { it.exists() && it.isDirectory }?.absolutePath
    }
}
