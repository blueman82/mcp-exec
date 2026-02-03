package com.adobe.metamcp.services

import com.adobe.metamcp.model.ServerConfig
import com.adobe.metamcp.model.ServersConfig
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.Logger
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/**
 * Custom exceptions for config operations
 */
class ConfigNotFoundError(configPath: String) : Exception("Config file not found: $configPath")
class ConfigParseError(message: String) : Exception("Failed to parse config: $message")
class ConfigValidationError(message: String) : Exception("Config validation failed: $message")

/**
 * Servers Config Service - CRUD operations for servers.json
 * Port of extension/src/services/ServersConfigManager.ts
 */
/**
 * Listener for config changes
 */
fun interface ConfigChangeListener {
    fun onConfigChanged()
}

@Service(Service.Level.APP)
class ServersConfigService {
    private val log = Logger.getInstance(ServersConfigService::class.java)

    private val json = Json {
        prettyPrint = true
        ignoreUnknownKeys = true
        encodeDefaults = false
    }

    private val changeListeners = mutableListOf<ConfigChangeListener>()

    val configPath: String by lazy {
        val homeDir = System.getProperty("user.home")
        File(homeDir, ".meta-mcp/servers.json").absolutePath
    }

    companion object {
        fun getInstance(): ServersConfigService =
            ApplicationManager.getApplication().getService(ServersConfigService::class.java)
    }

    /**
     * Add a listener for config changes
     */
    fun addChangeListener(listener: ConfigChangeListener) {
        changeListeners.add(listener)
    }

    /**
     * Remove a config change listener
     */
    fun removeChangeListener(listener: ConfigChangeListener) {
        changeListeners.remove(listener)
    }

    /**
     * Notify all listeners of a config change
     */
    private fun notifyListeners() {
        changeListeners.forEach { it.onConfigChanged() }
    }

    /**
     * Check if config file exists
     */
    fun exists(): Boolean = File(configPath).exists()

    /**
     * Load and validate servers config
     */
    fun load(): ServersConfig {
        val file = File(configPath)
        if (!file.exists()) {
            throw ConfigNotFoundError(configPath)
        }

        val rawData = try {
            file.readText()
        } catch (e: Exception) {
            throw ConfigNotFoundError(configPath)
        }

        return try {
            json.decodeFromString<ServersConfig>(rawData)
        } catch (e: Exception) {
            throw ConfigParseError(e.message ?: "Unknown parse error")
        }
    }

    /**
     * Save config with atomic write (temp file + rename)
     */
    fun save(config: ServersConfig) {
        val file = File(configPath)
        val dir = file.parentFile

        if (!dir.exists()) {
            dir.mkdirs()
        }

        val tempFile = File("$configPath.tmp")
        val content = json.encodeToString(config)

        try {
            tempFile.writeText(content)
            Files.move(tempFile.toPath(), file.toPath(), StandardCopyOption.REPLACE_EXISTING)
            log.info("Saved servers config to $configPath")
        } catch (e: Exception) {
            tempFile.delete()
            throw e
        }
    }

    /**
     * Initialize empty config if not exists
     */
    fun init(): ServersConfig {
        if (exists()) {
            return load()
        }

        val config = ServersConfig()
        save(config)
        return config
    }

    /**
     * List all server names
     */
    fun listServers(): List<String> {
        if (!exists()) {
            return emptyList()
        }
        return load().mcpServers.keys.toList()
    }

    /**
     * Get a server config by name
     */
    fun getServer(name: String): ServerConfig? {
        if (!exists()) {
            return null
        }
        return load().mcpServers[name]
    }

    /**
     * Add or update a server
     */
    fun setServer(name: String, serverConfig: ServerConfig) {
        if (!serverConfig.isValid()) {
            throw ConfigValidationError("Either command or url is required")
        }

        val config = if (exists()) load() else ServersConfig()
        config.mcpServers[name] = serverConfig
        save(config)
        log.info("Saved server: $name")
        notifyListeners()
    }

    /**
     * Remove a server
     * @return true if removed, false if not found
     */
    fun removeServer(name: String): Boolean {
        if (!exists()) {
            return false
        }
        val config = load()
        if (name !in config.mcpServers) {
            return false
        }
        config.mcpServers.remove(name)
        save(config)
        log.info("Removed server: $name")
        notifyListeners()
        return true
    }

    /**
     * Enable/disable a server
     */
    fun setServerEnabled(name: String, enabled: Boolean): Boolean {
        val server = getServer(name) ?: return false
        val updatedServer = server.copy(disabled = !enabled)
        setServer(name, updatedServer)
        return true
    }

    /**
     * Rename a server (remove old, add new)
     */
    fun renameServer(oldName: String, newName: String): Boolean {
        val server = getServer(oldName) ?: return false
        if (oldName == newName) return true

        val config = load()
        config.mcpServers.remove(oldName)
        config.mcpServers[newName] = server
        save(config)
        log.info("Renamed server: $oldName -> $newName")
        notifyListeners()
        return true
    }
}
