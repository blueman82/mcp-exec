package com.adobe.metamcp.ui.panels

import com.adobe.metamcp.model.CatalogServer
import com.adobe.metamcp.model.LifecycleStatus
import com.adobe.metamcp.model.ServerConfig
import com.adobe.metamcp.services.*
import com.adobe.metamcp.ui.dialogs.LocalServerSetupDialog
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.ui.DocumentAdapter
import com.intellij.ui.SearchTextField
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.table.JBTable
import kotlinx.coroutines.runBlocking
import java.awt.BorderLayout
import java.awt.Color
import java.awt.Component
import java.awt.FlowLayout
import javax.swing.*
import javax.swing.event.DocumentEvent
import javax.swing.table.AbstractTableModel
import javax.swing.table.DefaultTableCellRenderer

/**
 * Catalog Panel - Browse and install MCP servers from GitHub catalog
 */
class CatalogPanel(private val project: Project) : JPanel(BorderLayout()) {

    private val log = Logger.getInstance(CatalogPanel::class.java)
    private val catalogService = CatalogService.getInstance()
    private val configService = ServersConfigService.getInstance()
    private val repoDownloader = RepoDownloader.getInstance()
    private val repoDetector = RepoDetector.getInstance()
    private val localServerParser = LocalServerParser.getInstance()

    private val tableModel = CatalogTableModel()
    private val table = JBTable(tableModel)
    private val searchField = SearchTextField()

    private var allServers: List<CatalogServer> = emptyList()

    init {
        // Configure table
        table.setShowGrid(true)
        table.rowHeight = 32
        table.selectionModel.selectionMode = ListSelectionModel.SINGLE_SELECTION

        // Set column widths
        table.columnModel.getColumn(0).preferredWidth = 150  // Name
        table.columnModel.getColumn(1).preferredWidth = 300  // Description
        table.columnModel.getColumn(2).preferredWidth = 100  // Tags
        table.columnModel.getColumn(3).preferredWidth = 80   // Lifecycle

        // Custom renderer for lifecycle column
        table.columnModel.getColumn(3).cellRenderer = LifecycleCellRenderer()

        // Toolbar
        val toolbar = createToolbar()
        add(toolbar, BorderLayout.NORTH)

        // Table with scroll
        add(JBScrollPane(table), BorderLayout.CENTER)

        // Install button panel
        val buttonPanel = JPanel(FlowLayout(FlowLayout.RIGHT))
        val installButton = JButton("Install Selected")
        installButton.addActionListener { installSelectedServer() }
        buttonPanel.add(installButton)
        add(buttonPanel, BorderLayout.SOUTH)

        // Search filter
        searchField.addDocumentListener(object : DocumentAdapter() {
            override fun textChanged(e: DocumentEvent) {
                filterServers(searchField.text)
            }
        })

        // Initial load
        refreshCatalog()
    }

    private fun createToolbar(): JPanel {
        val toolbar = JPanel(BorderLayout())

        val leftPanel = JPanel(FlowLayout(FlowLayout.LEFT))
        val refreshButton = JButton("Refresh")
        refreshButton.addActionListener { refreshCatalog() }
        leftPanel.add(refreshButton)

        toolbar.add(leftPanel, BorderLayout.WEST)
        toolbar.add(searchField, BorderLayout.CENTER)

        return toolbar
    }

