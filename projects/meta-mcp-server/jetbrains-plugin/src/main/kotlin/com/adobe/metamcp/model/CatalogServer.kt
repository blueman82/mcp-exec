package com.adobe.metamcp.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/**
 * Environment variable definition from catalog
 * Note: 'default' can be string, number, or boolean in JSON
 */
@Serializable
data class McpServerEnvVar(
    val default: JsonElement? = null,
    val optional: Boolean = false
)

/**
 * Raw server entry from GitHub catalog (mcp-server-list.json)
 * Note: Some fields like 'owner' can be string OR array, so we use JsonElement
 */
@Serializable
data class McpServerEntry(
    val name: String,
    val description: String,
    val tags: List<String> = emptyList(),
    val url: String,
    @SerialName("remote_url")
    val remoteUrl: String? = null,
    val icon: String? = null,
    val functions: List<String>? = null,
    val mode: String? = null,
    val lifecycle: String? = null,
    @SerialName("published_on")
    val publishedOn: String? = null,
    @SerialName("server_type")
    val serverType: String? = null,
    @SerialName("package_path")
    val packagePath: String? = null,
    @SerialName("repo_hint")
    val repoHint: String? = null,
    val owner: JsonElement? = null,  // Can be string or array
    val env: Map<String, McpServerEnvVar>? = null,
    @SerialName("base64_icon")
    val base64Icon: String? = null
)

/**
 * Transformed catalog server for UI display
 */
data class CatalogServer(
    val id: String,
    val name: String,
    val description: String,
    val tags: List<String>,
    val repoUrl: String,
    val env: Map<String, McpServerEnvVar>,
    val lifecycle: String?,
    val serverType: String?,
    val packagePath: String?,
    val repoHint: String?,
    val functions: List<String>?
) {
    /**
     * Check if this is an internal/local server requiring build
     */
    val isInternal: Boolean
        get() = serverType == "Internal"

    /**
     * Get lifecycle badge text
     */
    val lifecycleBadge: String?
        get() = lifecycle?.replaceFirstChar { it.uppercase() }

    /**
     * Check if server requires environment variables
     */
    val requiresEnvVars: Boolean
        get() = env.any { !it.value.optional }

    companion object {
        /**
         * Transform raw catalog entry to CatalogServer
         */
        fun fromEntry(entry: McpServerEntry): CatalogServer {
            // Extract ID from URL (last part of path)
            val urlParts = entry.url.split("/")
            val id = urlParts.lastOrNull()?.takeIf { it.isNotEmpty() }
                ?: entry.name.lowercase().replace(Regex("\\s+"), "-")

            return CatalogServer(
                id = id,
                name = entry.name,
                description = entry.description,
                tags = entry.tags,
                repoUrl = entry.url,
                env = entry.env ?: emptyMap(),
                lifecycle = entry.lifecycle,
                serverType = entry.serverType,
                packagePath = entry.packagePath,
                repoHint = entry.repoHint,
                functions = entry.functions
            )
        }
    }
}

/**
 * Lifecycle status for display styling
 */
enum class LifecycleStatus(val displayName: String) {
    EXPERIMENTAL("Experimental"),
    STABLE("Stable"),
    DEPRECATED("Deprecated");

    companion object {
        fun fromString(value: String?): LifecycleStatus? {
            return entries.find { it.name.equals(value, ignoreCase = true) }
        }
    }
}
