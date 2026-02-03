package com.adobe.metamcp.ui.dialogs

import com.adobe.metamcp.model.CatalogServer
import com.adobe.metamcp.model.ServerConfig
import com.adobe.metamcp.services.LocalServerMeta
import com.adobe.metamcp.services.Runtime
import com.adobe.metamcp.util.ShellUtils
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.DialogWrapper
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBTextField
import java.awt.BorderLayout
import java.awt.Dimension
import java.awt.GridBagConstraints
import java.awt.GridBagLayout
import java.awt.Insets
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit
import javax.swing.*

/**
 * Local Server Setup Dialog - Build and configure internal/local MCP servers
 */
class LocalServerSetupDialog(
    private val project: Project,
    private val server: CatalogServer,
    private val serverPath: String,
    private val meta: LocalServerMeta
) : DialogWrapper(project) {

    private val envFields = mutableMapOf<String, JBTextField>()
    private var buildCompleted = meta.isBuilt
    private var buildButton: JButton? = null
    private var statusLabel: JBLabel? = null
    private var buildScheduler: ScheduledExecutorService? = null
    private var buildPoller: ScheduledFuture<*>? = null

    init {
        title = "Setup ${server.name}"
        init()
        updateBuildStatus()
    }

    override fun createCenterPanel(): JComponent {
        val mainPanel = JPanel(BorderLayout(10, 10))

        // Info panel
        val infoPanel = JPanel(GridBagLayout())
        val gbc = GridBagConstraints().apply {
            insets = Insets(4, 4, 4, 4)
            fill = GridBagConstraints.HORIZONTAL
            anchor = GridBagConstraints.WEST
        }

        gbc.gridx = 0; gbc.gridy = 0; gbc.weightx = 0.0
        infoPanel.add(JLabel("Server:"), gbc)
        gbc.gridx = 1; gbc.weightx = 1.0
        infoPanel.add(JLabel(server.name), gbc)

        gbc.gridx = 0; gbc.gridy = 1; gbc.weightx = 0.0
        infoPanel.add(JLabel("Path:"), gbc)
        gbc.gridx = 1; gbc.weightx = 1.0
        val pathLabel = JLabel(serverPath)
        pathLabel.toolTipText = serverPath
        infoPanel.add(pathLabel, gbc)

        gbc.gridx = 0; gbc.gridy = 2; gbc.weightx = 0.0
        infoPanel.add(JLabel("Runtime:"), gbc)
        gbc.gridx = 1; gbc.weightx = 1.0
        infoPanel.add(JLabel(if (meta.runtime == Runtime.NODE) "Node.js" else "Python"), gbc)

        mainPanel.add(infoPanel, BorderLayout.NORTH)

        // Build section (if needed)
        if (meta.hasBuildScript) {
            val buildPanel = createBuildPanel()
            mainPanel.add(buildPanel, BorderLayout.CENTER)
        }

        // Environment variables section
        if (meta.envVars.isNotEmpty()) {
            val envPanel = createEnvPanel()
            mainPanel.add(envPanel, BorderLayout.SOUTH)
        }

        mainPanel.preferredSize = Dimension(500, 400)
        return mainPanel
    }

    private var buildOutputArea: JTextArea? = null
    private var skipBuildButton: JButton? = null

    private fun createBuildPanel(): JPanel {
        val panel = JPanel(BorderLayout(10, 10))
        panel.border = BorderFactory.createTitledBorder("Build")

        val contentPanel = JPanel(GridBagLayout())
        val gbc = GridBagConstraints().apply {
            insets = Insets(4, 4, 4, 4)
            fill = GridBagConstraints.HORIZONTAL
        }

        // Status
        gbc.gridx = 0; gbc.gridy = 0; gbc.weightx = 0.0
        contentPanel.add(JLabel("Status:"), gbc)
        gbc.gridx = 1; gbc.weightx = 1.0; gbc.gridwidth = 2
        statusLabel = JBLabel(if (meta.isBuilt) "Built" else "Not built")
        contentPanel.add(statusLabel, gbc)

        // Entry point info
        gbc.gridx = 0; gbc.gridy = 1; gbc.weightx = 0.0; gbc.gridwidth = 1
        contentPanel.add(JLabel("Looking for:"), gbc)
        gbc.gridx = 1; gbc.weightx = 1.0; gbc.gridwidth = 2
        val entryPointLabel = JLabel(File(serverPath, meta.entryPoint).absolutePath)
        entryPointLabel.toolTipText = "Build completes when this file exists"
        contentPanel.add(entryPointLabel, gbc)

        // Build button
        gbc.gridx = 0; gbc.gridy = 2; gbc.gridwidth = 2; gbc.weightx = 1.0
        buildButton = JButton("Build Server (npm install && npm run build)")
        buildButton?.addActionListener { runBuild() }
        contentPanel.add(buildButton, gbc)

        // Skip build button (for when build is done externally)
        gbc.gridx = 2; gbc.gridwidth = 1; gbc.weightx = 0.0
        skipBuildButton = JButton("Skip (Already Built)")
        skipBuildButton?.toolTipText = "Use if you've already built the server manually"
        skipBuildButton?.addActionListener {
            buildCompleted = true
            updateBuildStatus()
        }
        contentPanel.add(skipBuildButton, gbc)

        // Build output area
        gbc.gridx = 0; gbc.gridy = 3; gbc.gridwidth = 3; gbc.weightx = 1.0
        gbc.fill = GridBagConstraints.BOTH; gbc.weighty = 1.0
        buildOutputArea = JTextArea(8, 50)
        buildOutputArea?.isEditable = false
        buildOutputArea?.font = java.awt.Font("Monospaced", java.awt.Font.PLAIN, 11)
        val scrollPane = JScrollPane(buildOutputArea)
        contentPanel.add(scrollPane, gbc)

        // Note
        gbc.gridy = 4; gbc.weighty = 0.0; gbc.fill = GridBagConstraints.HORIZONTAL
        val noteLabel = JLabel("<html><i>Build output will appear above. OK button enabled after build completes.</i></html>")
        contentPanel.add(noteLabel, gbc)

        panel.add(contentPanel, BorderLayout.CENTER)
        return panel
    }

    private fun createEnvPanel(): JPanel {
        val panel = JPanel(BorderLayout())
        panel.border = BorderFactory.createTitledBorder("Environment Variables")

        val fieldsPanel = JPanel(GridBagLayout())
        val gbc = GridBagConstraints().apply {
            insets = Insets(4, 4, 4, 4)
            fill = GridBagConstraints.HORIZONTAL
            anchor = GridBagConstraints.WEST
        }

        var row = 0
        for (envVar in meta.envVars) {
            val label = if (envVar.optional) "${envVar.key} (optional):" else "${envVar.key}:"

            gbc.gridx = 0; gbc.gridy = row; gbc.weightx = 0.0
            val jLabel = JLabel(label)
            envVar.description?.let { jLabel.toolTipText = it }
            fieldsPanel.add(jLabel, gbc)

            gbc.gridx = 1; gbc.weightx = 1.0
            val field = JBTextField()
            field.text = envVar.placeholder
            envFields[envVar.key] = field
            fieldsPanel.add(field, gbc)

            row++
        }

        panel.add(JScrollPane(fieldsPanel), BorderLayout.CENTER)
        return panel
    }

    private fun runBuild() {
        buildButton?.isEnabled = false
        skipBuildButton?.isEnabled = false
        statusLabel?.text = "Building..."
        buildOutputArea?.text = ""

        // Create .env from .env.example if needed
        val envExampleFile = File(serverPath, ".env.example")
        val envFile = File(serverPath, ".env")
        if (envExampleFile.exists() && !envFile.exists()) {
            envExampleFile.copyTo(envFile)
            appendOutput("Created .env from .env.example\n")
        }

        appendOutput("Running: npm install && npm run build\n")
        appendOutput("Working directory: $serverPath\n")
        appendOutput("Looking for: ${File(serverPath, meta.entryPoint).absolutePath}\n")
        appendOutput("-".repeat(50) + "\n")

        // Run build in terminal
        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                val command = ShellUtils.buildLoginShellCommand("npm install && npm run build")
                val process = ProcessBuilder(command)
                    .directory(File(serverPath))
                    .redirectErrorStream(true)
                    .start()

                // Start polling for build completion
                startBuildPolling()

                // Read output in real-time
                val reader = process.inputStream.bufferedReader()
                var line: String?
                while (reader.readLine().also { line = it } != null) {
                    val outputLine = line
                    SwingUtilities.invokeLater {
                        appendOutput("$outputLine\n")
                    }
                }

                val exitCode = process.waitFor()
                SwingUtilities.invokeLater {
                    appendOutput("-".repeat(50) + "\n")
                    appendOutput("Process exited with code: $exitCode\n")

                    val entryPointFile = File(serverPath, meta.entryPoint)
                    if (entryPointFile.exists()) {
                        appendOutput("✓ Entry point found: ${entryPointFile.absolutePath}\n")
                        buildCompleted = true
                        updateBuildStatus()
                    } else {
                        appendOutput("✗ Entry point NOT found: ${entryPointFile.absolutePath}\n")
                        appendOutput("Click 'Skip (Already Built)' if built elsewhere.\n")
                        statusLabel?.text = "Build finished but entry point not found"
                        buildButton?.isEnabled = true
                        skipBuildButton?.isEnabled = true
                    }
                }

            } catch (e: Exception) {
                SwingUtilities.invokeLater {
                    appendOutput("ERROR: ${e.message}\n")
                    statusLabel?.text = "Build failed: ${e.message}"
                    buildButton?.isEnabled = true
                    skipBuildButton?.isEnabled = true
                }
            }
        }
    }

    private fun appendOutput(text: String) {
        buildOutputArea?.append(text)
        buildOutputArea?.caretPosition = buildOutputArea?.document?.length ?: 0
    }

    private fun startBuildPolling() {
        // Shutdown any existing scheduler
        buildScheduler?.shutdownNow()

        val scheduler = Executors.newSingleThreadScheduledExecutor()
        buildScheduler = scheduler
        val entryPointFile = File(serverPath, meta.entryPoint)

        buildPoller = scheduler.scheduleAtFixedRate({
            if (entryPointFile.exists()) {
                buildCompleted = true
                buildPoller?.cancel(false)
                SwingUtilities.invokeLater {
                    statusLabel?.text = "Build completed!"
                    buildButton?.isEnabled = false
                    updateBuildStatus()
                }
            }
        }, 2, 2, TimeUnit.SECONDS)

        // Cancel after 2 minutes
        scheduler.schedule({
            if (!buildCompleted) {
                buildPoller?.cancel(false)
                SwingUtilities.invokeLater {
                    statusLabel?.text = "Build timed out"
                    buildButton?.isEnabled = true
                }
            }
        }, 2, TimeUnit.MINUTES)
    }

    private fun updateBuildStatus() {
        if (meta.hasBuildScript) {
            buildButton?.isEnabled = !buildCompleted
            skipBuildButton?.isEnabled = !buildCompleted
            statusLabel?.text = if (buildCompleted) "✓ Built" else "Not built"
        }
        // Enable/disable OK button based on build status
        isOKActionEnabled = !meta.hasBuildScript || buildCompleted
    }

    fun getServerConfig(): ServerConfig? {
        if (meta.hasBuildScript && !buildCompleted) {
            return null
        }

        val env = collectEnvVars().takeIf { it.isNotEmpty() }
        val entryPointPath = File(serverPath, meta.entryPoint).absolutePath
        val command = if (meta.runtime == Runtime.NODE) "node" else "python"

        return ServerConfig(
            command = command,
            args = listOf(entryPointPath),
            env = env,
            description = server.description
        )
    }

    private fun collectEnvVars(): Map<String, String> {
        return envFields.mapNotNull { (key, field) ->
            val value = field.text.trim()
            val placeholder = meta.envVars.find { it.key == key }?.placeholder
            if (value.isNotEmpty() && value != placeholder) key to value else null
        }.toMap()
    }

    override fun dispose() {
        buildPoller?.cancel(true)
        buildScheduler?.shutdownNow()
        super.dispose()
    }
}
