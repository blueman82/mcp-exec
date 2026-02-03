package com.adobe.metamcp.ui.panels

import com.adobe.metamcp.model.CommandType
import com.adobe.metamcp.model.ServerConfig
import com.adobe.metamcp.model.ServerListItem
import com.adobe.metamcp.services.ConfigChangeListener
import com.adobe.metamcp.services.ServersConfigService
import com.adobe.metamcp.ui.dialogs.ServerEditorDialog
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.table.JBTable
import java.awt.BorderLayout
import java.awt.FlowLayout
import javax.swing.*
import javax.swing.table.AbstractTableModel

/**
 * Servers Panel - Displays and manages servers from servers.json
 */
class ServersPanel(private val project: Project) : JPanel(BorderLayout()) {

    private val configService = ServersConfigService.getInstance()
    private val tableModel = ServerTableModel()
    private val table = JBTable(tableModel)

    init {
        // Configure table
        table.setShowGrid(true)
        table.rowHeight = 28
        table.selectionModel.selectionMode = ListSelectionModel.SINGLE_SELECTION

        // Set column widths
        table.columnModel.getColumn(0).preferredWidth = 150  // Name
        table.columnModel.getColumn(1).preferredWidth = 100  // Type
        table.columnModel.getColumn(2).preferredWidth = 80   // Status

        // Toolbar
        val toolbar = createToolbar()
        add(toolbar, BorderLayout.NORTH)

        // Table with scroll
        add(JBScrollPane(table), BorderLayout.CENTER)

        // Double-click to edit
        table.addMouseListener(object : java.awt.event.MouseAdapter() {
            override fun mouseClicked(e: java.awt.event.MouseEvent) {
                if (e.clickCount == 2) {
                    editSelectedServer()
                }
            }
        })

        // Listen for config changes (auto-refresh when servers added from Catalog)
        configService.addChangeListener(ConfigChangeListener {
            SwingUtilities.invokeLater { refreshServers() }
        })

        // Initial load
        refreshServers()
    }

    private fun createToolbar(): JPanel {
        val toolbar = JPanel(FlowLayout(FlowLayout.LEFT))

        val addButton = JButton("Add Server")
        addButton.addActionListener { addServer() }
        toolbar.add(addButton)

        val editButton = JButton("Edit")
        editButton.addActionListener { editSelectedServer() }
        toolbar.add(editButton)

        val deleteButton = JButton("Delete")
        deleteButton.addActionListener { deleteSelectedServer() }
        toolbar.add(deleteButton)

        val refreshButton = JButton("Refresh")
        refreshButton.addActionListener { refreshServers() }
        toolbar.add(refreshButton)

        return toolbar
    }

    private fun refreshServers() {
        ApplicationManager.getApplication().executeOnPooledThread {
            val items = try {
                if (configService.exists()) {
                    val config = configService.load()
                    config.mcpServers.map { (name, serverConfig) ->
                        ServerListItem(
                            name = name,
                            config = serverConfig,
                            connected = serverConfig.disabled != true
                        )
                    }
                } else {
                    emptyList()
                }
            } catch (e: Exception) {
                emptyList()
            }

            SwingUtilities.invokeLater {
                tableModel.setServers(items)
            }
        }
    }

    private fun addServer() {
        val dialog = ServerEditorDialog(project, null, null)
        if (dialog.showAndGet()) {
            val name = dialog.getServerName()
            val config = dialog.getServerConfig()
            if (name.isNotBlank() && config != null) {
                try {
                    configService.setServer(name, config)
                    refreshServers()
                } catch (e: Exception) {
                    Messages.showErrorDialog(project, "Failed to add server: ${e.message}", "Error")
                }
            }
        }
    }

    private fun editSelectedServer() {
        val selectedRow = table.selectedRow
        if (selectedRow < 0) {
            Messages.showWarningDialog(project, "Please select a server to edit.", "No Selection")
            return
        }

        val item = tableModel.getServerAt(selectedRow) ?: return
        val dialog = ServerEditorDialog(project, item.name, item.config)

        if (dialog.showAndGet()) {
            val newName = dialog.getServerName()
            val config = dialog.getServerConfig()
            if (newName.isNotBlank() && config != null) {
                try {
                    if (newName != item.name) {
                        // Name changed - rename
                        configService.renameServer(item.name, newName)
                    }
                    configService.setServer(newName, config)
                    refreshServers()
                } catch (e: Exception) {
                    Messages.showErrorDialog(project, "Failed to update server: ${e.message}", "Error")
                }
            }
        }
    }

    private fun deleteSelectedServer() {
        val selectedRow = table.selectedRow
        if (selectedRow < 0) {
            Messages.showWarningDialog(project, "Please select a server to delete.", "No Selection")
            return
        }

        val item = tableModel.getServerAt(selectedRow) ?: return

        val result = Messages.showYesNoDialog(
            project,
            "Are you sure you want to delete server '${item.name}'?",
            "Delete Server",
            Messages.getQuestionIcon()
        )

        if (result == Messages.YES) {
            try {
                configService.removeServer(item.name)
                refreshServers()
            } catch (e: Exception) {
                Messages.showErrorDialog(project, "Failed to delete server: ${e.message}", "Error")
            }
        }
    }
}

/**
 * Table model for servers list
 */
class ServerTableModel : AbstractTableModel() {
    private val columns = arrayOf("Name", "Type", "Status")
    private var servers: List<ServerListItem> = emptyList()

    fun setServers(servers: List<ServerListItem>) {
        this.servers = servers
        fireTableDataChanged()
    }

    fun getServerAt(row: Int): ServerListItem? {
        return servers.getOrNull(row)
    }

    override fun getRowCount(): Int = servers.size

    override fun getColumnCount(): Int = columns.size

    override fun getColumnName(column: Int): String = columns[column]

    override fun getValueAt(rowIndex: Int, columnIndex: Int): Any {
        val server = servers[rowIndex]
        return when (columnIndex) {
            0 -> server.name
            1 -> server.displayType
            2 -> server.displayStatus
            else -> ""
        }
    }
}
