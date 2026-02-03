package com.adobe.metamcp.services

import com.adobe.metamcp.model.CatalogServer
import com.adobe.metamcp.model.McpServerEntry
import com.intellij.credentialStore.CredentialAttributes
import com.intellij.credentialStore.Credentials
import com.intellij.credentialStore.generateServiceName
import com.intellij.ide.passwordSafe.PasswordSafe
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
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.util.*

/**
 * Catalog Service - Fetches MCP server catalog from GitHub
 * Port of extension/src/services/GitHubCatalogService.ts
 */
@Service(Service.Level.APP)
class CatalogService {
    private val log = Logger.getInstance(CatalogService::class.java)

    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
    }

    private val client = HttpClient(CIO) {
        engine {
            requestTimeout = 30000
        }
    }

    // GitHub repository details
    private val repoOwner = "Adobe-AIFoundations"
    private val registryRepo = "easymcp"
    private val registryBranch = "mcp-registry"
    private val serverListPath = "mcp-server-list.json"

    // Cache
    private var cachedServers: List<CatalogServer>? = null
    private var cacheTimestamp: Long = 0
    private val cacheTtlMs: Long = 5 * 60 * 1000 // 5 minutes

    companion object {
        private const val CREDENTIAL_SERVICE = "Meta-MCP"
        private const val CREDENTIAL_KEY = "github-token"

        fun getInstance(): CatalogService =
            ApplicationManager.getApplication().getService(CatalogService::class.java)
    }

    /**
     * Get stored GitHub token from credential store
     */
    fun getGitHubToken(): String? {
        val credentialAttributes = CredentialAttributes(
            generateServiceName(CREDENTIAL_SERVICE, CREDENTIAL_KEY)
        )
        return PasswordSafe.instance.getPassword(credentialAttributes)
    }

    /**
     * Store GitHub token in credential store
     */
    fun setGitHubToken(token: String) {
        val credentialAttributes = CredentialAttributes(
            generateServiceName(CREDENTIAL_SERVICE, CREDENTIAL_KEY)
        )
        PasswordSafe.instance.set(credentialAttributes, Credentials("", token))
        log.info("GitHub token saved to credential store")
    }

    /**
     * Check if GitHub token is configured
     */
    fun hasGitHubToken(): Boolean = getGitHubToken() != null

    /**
     * Result of fetching catalog
     */
    data class CatalogResult(
        val servers: List<CatalogServer>,
        val error: String? = null,
        val fromCache: Boolean = false
    )

    /**
     * Fetch server catalog from GitHub
     * Uses GitHub's raw content API (no auth required for public repos)
     */
    suspend fun fetchCatalog(token: String? = null): List<CatalogServer> {
        return fetchCatalogWithResult(token).servers
    }

    /**
     * Fetch server catalog with detailed result
     */
    suspend fun fetchCatalogWithResult(token: String? = null): CatalogResult {
        // Return cached data if still valid
        cachedServers?.let { cached ->
            if (System.currentTimeMillis() - cacheTimestamp < cacheTtlMs) {
                log.info("Returning cached catalog (${cached.size} servers)")
                return CatalogResult(cached, fromCache = true)
            }
        }

        // Use provided token, or get from credential store
        val authToken = token ?: getGitHubToken()

        if (authToken == null) {
            log.warn("No GitHub token configured - catalog fetch will fail for private repos")
            return CatalogResult(
                servers = cachedServers ?: emptyList(),
                error = "GitHub token required. Go to Setup tab to configure.",
                fromCache = cachedServers != null
            )
        }

        return withContext(Dispatchers.IO) {
            try {
                // Always use GitHub API with auth for private repos
                val url = "https://api.github.com/repos/$repoOwner/$registryRepo/contents/$serverListPath?ref=$registryBranch"
                log.info("Fetching catalog from: $url")

                val response: HttpResponse = client.get(url) {
                    header(HttpHeaders.Authorization, "Bearer $authToken")
                    header(HttpHeaders.Accept, "application/vnd.github.v3+json")
                    header(HttpHeaders.UserAgent, "Meta-MCP-JetBrains-Plugin")
                }

                if (!response.status.isSuccess()) {
                    val errorMsg = when (response.status.value) {
                        401 -> "Invalid GitHub token. Please update in Setup tab."
                        403 -> "GitHub API rate limit exceeded or token lacks permissions."
                        404 -> "Repository not found or no access. Check token has 'repo' scope."
                        else -> "HTTP ${response.status.value}: ${response.status.description}"
                    }
                    log.warn("Failed to fetch catalog: $errorMsg")
                    return@withContext CatalogResult(
                        servers = cachedServers ?: emptyList(),
                        error = errorMsg,
                        fromCache = cachedServers != null
                    )
                }

                val apiResponse = response.bodyAsText()
                val contentJson = json.parseToJsonElement(apiResponse).jsonObject

                // GitHub API returns base64-encoded content
                val base64Content = contentJson["content"]?.jsonPrimitive?.content
                    ?.replace("\n", "")
                    ?: throw Exception("No content in response")

                val content = String(Base64.getDecoder().decode(base64Content))
                log.info("Received catalog content: ${content.take(200)}...")

                val entries: List<McpServerEntry> = json.decodeFromString(content)

                log.info("Fetched ${entries.size} servers from catalog")

                val servers = entries.map { CatalogServer.fromEntry(it) }
                cachedServers = servers
                cacheTimestamp = System.currentTimeMillis()

                CatalogResult(servers)
            } catch (e: Exception) {
                val errorMsg = e.message ?: e.javaClass.simpleName
                log.error("Failed to fetch catalog: $errorMsg", e)
                CatalogResult(
                    servers = cachedServers ?: emptyList(),
                    error = errorMsg,
                    fromCache = cachedServers != null
                )
            }
        }
    }

    /**
     * Build the URL for fetching catalog
     * Uses raw.githubusercontent.com for unauthenticated access
     */
    private fun buildCatalogUrl(authenticated: Boolean): String {
        return if (authenticated) {
            // Use API endpoint with authentication
            "https://api.github.com/repos/$repoOwner/$registryRepo/contents/$serverListPath?ref=$registryBranch"
        } else {
            // Use raw content URL (no auth needed for public repos)
            "https://raw.githubusercontent.com/$repoOwner/$registryRepo/$registryBranch/$serverListPath"
        }
    }

    /**
     * Search/filter catalog servers
     */
    fun filterCatalog(servers: List<CatalogServer>, query: String): List<CatalogServer> {
        if (query.isBlank()) {
            return servers
        }

        val q = query.lowercase()
        return servers.filter { server ->
            server.name.lowercase().contains(q) ||
                server.description.lowercase().contains(q) ||
                server.tags.any { it.lowercase().contains(q) }
        }
    }

    /**
     * Clear the cache (useful for refresh)
     */
    fun clearCache() {
        cachedServers = null
        cacheTimestamp = 0
        log.info("Catalog cache cleared")
    }

    /**
     * Get cached servers without fetching
     */
    fun getCachedServers(): List<CatalogServer>? = cachedServers
}
