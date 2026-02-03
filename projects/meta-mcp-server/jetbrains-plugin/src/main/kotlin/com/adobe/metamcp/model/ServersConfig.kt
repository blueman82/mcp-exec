package com.adobe.metamcp.model

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/**
 * Server configuration - supports both stdio (command) and HTTP (url) transports
 */
@Serializable
data class ServerConfig(
    // Stdio transport
    val type: String? = null,
    val command: String? = null,
    val args: List<String>? = null,
    val env: Map<String, String>? = null,
    // HTTP transport
    val url: String? = null,
    val headers: Map<String, String>? = null,
    // Common
    val disabled: Boolean? = null,
    val description: String? = null,
    val tags: List<String>? = null
) {
    /**
     * Check if config uses URL-based transport
     */
    fun isUrlConfig(): Boolean = url != null

    /**
     * Validate config - either command or url is required
     */
    fun isValid(): Boolean = command != null || url != null
}

/**
 * Root servers.json configuration
 */
@Serializable
data class ServersConfig(
    val mcpServers: MutableMap<String, ServerConfig> = mutableMapOf()
)

/**
 * Server list item for UI display
 */
data class ServerListItem(
    val name: String,
    val config: ServerConfig,
    val connected: Boolean = false
) {
    val displayType: String
        get() = when {
            config.url != null -> "HTTP"
            config.command == "npx" -> "npx"
            config.command == "uvx" -> "uvx"
            config.command == "python" -> "Python"
            config.command == "docker" -> "Docker"
            else -> config.command ?: "Unknown"
        }

    val displayStatus: String
        get() = when {
            config.disabled == true -> "Disabled"
            connected -> "Connected"
            else -> "Ready"
        }
}

/**
 * Command types for the server editor dropdown
 */
enum class CommandType(val displayName: String, val command: String?) {
    NPX("npx (Node.js)", "npx"),
    UVX("uvx (Python)", "uvx"),
    PYTHON("python", "python"),
    DOCKER("docker", "docker"),
    CUSTOM("Custom Command", null),
    URL("HTTP URL", null);

    companion object {
        fun fromConfig(config: ServerConfig): CommandType {
            return when {
                config.url != null -> URL
                config.command == "npx" -> NPX
                config.command == "uvx" -> UVX
                config.command == "python" -> PYTHON
                config.command == "docker" -> DOCKER
                else -> CUSTOM
            }
        }
    }
}
