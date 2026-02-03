package com.adobe.metamcp.ui.panels

import com.adobe.metamcp.model.DetectedTool
import com.adobe.metamcp.model.McpPackageStatus
import com.adobe.metamcp.services.AIToolConfigService
import com.adobe.metamcp.services.CatalogService
import com.adobe.metamcp.util.ShellUtils
import com.intellij.openapi.ide.CopyPasteManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.ui.components.JBScrollPane
import java.awt.*
import java.awt.datatransfer.StringSelection
import java.util.concurrent.TimeUnit
import javax.swing.*

/**
 * Setup Panel - Configure AI tools with meta-mcp
 */
class SetupPanel(private val project: Project) : JPanel(BorderLayout()) {

    private val configService = AIToolConfigService.getInstance()
    private val catalogService = CatalogService.getInstance()

    private var packagesPanel: JPanel? = null
    private var toolsPanel: JPanel? = null
    private var snippetArea: JTextArea? = null

    private var packageStatus: McpPackageStatus = McpPackageStatus()
    private var detectedTools: List<DetectedTool> = emptyList()

    init {
        val mainPanel = JPanel()
        mainPanel.layout = BoxLayout(mainPanel, BoxLayout.Y_AXIS)

        // GitHub Token Section (required for private catalog)
        val githubPanel = createGitHubSection()
        mainPanel.add(githubPanel)
        mainPanel.add(Box.createVerticalStrut(16))

        // Package Installation Section
        packagesPanel = createPackagesSection()
        mainPanel.add(packagesPanel)
        mainPanel.add(Box.createVerticalStrut(16))

        // AI Tools Section
        toolsPanel = createToolsSection()
        mainPanel.add(toolsPanel)
        mainPanel.add(Box.createVerticalStrut(16))

        // Generic Snippet Section
        val snippetPanel = createSnippetSection()
        mainPanel.add(snippetPanel)

        add(JBScrollPane(mainPanel), BorderLayout.CENTER)

        // Toolbar
        val toolbar = JPanel(FlowLayout(FlowLayout.LEFT))
        val refreshButton = JButton("Refresh")
        refreshButton.addActionListener { refresh() }
        toolbar.add(refreshButton)
        add(toolbar, BorderLayout.NORTH)

        // Initial load
        refresh()
    }

    private fun createGitHubSection(): JPanel {
        val panel = JPanel(BorderLayout())
        panel.border = BorderFactory.createTitledBorder("GitHub Access (Required for Catalog)")

        val content = JPanel(GridBagLayout())
        val gbc = GridBagConstraints().apply {
            insets = Insets(4, 8, 4, 8)
            fill = GridBagConstraints.HORIZONTAL
            anchor = GridBagConstraints.WEST
        }

        // Token status
        gbc.gridx = 0; gbc.gridy = 0; gbc.weightx = 0.0
        content.add(JLabel("GitHub Token:"), gbc)

        gbc.gridx = 1; gbc.weightx = 0.5
        val tokenStatus = JLabel(if (catalogService.hasGitHubToken()) "✓ Configured" else "✗ Not configured")
        content.add(tokenStatus, gbc)

        // Token input
        gbc.gridx = 0; gbc.gridy = 1; gbc.weightx = 0.0
        content.add(JLabel("Enter Token:"), gbc)

        gbc.gridx = 1; gbc.weightx = 0.5
        val tokenField = JPasswordField(30)
        content.add(tokenField, gbc)

        gbc.gridx = 2; gbc.weightx = 0.0
        val saveButton = JButton("Save")
        saveButton.addActionListener {
            val token = String(tokenField.password).trim()
            if (token.isNotEmpty()) {
                catalogService.setGitHubToken(token)
                tokenStatus.text = "✓ Configured"
                tokenField.text = ""
                Messages.showInfoMessage(
                    project,
                    "GitHub token saved. You can now access the Catalog.",
                    "Token Saved"
                )
            } else {
                Messages.showWarningDialog(project, "Please enter a valid token.", "Invalid Token")
            }
        }
        content.add(saveButton, gbc)

        // Help text
        gbc.gridx = 0; gbc.gridy = 2; gbc.gridwidth = 3; gbc.weightx = 1.0
        val helpText = JLabel("<html><small>Create a GitHub Personal Access Token with 'repo' scope at: " +
            "<a href='https://github.com/settings/tokens'>github.com/settings/tokens</a></small></html>")
        content.add(helpText, gbc)

        panel.add(content, BorderLayout.CENTER)
        return panel
    }