    private fun refreshCatalog() {
        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "Loading Catalog...", true) {
            override fun run(indicator: ProgressIndicator) {
                indicator.isIndeterminate = true
                val result = runBlocking {
                    catalogService.fetchCatalogWithResult()
                }

                SwingUtilities.invokeLater {
                    allServers = result.servers
                    filterServers(searchField.text)

                    // Show error or status message
                    if (result.error != null) {
                        val cacheNote = if (result.fromCache) " (showing cached data)" else ""
                        Messages.showWarningDialog(
                            project,
                            "Failed to fetch catalog: ${result.error}$cacheNote",
                            "Catalog Load Warning"
                        )
                    } else if (result.servers.isEmpty()) {
                        Messages.showInfoMessage(
                            project,
                            "The catalog is empty or could not be loaded.",
                            "Catalog Status"
                        )
                    }
                }
            }

            override fun onThrowable(error: Throwable) {
                SwingUtilities.invokeLater {
                    Messages.showErrorDialog(
                        project,
                        "Failed to load catalog: ${error.message}",
                        "Catalog Error"
                    )
                }
            }
        })
    }

    private fun filterServers(query: String) {
        val filtered = catalogService.filterCatalog(allServers, query)
        tableModel.setServers(filtered)
    }

    private fun installSelectedServer() {
        val selectedRow = table.selectedRow
        if (selectedRow < 0) {
            Messages.showWarningDialog(project, "Please select a server to install.", "No Selection")
            return
        }

        val server = tableModel.getServerAt(selectedRow) ?: return

        if (server.isInternal) {
            installInternalServer(server)
        } else {
            installPublicServer(server)
        }
    }

    private fun installPublicServer(server: CatalogServer) {
        // For public servers, generate the npx/uvx config
        val config = generatePublicServerConfig(server)

        try {
            configService.init() // Ensure config exists
            configService.setServer(server.id, config)
            Messages.showInfoMessage(
                project,
                "Server '${server.name}' has been added to servers.json",
                "Server Installed"
            )
        } catch (e: Exception) {
            Messages.showErrorDialog(project, "Failed to install server: ${e.message}", "Error")
        }
    }

    private fun installInternalServer(server: CatalogServer) {
        // For internal servers, need to:
        // 1. Find or download the repo
        // 2. Build if needed
        // 3. Parse .env.example
        // 4. Show setup dialog

        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "Preparing ${server.name}...", true) {
            override fun run(indicator: ProgressIndicator) {
                indicator.isIndeterminate = true

                // Try to find existing repo or download
                val repoInfo = server.repoHint?.let { repoDownloader.parseRepoIdentifier(it) }
                val repoName = repoInfo?.second ?: "adobe-mcp-servers"
                val repoOwner = repoInfo?.first ?: "Adobe-AIFoundations"

                var repoPath = repoDetector.findRepository(repoName)

                if (repoPath == null) {
                    // Download the repo
                    indicator.text = "Downloading repository..."
                    repoPath = runBlocking {
                        repoDownloader.downloadRepository(repoOwner, repoName) { progress ->
                            indicator.text = progress.message
                        }
                    }
                }

                // Find the server within the repo
                // Use takeIf to properly handle validation - if path invalid, fall through to alternatives
                val serverPath = server.packagePath
                    ?.takeIf { repoDetector.validatePackagePath(repoPath, it) }
                    ?.let { java.io.File(repoPath, it).absolutePath }
                    ?: repoDetector.findLocalServer(repoPath, server.id)
                    ?: repoPath

                log.info("Server path resolved to: $serverPath (packagePath=${server.packagePath}, id=${server.id})")

                // Parse server metadata
                val meta = localServerParser.parseLocalServer(serverPath)

                SwingUtilities.invokeLater {
                    // Show setup dialog
                    val dialog = LocalServerSetupDialog(project, server, serverPath, meta)
                    if (dialog.showAndGet()) {
                        val config = dialog.getServerConfig()
                        if (config != null) {
                            try {
                                configService.init()
                                configService.setServer(server.id, config)
                                Messages.showInfoMessage(
                                    project,
                                    "Server '${server.name}' has been installed successfully.",
                                    "Server Installed"
                                )
                            } catch (e: Exception) {
                                Messages.showErrorDialog(project, "Failed to install: ${e.message}", "Error")
                            }
                        }
                    }
                }
            }

            override fun onThrowable(error: Throwable) {
                SwingUtilities.invokeLater {
                    Messages.showErrorDialog(
                        project,
                        "Failed to prepare server: ${error.message}",
                        "Error"
                    )
                }
            }
        })
    }

    private fun generatePublicServerConfig(server: CatalogServer): ServerConfig {
        val isPython = server.tags.contains("python") || server.tags.contains("uvx")

        return if (isPython) {
            ServerConfig(
                command = "uvx",
                args = listOf(server.id),
                description = server.description
            )
        } else {
            ServerConfig(
                command = "npx",
                args = listOf("-y", server.id),
                description = server.description
            )
        }
    }
}

/**
 * Table model for catalog servers
 */
class CatalogTableModel : AbstractTableModel() {
    private val columns = arrayOf("Name", "Description", "Tags", "Lifecycle")
    private var servers: List<CatalogServer> = emptyList()

    fun setServers(servers: List<CatalogServer>) {
        this.servers = servers
        fireTableDataChanged()
    }

    fun getServerAt(row: Int): CatalogServer? = servers.getOrNull(row)

    override fun getRowCount(): Int = servers.size
    override fun getColumnCount(): Int = columns.size
    override fun getColumnName(column: Int): String = columns[column]

    override fun getValueAt(rowIndex: Int, columnIndex: Int): Any {
        val server = servers[rowIndex]
        return when (columnIndex) {
            0 -> server.name
            1 -> server.description
            2 -> server.tags.joinToString(", ")
            3 -> server.lifecycle ?: ""
            else -> ""
        }
    }
}

/**
 * Cell renderer for lifecycle status badges
 */
class LifecycleCellRenderer : DefaultTableCellRenderer() {
    companion object {
        private val EXPERIMENTAL_BG = Color(255, 243, 205)
        private val EXPERIMENTAL_FG = Color(133, 100, 4)
        private val STABLE_BG = Color(212, 237, 218)
        private val STABLE_FG = Color(21, 87, 36)
        private val DEPRECATED_BG = Color(248, 215, 218)
        private val DEPRECATED_FG = Color(114, 28, 36)
    }

    override fun getTableCellRendererComponent(
        table: JTable, value: Any?, isSelected: Boolean,
        hasFocus: Boolean, row: Int, column: Int
    ): Component {
        super.getTableCellRendererComponent(table, value, isSelected, hasFocus, row, column)

        val lifecycle = LifecycleStatus.fromString(value?.toString())
        val (bg, fg) = when (lifecycle) {
            LifecycleStatus.EXPERIMENTAL -> EXPERIMENTAL_BG to EXPERIMENTAL_FG
            LifecycleStatus.STABLE -> STABLE_BG to STABLE_FG
            LifecycleStatus.DEPRECATED -> DEPRECATED_BG to DEPRECATED_FG
            null -> table.background to table.foreground
        }

        background = if (isSelected) table.selectionBackground else bg
        foreground = if (isSelected && lifecycle == null) table.selectionForeground else fg
        horizontalAlignment = CENTER

        return this
    }
}
