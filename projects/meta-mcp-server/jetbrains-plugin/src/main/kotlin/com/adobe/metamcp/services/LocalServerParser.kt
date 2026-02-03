package com.adobe.metamcp.services

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.Logger
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File

/**
 * Environment variable definition
 */
data class EnvVar(
    val key: String,
    val placeholder: String,
    val optional: Boolean,
    val description: String? = null
)

/**
 * Local server metadata
 */
data class LocalServerMeta(
    val envVars: List<EnvVar>,
    val runtime: Runtime,
    val entryPoint: String,
    val isBuilt: Boolean,
    val hasBuildScript: Boolean
)

enum class Runtime {
    NODE, PYTHON
}

/**
 * Local Server Parser - Extracts configuration metadata from local MCP server packages
 * Port of extension/src/services/LocalServerParser.ts
 */
@Service(Service.Level.APP)
class LocalServerParser {
    private val log = Logger.getInstance(LocalServerParser::class.java)

    private val json = Json {
        ignoreUnknownKeys = true
    }

    companion object {
        fun getInstance(): LocalServerParser =
            ApplicationManager.getApplication().getService(LocalServerParser::class.java)
    }

    /**
     * Parse a local MCP server package to extract configuration metadata
     */
    fun parseLocalServer(packagePath: String): LocalServerMeta {
        val packageDir = File(packagePath)

        // Detect runtime based on file existence
        val hasPackageJson = File(packageDir, "package.json").exists()
        val hasRequirementsTxt = File(packageDir, "requirements.txt").exists()

        val runtime = if (hasPackageJson) Runtime.NODE else Runtime.PYTHON
        val entryPoint = if (runtime == Runtime.NODE) "dist/index.js" else "server.py"

        // Check if already built
        val isBuilt = File(packageDir, entryPoint).exists()

        // Check if build script exists (for node projects)
        var hasBuildScript = false
        if (hasPackageJson) {
            try {
                val pkgJsonFile = File(packageDir, "package.json")
                val pkgJson = json.parseToJsonElement(pkgJsonFile.readText()).jsonObject
                val scripts = pkgJson["scripts"]?.jsonObject
                hasBuildScript = scripts?.containsKey("build") == true
            } catch (e: Exception) {
                log.warn("Failed to parse package.json: ${e.message}")
            }
        }

        // Parse .env.example for required env vars
        val envVars = parseEnvExample(File(packageDir, ".env.example").absolutePath)

        return LocalServerMeta(
            envVars = envVars,
            runtime = runtime,
            entryPoint = entryPoint,
            isBuilt = isBuilt,
            hasBuildScript = hasBuildScript
        )
    }

    /**
     * Parse .env.example file to extract environment variable definitions
     */
    fun parseEnvExample(filePath: String): List<EnvVar> {
        val file = File(filePath)
        if (!file.exists()) {
            return emptyList()
        }

        val vars = mutableListOf<EnvVar>()
        var isOptionalSection = false
        var lastComment = ""

        file.readLines().forEach { line ->
            val trimmedLine = line.trim()
            val lowerLine = trimmedLine.lowercase()

            // Track section headers
            if (lowerLine.contains("# optional") || lowerLine.contains("#optional")) {
                isOptionalSection = true
                return@forEach
            }
            if (lowerLine.contains("# required") || lowerLine.contains("#required")) {
                isOptionalSection = false
                return@forEach
            }

            // Capture inline comments as descriptions
            if (trimmedLine.startsWith("#") &&
                !lowerLine.contains("optional") &&
                !lowerLine.contains("required")
            ) {
                lastComment = trimmedLine.removePrefix("#").trim()
                return@forEach
            }

            // Parse KEY=value lines
            val match = Regex("^([A-Z][A-Z0-9_]*)=(.*)$").find(trimmedLine)
            if (match != null) {
                vars.add(
                    EnvVar(
                        key = match.groupValues[1],
                        placeholder = match.groupValues[2],
                        optional = isOptionalSection,
                        description = lastComment.takeIf { it.isNotEmpty() }
                    )
                )
                lastComment = ""
            }
        }

        return vars
    }

    /**
     * Check if a server package needs to be built
     */
    fun needsBuild(meta: LocalServerMeta): Boolean {
        return !meta.isBuilt && meta.hasBuildScript
    }
}
