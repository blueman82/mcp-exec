package com.adobe.metamcp.model

import kotlinx.serialization.json.JsonObject

/**
 * Configuration format type
 */
enum class ConfigFormat {
    MCP_SERVERS,  // Uses "mcpServers" key (JSON)
    SERVERS       // Uses "servers" key (VS Code style JSON)
}

/**
 * AI Tool definition with configuration pattern
 */
data class AIToolDefinition(
    val id: String,
    val name: String,
    val detectPath: String,
    val configPath: String,
    val configFormat: ConfigFormat,
    val configKey: String,
    val requiresType: Boolean = false
)

/**
 * Registry of known AI tools and their MCP configuration patterns
 */
object AIToolRegistry {
    val tools: List<AIToolDefinition> = listOf(
        AIToolDefinition(
            id = "claude",
            name = "Claude",
            detectPath = ".claude.json",
            configPath = ".claude.json",
            configFormat = ConfigFormat.MCP_SERVERS,
            configKey = "mcpServers"
        ),
        AIToolDefinition(
            id = "cursor",
            name = "Cursor",
            detectPath = ".cursor",
            configPath = ".cursor/mcp.json",
            configFormat = ConfigFormat.MCP_SERVERS,
            configKey = "mcpServers"
        ),
        AIToolDefinition(
            id = "droid",
            name = "Droid (Factory)",
            detectPath = ".factory",
            configPath = ".factory/mcp.json",
            configFormat = ConfigFormat.MCP_SERVERS,
            configKey = "mcpServers"
        ),
        AIToolDefinition(
            id = "vscode",
            name = "VS Code",
            detectPath = ".vscode",
            configPath = ".vscode/mcp.json",
            configFormat = ConfigFormat.SERVERS,
            configKey = "servers",
            requiresType = true
        ),
        AIToolDefinition(
            id = "junie",
            name = "Junie (JetBrains)",
            detectPath = ".junie",
            configPath = ".junie/mcp/mcp.json",
            configFormat = ConfigFormat.MCP_SERVERS,
            configKey = "mcpServers"
        )
    )

    fun getById(id: String): AIToolDefinition? = tools.find { it.id == id }

    const val META_MCP_SERVER_NAME = "meta-mcp"
    const val MCP_EXEC_SERVER_NAME = "mcp-exec"
}

/**
 * Detected AI tool with installation/configuration status
 */
data class DetectedTool(
    val tool: AIToolDefinition,
    val installed: Boolean,
    val configured: Boolean,
    val configExists: Boolean,
    val hasExistingServers: Boolean,
    val existingServerCount: Int
)

/**
 * MCP package installation status
 */
data class McpPackageStatus(
    val metaMcpInstalled: Boolean = false,
    val metaMcpVersion: String? = null,
    val metaMcpSource: PackageSource? = null,
    val mcpExecInstalled: Boolean = false,
    val mcpExecVersion: String? = null,
    val mcpExecSource: PackageSource? = null
)

enum class PackageSource {
    GLOBAL,
    LOCAL
}

/**
 * Config snippet for tool configuration
 */
data class ConfigSnippet(
    val toolId: String,
    val toolName: String,
    val snippet: String,
    val fullConfig: JsonObject
)
