package com.adobe.metamcp.services

import com.adobe.metamcp.model.*
import com.adobe.metamcp.util.ShellUtils
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.Logger
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * AI Tool Configuration Service - Detects AI tools and manages MCP configuration
 * Port of extension/src/services/AIToolConfigurator.ts
 */
@Service(Service.Level.APP)
class AIToolConfigService {
    private val log = Logger.getInstance(AIToolConfigService::class.java)

    private val json = Json {
        prettyPrint = true
        ignoreUnknownKeys = true
        encodeDefaults = false
    }

    private val homeDir: String = System.getProperty("user.home")

    private val serversConfigPath: String by lazy {
        File(homeDir, ".meta-mcp/servers.json").absolutePath
    }

    companion object {
        fun getInstance(): AIToolConfigService =
            ApplicationManager.getApplication().getService(AIToolConfigService::class.java)

        /**
         * Strip single-line comments from JSON content (handles // comments)
         * Some tools like Junie use JSON with comments which isn't valid JSON
         */
        fun stripJsonComments(content: String): String {
            return content.lines()
                .map { line ->
                    // Find // that's not inside a string
                    var inString = false
                    var i = 0
                    while (i < line.length) {
                        val c = line[i]
                        if (c == '"' && (i == 0 || line[i - 1] != '\\')) {
                            inString = !inString
                        } else if (!inString && c == '/' && i + 1 < line.length && line[i + 1] == '/') {
                            return@map line.substring(0, i).trimEnd()
                        }
                        i++
                    }
                    line
                }
                .joinToString("\n")
        }
    }

    /**
     * Detect all installed AI tools and their configuration status
     */
    fun detectInstalledTools(): List<DetectedTool> {
        return AIToolRegistry.tools.map { tool ->
            val detectFullPath = File(homeDir, tool.detectPath)
            val configFullPath = resolveConfigPath(tool.configPath)

            val installed = detectFullPath.exists()
            val configExists = configFullPath.exists()
            val configured = configExists && isMetaMcpConfigured(tool)

            // Check for existing servers (excluding meta-mcp)
            val existingServers = getExistingServers(tool)
            val hasExistingServers = existingServers.isNotEmpty()
            val existingServerCount = existingServers.size

            DetectedTool(
                tool = tool,
                installed = installed,
                configured = configured,
                configExists = configExists,
                hasExistingServers = hasExistingServers,
                existingServerCount = existingServerCount
            )
        }
    }

    /**
     * Get existing server names from a tool's config (excluding meta-mcp)
     */
    fun getExistingServers(tool: AIToolDefinition): List<String> {
        val configPath = resolveConfigPath(tool.configPath)
        if (!configPath.exists()) return emptyList()

        return try {
            val content = stripJsonComments(configPath.readText()).trim()
            if (content.isEmpty()) return emptyList()
            val config = json.parseToJsonElement(content).jsonObject
            val servers = config[tool.configKey]?.jsonObject ?: return emptyList()
            servers.keys.filter { it != AIToolRegistry.META_MCP_SERVER_NAME && it != AIToolRegistry.MCP_EXEC_SERVER_NAME }
        } catch (e: Exception) {
            log.warn("Failed to read existing servers: ${e.message}")
            emptyList()
        }
    }