    private fun createPackagesSection(): JPanel {
        val panel = JPanel(BorderLayout())
        panel.border = BorderFactory.createTitledBorder("MCP Packages")

        val content = JPanel(GridBagLayout())
        val gbc = GridBagConstraints().apply {
            insets = Insets(4, 8, 4, 8)
            fill = GridBagConstraints.HORIZONTAL
            anchor = GridBagConstraints.WEST
        }

        // meta-mcp-server row
        gbc.gridx = 0; gbc.gridy = 0; gbc.weightx = 0.0
        content.add(JLabel("meta-mcp-server:"), gbc)

        gbc.gridx = 1; gbc.weightx = 0.3
        val metaMcpStatus = JLabel("Checking...")
        content.add(metaMcpStatus, gbc)

        gbc.gridx = 2; gbc.weightx = 0.0
        val installMetaMcp = JButton("Install")
        installMetaMcp.addActionListener { installPackage("@justanothermldude/meta-mcp-server") }
        content.add(installMetaMcp, gbc)

        // mcp-exec row
        gbc.gridx = 0; gbc.gridy = 1; gbc.weightx = 0.0
        content.add(JLabel("mcp-exec:"), gbc)

        gbc.gridx = 1; gbc.weightx = 0.3
        val mcpExecStatus = JLabel("Checking...")
        content.add(mcpExecStatus, gbc)

        gbc.gridx = 2; gbc.weightx = 0.0
        val installMcpExec = JButton("Install")
        installMcpExec.addActionListener { installPackage("@justanothermldude/mcp-exec") }
        content.add(installMcpExec, gbc)

        panel.add(content, BorderLayout.CENTER)

        // Store references for updating
        panel.putClientProperty("metaMcpStatus", metaMcpStatus)
        panel.putClientProperty("mcpExecStatus", mcpExecStatus)
        panel.putClientProperty("installMetaMcp", installMetaMcp)
        panel.putClientProperty("installMcpExec", installMcpExec)

        return panel
    }

    private fun createToolsSection(): JPanel {
        val panel = JPanel(BorderLayout())
        panel.border = BorderFactory.createTitledBorder("AI Tools")

        val content = JPanel()
        content.layout = BoxLayout(content, BoxLayout.Y_AXIS)

        // Will be populated in refresh()
        panel.add(content, BorderLayout.CENTER)
        panel.putClientProperty("content", content)

        return panel
    }

    private fun createSnippetSection(): JPanel {
        val panel = JPanel(BorderLayout())
        panel.border = BorderFactory.createTitledBorder("Generic Config Snippet")

        snippetArea = JTextArea(10, 50)
        snippetArea?.isEditable = false
        snippetArea?.font = Font(Font.MONOSPACED, Font.PLAIN, 12)

        panel.add(JBScrollPane(snippetArea), BorderLayout.CENTER)

        val buttonPanel = JPanel(FlowLayout(FlowLayout.RIGHT))
        val copyButton = JButton("Copy to Clipboard")
        copyButton.addActionListener {
            snippetArea?.text?.let { text ->
                CopyPasteManager.getInstance().setContents(StringSelection(text))
                Messages.showInfoMessage(project, "Snippet copied to clipboard", "Copied")
            }
        }
        buttonPanel.add(copyButton)
        panel.add(buttonPanel, BorderLayout.SOUTH)

        return panel
    }

    private fun refresh() {
        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "Detecting packages...", false) {
            override fun run(indicator: ProgressIndicator) {
                packageStatus = configService.detectMcpPackages()
                detectedTools = configService.detectInstalledTools()

                SwingUtilities.invokeLater {
                    updatePackagesUI()
                    updateToolsUI()
                    updateSnippetUI()
                }
            }
        })
    }

    private fun updatePackagesUI() {
        packagesPanel?.let { panel ->
            val metaMcpStatus = panel.getClientProperty("metaMcpStatus") as? JLabel
            val mcpExecStatus = panel.getClientProperty("mcpExecStatus") as? JLabel
            val installMetaMcp = panel.getClientProperty("installMetaMcp") as? JButton
            val installMcpExec = panel.getClientProperty("installMcpExec") as? JButton

            if (packageStatus.metaMcpInstalled) {
                val version = packageStatus.metaMcpVersion ?: "installed"
                val source = packageStatus.metaMcpSource?.name?.lowercase() ?: ""
                metaMcpStatus?.text = "$version ($source)"
                metaMcpStatus?.foreground = Color(21, 87, 36)
                installMetaMcp?.isEnabled = false
            } else {
                metaMcpStatus?.text = "Not installed"
                metaMcpStatus?.foreground = Color(114, 28, 36)
                installMetaMcp?.isEnabled = true
            }

            if (packageStatus.mcpExecInstalled) {
                val version = packageStatus.mcpExecVersion ?: "installed"
                val source = packageStatus.mcpExecSource?.name?.lowercase() ?: ""
                mcpExecStatus?.text = "$version ($source)"
                mcpExecStatus?.foreground = Color(21, 87, 36)
                installMcpExec?.isEnabled = false
            } else {
                mcpExecStatus?.text = "Not installed"
                mcpExecStatus?.foreground = Color(114, 28, 36)
                installMcpExec?.isEnabled = true
            }
        }
    }

    private fun updateToolsUI() {
        toolsPanel?.let { panel ->
            val content = panel.getClientProperty("content") as? JPanel ?: return

            content.removeAll()

            for (detected in detectedTools) {
                val toolPanel = createToolRow(detected)
                content.add(toolPanel)
                content.add(Box.createVerticalStrut(8))
            }

            content.revalidate()
            content.repaint()
        }
    }

    private fun createToolRow(detected: DetectedTool): JPanel {
        val panel = JPanel(FlowLayout(FlowLayout.LEFT))

        // Tool name
        val nameLabel = JLabel(detected.tool.name)
        nameLabel.preferredSize = Dimension(120, nameLabel.preferredSize.height)
        panel.add(nameLabel)

        // Status
        val statusText = when {
            !detected.installed -> "Not installed"
            detected.configured -> "Configured"
            detected.configExists -> "Not configured"
            else -> "No config"
        }
        val statusLabel = JLabel(statusText)
        statusLabel.preferredSize = Dimension(100, statusLabel.preferredSize.height)
        statusLabel.foreground = when {
            !detected.installed -> Color.GRAY
            detected.configured -> Color(21, 87, 36)
            else -> Color(133, 100, 4)
        }
        panel.add(statusLabel)

        // Existing servers count
        if (detected.hasExistingServers) {
            val serversLabel = JLabel("(${detected.existingServerCount} servers)")
            serversLabel.foreground = Color.GRAY
            panel.add(serversLabel)
        }

        // Configure button
        val configureButton = JButton("Configure")
        configureButton.isEnabled = detected.installed &&
            (packageStatus.metaMcpInstalled || packageStatus.mcpExecInstalled)
        configureButton.addActionListener { configureTool(detected) }
        panel.add(configureButton)

        // Package toggle (if configured)
        if (detected.configured) {
            val activePackage = configService.getActivePackage(detected.tool)
            val toggleLabel = JLabel("Active: $activePackage")
            toggleLabel.foreground = Color.GRAY
            panel.add(toggleLabel)
        }

        return panel
    }

    private fun updateSnippetUI() {
        val snippet = configService.generateGenericSnippet()
        snippetArea?.text = snippet.snippet
    }

    private fun installPackage(packageName: String) {
        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "Installing $packageName...", false) {
            override fun run(indicator: ProgressIndicator) {
                try {
                    val command = ShellUtils.buildLoginShellCommand("npm install -g $packageName")
                    val process = ProcessBuilder(command)
                        .redirectErrorStream(true)
                        .start()

                    val output = process.inputStream.bufferedReader().readText()
                    process.waitFor(5, TimeUnit.MINUTES)

                    SwingUtilities.invokeLater {
                        if (process.exitValue() == 0) {
                            Messages.showInfoMessage(project, "$packageName installed successfully", "Success")
                            refresh()
                        } else {
                            Messages.showErrorDialog(project, "Failed to install $packageName:\n$output", "Error")
                        }
                    }
                } catch (e: Exception) {
                    SwingUtilities.invokeLater {
                        Messages.showErrorDialog(project, "Failed to install: ${e.message}", "Error")
                    }
                }
            }
        })
    }

    private fun configureTool(detected: DetectedTool) {
        val result = configService.autoConfigure(detected.tool.id)

        if (result.success) {
            val message = buildString {
                append("${detected.tool.name} has been configured.\n")
                result.configPath?.let { append("Config: $it\n") }
                if (result.migratedCount > 0) {
                    append("Migrated ${result.migratedCount} servers to servers.json\n")
                }
                result.backupPath?.let { append("Backup: $it") }
            }
            Messages.showInfoMessage(project, message, "Configuration Complete")
            refresh()

            // Open both config files in editor (like VS Code extension)
            openConfigFiles(result.configPath, result.serversConfigPath)
        } else {
            Messages.showErrorDialog(project, result.error ?: "Unknown error", "Configuration Failed")
        }
    }

    private fun openConfigFiles(toolConfigPath: String?, serversConfigPath: String?) {
        val fileEditorManager = com.intellij.openapi.fileEditor.FileEditorManager.getInstance(project)
        val localFileSystem = com.intellij.openapi.vfs.LocalFileSystem.getInstance()

        // Open servers.json first
        serversConfigPath?.let { path ->
            localFileSystem.refreshAndFindFileByPath(path)?.let { vFile ->
                fileEditorManager.openFile(vFile, true)
            }
        }

        // Open tool's mcp.json (will be focused)
        toolConfigPath?.let { path ->
            localFileSystem.refreshAndFindFileByPath(path)?.let { vFile ->
                fileEditorManager.openFile(vFile, true)
            }
        }
    }
}