    /**
     * Check if meta-mcp is already configured in a tool's config
     */
    fun isMetaMcpConfigured(tool: AIToolDefinition): Boolean {
        val configPath = resolveConfigPath(tool.configPath)
        if (!configPath.exists()) return false

        return try {
            val content = stripJsonComments(configPath.readText()).trim()
            if (content.isEmpty()) return false
            val config = json.parseToJsonElement(content).jsonObject
            val servers = config[tool.configKey]?.jsonObject ?: return false
            AIToolRegistry.META_MCP_SERVER_NAME in servers || AIToolRegistry.MCP_EXEC_SERVER_NAME in servers
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Detect if meta-mcp-server and mcp-exec are installed (global npm)
     */
    fun detectMcpPackages(): McpPackageStatus {
        val metaMcp = checkGlobalNpmPackage("@justanothermldude/meta-mcp-server")
        val mcpExec = checkGlobalNpmPackage("@justanothermldude/mcp-exec")

        return McpPackageStatus(
            metaMcpInstalled = metaMcp != null,
            metaMcpVersion = metaMcp,
            metaMcpSource = if (metaMcp != null) PackageSource.GLOBAL else null,
            mcpExecInstalled = mcpExec != null,
            mcpExecVersion = mcpExec,
            mcpExecSource = if (mcpExec != null) PackageSource.GLOBAL else null
        )
    }

    /**
     * Check if a global npm package is installed, returning its version if found
     */
    private fun checkGlobalNpmPackage(packageName: String): String? {
        return try {
            val result = runCommand("npm", "list", "-g", packageName, "--depth=0", "--json")
            if (result != null) {
                val jsonResult = json.parseToJsonElement(result).jsonObject
                val deps = jsonResult["dependencies"]?.jsonObject
                deps?.get(packageName)?.jsonObject?.get("version")?.jsonPrimitive?.content
            } else null
        } catch (e: Exception) {
            log.debug("$packageName not installed globally")
            null
        }
    }

    /**
     * Generate config snippet for a specific tool
     */
    fun generateSnippet(toolId: String): ConfigSnippet? {
        val tool = AIToolRegistry.getById(toolId) ?: return null
        val serverEntry = buildServerEntryJson(tool, "@justanothermldude/meta-mcp-server")

        val fullConfig = buildJsonObject {
            put(tool.configKey, buildJsonObject {
                put(AIToolRegistry.META_MCP_SERVER_NAME, serverEntry)
            })
        }

        return ConfigSnippet(
            toolId = tool.id,
            toolName = tool.name,
            snippet = json.encodeToString(fullConfig),
            fullConfig = fullConfig
        )
    }

    /**
     * Generate a generic snippet for other platforms
     */
    fun generateGenericSnippet(): ConfigSnippet {
        val metaMcpEntry = buildJsonObject {
            put("command", "npx")
            put("args", buildJsonArray {
                add("-y")
                add("@justanothermldude/meta-mcp-server")
            })
            put("env", buildJsonObject {
                put("SERVERS_CONFIG", serversConfigPath)
            })
        }

        val mcpExecEntry = buildJsonObject {
            put("command", "npx")
            put("args", buildJsonArray {
                add("-y")
                add("@justanothermldude/mcp-exec")
            })
            put("env", buildJsonObject {
                put("SERVERS_CONFIG", serversConfigPath)
            })
        }

        val fullConfig = buildJsonObject {
            put("mcpServers", buildJsonObject {
                put(AIToolRegistry.META_MCP_SERVER_NAME, metaMcpEntry)
                put(AIToolRegistry.MCP_EXEC_SERVER_NAME, mcpExecEntry)
            })
        }

        return ConfigSnippet(
            toolId = "generic",
            toolName = "Other Platforms",
            snippet = json.encodeToString(fullConfig),
            fullConfig = fullConfig
        )
    }

    /**
     * Auto-configure a tool with installed MCP packages
     */
    fun autoConfigure(toolId: String): ConfigureResult {
        val packages = detectMcpPackages()

        if (!packages.metaMcpInstalled && !packages.mcpExecInstalled) {
            return ConfigureResult(
                success = false,
                error = "No MCP packages installed. Install meta-mcp-server or mcp-exec first."
            )
        }

        ensureServersConfig()

        val tool = AIToolRegistry.getById(toolId)
            ?: return ConfigureResult(success = false, error = "Unknown tool: $toolId")

        val configPath = resolveConfigPath(tool.configPath)
        val configDir = configPath.parentFile

        if (!configDir.exists()) {
            configDir.mkdirs()
        }

        // Read existing config or create empty
        var existingConfig = JsonObject(emptyMap())
        var backupPath: String? = null

        if (configPath.exists()) {
            try {
                val content = stripJsonComments(configPath.readText()).trim()
                if (content.isNotEmpty()) {
                    existingConfig = json.parseToJsonElement(content).jsonObject

                    // Create backup
                    backupPath = "${configPath.absolutePath}.bak"
                    configPath.copyTo(File(backupPath), overwrite = true)
                }
            } catch (e: Exception) {
                return ConfigureResult(success = false, error = "Failed to parse existing config: ${e.message}")
            }
        }

        // Get existing servers from tool config
        val existingServers = existingConfig[tool.configKey]?.jsonObject ?: JsonObject(emptyMap())

        // Identify servers to migrate
        val serversToMigrate = existingServers.entries.filter { (name, _) ->
            name != AIToolRegistry.META_MCP_SERVER_NAME && name != AIToolRegistry.MCP_EXEC_SERVER_NAME
        }

        // Migrate servers to servers.json
        var migratedCount = 0
        if (serversToMigrate.isNotEmpty()) {
            try {
                val serversConfigFile = File(serversConfigPath)
                val serversConfig = if (serversConfigFile.exists()) {
                    json.parseToJsonElement(serversConfigFile.readText()).jsonObject.toMutableMap()
                } else {
                    mutableMapOf()
                }

                val mcpServers = (serversConfig["mcpServers"] as? JsonObject)?.toMutableMap()
                    ?: mutableMapOf()

                for ((name, config) in serversToMigrate) {
                    if (name !in mcpServers) {
                        mcpServers[name] = config
                        migratedCount++
                    }
                }

                serversConfig["mcpServers"] = JsonObject(mcpServers)
                serversConfigFile.writeText(json.encodeToString(JsonObject(serversConfig)))
            } catch (e: Exception) {
                return ConfigureResult(success = false, error = "Failed to migrate servers: ${e.message}")
            }
        }

        // Build new tool config with only meta-mcp and mcp-exec
        val newServers = mutableMapOf<String, JsonElement>()

        if (packages.metaMcpInstalled) {
            newServers[AIToolRegistry.META_MCP_SERVER_NAME] = buildServerEntryJson(tool, "@justanothermldude/meta-mcp-server")
        }

        if (packages.mcpExecInstalled) {
            newServers[AIToolRegistry.MCP_EXEC_SERVER_NAME] = buildServerEntryJson(tool, "@justanothermldude/mcp-exec")
        }

        val updatedConfig = existingConfig.toMutableMap()
        updatedConfig[tool.configKey] = JsonObject(newServers)

        try {
            configPath.writeText(json.encodeToString(JsonObject(updatedConfig)))
            return ConfigureResult(
                success = true,
                backupPath = backupPath,
                configPath = configPath.absolutePath,
                serversConfigPath = serversConfigPath,
                toolName = tool.name,
                migratedCount = migratedCount
            )
        } catch (e: Exception) {
            return ConfigureResult(success = false, error = "Failed to write config: ${e.message}")
        }
    }

    /**
     * Get which MCP package is currently active in a tool's config
     */
    fun getActivePackage(tool: AIToolDefinition): String {
        val configPath = resolveConfigPath(tool.configPath)
        if (!configPath.exists()) return "none"

        return try {
            val content = stripJsonComments(configPath.readText()).trim()
            if (content.isEmpty()) return "none"
            val config = json.parseToJsonElement(content).jsonObject
            val servers = config[tool.configKey]?.jsonObject ?: return "none"

            when {
                AIToolRegistry.MCP_EXEC_SERVER_NAME in servers -> "mcp-exec"
                AIToolRegistry.META_MCP_SERVER_NAME in servers -> "meta-mcp"
                else -> "none"
            }
        } catch (e: Exception) {
            "none"
        }
    }

    /**
     * Switch which MCP package is active in a tool's config
     */
    fun switchActivePackage(toolId: String, mode: String): SwitchResult {
        val packages = detectMcpPackages()
        val tool = AIToolRegistry.getById(toolId)
            ?: return SwitchResult(success = false, error = "Unknown tool: $toolId")

        val configPath = resolveConfigPath(tool.configPath)

        var existingConfig = JsonObject(emptyMap())
        if (configPath.exists()) {
            try {
                val content = stripJsonComments(configPath.readText()).trim()
                if (content.isNotEmpty()) {
                    existingConfig = json.parseToJsonElement(content).jsonObject
                }
            } catch (e: Exception) {
                return SwitchResult(success = false, error = "Failed to parse config: ${e.message}")
            }
        }

        val newServers = mutableMapOf<String, JsonElement>()
        if (mode == "meta-mcp") {
            newServers[AIToolRegistry.META_MCP_SERVER_NAME] = buildServerEntryJson(tool, "@justanothermldude/meta-mcp-server")
        } else {
            newServers[AIToolRegistry.MCP_EXEC_SERVER_NAME] = buildServerEntryJson(tool, "@justanothermldude/mcp-exec")
        }

        val updatedConfig = existingConfig.toMutableMap()
        updatedConfig[tool.configKey] = JsonObject(newServers)

        ensureServersConfig()

        val configDir = configPath.parentFile
        if (!configDir.exists()) {
            configDir.mkdirs()
        }

        return try {
            configPath.writeText(json.encodeToString(JsonObject(updatedConfig)))
            SwitchResult(success = true)
        } catch (e: Exception) {
            SwitchResult(success = false, error = "Failed to write config: ${e.message}")
        }
    }

    /**
     * Build an MCP server entry for a tool
     */
    private fun buildServerEntryJson(tool: AIToolDefinition, packageName: String): JsonObject {
        return buildJsonObject {
            put("command", "npx")
            put("args", buildJsonArray {
                add("-y")
                add(packageName)
            })
            put("env", buildJsonObject {
                put("SERVERS_CONFIG", serversConfigPath)
            })
            if (tool.requiresType) {
                put("type", "stdio")
            }
        }
    }

    /**
     * Ensure servers.json exists
     */
    private fun ensureServersConfig() {
        val file = File(serversConfigPath)
        if (file.exists()) return

        val dir = file.parentFile
        if (!dir.exists()) {
            dir.mkdirs()
        }

        file.writeText("""{"mcpServers": {}}""")
    }

    /**
     * Resolve config path (handle ~ and relative paths)
     */
    private fun resolveConfigPath(configPath: String): File {
        return when {
            configPath.startsWith("~") -> File(homeDir, configPath.substring(1))
            File(configPath).isAbsolute -> File(configPath)
            else -> File(homeDir, configPath)
        }
    }

    /**
     * Run a command and return stdout (uses login shell for PATH)
     */
    private fun runCommand(vararg command: String): String? {
        return try {
            val fullCommand = ShellUtils.buildLoginShellCommand(*command)
            val process = ProcessBuilder(fullCommand)
                .redirectErrorStream(true)
                .start()

            val output = process.inputStream.bufferedReader().readText()
            process.waitFor(5, TimeUnit.SECONDS)

            if (process.exitValue() == 0) output else null
        } catch (e: Exception) {
            log.debug("Command failed: ${command.joinToString(" ")}: ${e.message}")
            null
        }
    }
}

data class ConfigureResult(
    val success: Boolean,
    val error: String? = null,
    val backupPath: String? = null,
    val configPath: String? = null,
    val serversConfigPath: String? = null,
    val toolName: String? = null,
    val migratedCount: Int = 0
)

data class SwitchResult(
    val success: Boolean,
    val error: String? = null
)
