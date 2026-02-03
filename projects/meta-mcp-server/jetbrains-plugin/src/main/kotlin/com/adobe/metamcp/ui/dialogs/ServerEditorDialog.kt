package com.adobe.metamcp.ui.dialogs

import com.adobe.metamcp.model.CommandType
import com.adobe.metamcp.model.ServerConfig
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.DialogWrapper
import com.intellij.openapi.ui.ValidationInfo
import com.intellij.ui.components.JBTextField
import com.intellij.ui.table.JBTable
import java.awt.BorderLayout
import java.awt.CardLayout
import java.awt.Dimension
import java.awt.GridBagConstraints
import java.awt.GridBagLayout
import java.awt.Insets
import javax.swing.*
import javax.swing.table.DefaultTableModel

/**
 * Server Editor Dialog - Add/Edit server configuration
 */
class ServerEditorDialog(
    private val project: Project,
    private val existingName: String?,
    private val existingConfig: ServerConfig?
) : DialogWrapper(project) {

    private val nameField = JBTextField()
    private val typeCombo = JComboBox(CommandType.entries.toTypedArray())
    private val commandField = JBTextField()
    private val argsField = JBTextField()
    private val urlField = JBTextField()
    private val descriptionField = JBTextField()

    // Environment variables table
    private val envTableModel = DefaultTableModel(arrayOf("Key", "Value"), 0)
    private val envTable = JBTable(envTableModel)

    private val cardLayout = CardLayout()
    private val cardPanel = JPanel(cardLayout)

    init {
        title = if (existingName != null) "Edit Server" else "Add Server"
        init()

        // Populate fields if editing
        existingName?.let { nameField.text = it }
        existingConfig?.let { config ->
            val cmdType = CommandType.fromConfig(config)
            typeCombo.selectedItem = cmdType

            when (cmdType) {
                CommandType.URL -> {
                    urlField.text = config.url ?: ""
                    cardLayout.show(cardPanel, "URL")
                }
                CommandType.CUSTOM -> {
                    commandField.text = config.command ?: ""
                    argsField.text = config.args?.joinToString(" ") ?: ""
                    cardLayout.show(cardPanel, "COMMAND")
                }
                else -> {
                    argsField.text = config.args?.joinToString(" ") ?: ""
                    cardLayout.show(cardPanel, "COMMAND")
                }
            }

            descriptionField.text = config.description ?: ""

            // Populate env vars
            config.env?.forEach { (key, value) ->
                envTableModel.addRow(arrayOf(key, value))
            }
        }

        // Add listener to toggle between URL and Command panels
        typeCombo.addActionListener {
            val selected = typeCombo.selectedItem as CommandType
            if (selected == CommandType.URL) {
                cardLayout.show(cardPanel, "URL")
            } else {
                cardLayout.show(cardPanel, "COMMAND")
                if (selected.command != null) {
                    commandField.text = selected.command
                    commandField.isEnabled = false
                } else {
                    commandField.text = ""
                    commandField.isEnabled = true
                }
            }
        }

        // Initialize command field state
        val initialType = typeCombo.selectedItem as CommandType
        if (initialType.command != null && existingConfig == null) {
            commandField.text = initialType.command
            commandField.isEnabled = false
        }
    }

    override fun createCenterPanel(): JComponent {
        val panel = JPanel(GridBagLayout())
        val gbc = GridBagConstraints().apply {
            insets = Insets(4, 4, 4, 4)
            fill = GridBagConstraints.HORIZONTAL
            anchor = GridBagConstraints.WEST
        }

        // Name
        gbc.gridx = 0; gbc.gridy = 0; gbc.weightx = 0.0
        panel.add(JLabel("Name:"), gbc)
        gbc.gridx = 1; gbc.weightx = 1.0
        nameField.preferredSize = Dimension(300, nameField.preferredSize.height)
        panel.add(nameField, gbc)

        // Type
        gbc.gridx = 0; gbc.gridy = 1; gbc.weightx = 0.0
        panel.add(JLabel("Type:"), gbc)
        gbc.gridx = 1; gbc.weightx = 1.0
        typeCombo.renderer = object : DefaultListCellRenderer() {
            override fun getListCellRendererComponent(
                list: JList<*>?, value: Any?, index: Int,
                isSelected: Boolean, cellHasFocus: Boolean
            ): java.awt.Component {
                super.getListCellRendererComponent(list, value, index, isSelected, cellHasFocus)
                text = (value as CommandType).displayName
                return this
            }
        }
        panel.add(typeCombo, gbc)

        // Card panel for URL or Command inputs
        val commandPanel = createCommandPanel()
        val urlPanel = createUrlPanel()
        cardPanel.add(commandPanel, "COMMAND")
        cardPanel.add(urlPanel, "URL")

        gbc.gridx = 0; gbc.gridy = 2; gbc.gridwidth = 2
        panel.add(cardPanel, gbc)

        // Description
        gbc.gridx = 0; gbc.gridy = 3; gbc.gridwidth = 1; gbc.weightx = 0.0
        panel.add(JLabel("Description:"), gbc)
        gbc.gridx = 1; gbc.weightx = 1.0
        panel.add(descriptionField, gbc)

        // Environment Variables
        gbc.gridx = 0; gbc.gridy = 4; gbc.gridwidth = 2
        panel.add(JLabel("Environment Variables:"), gbc)

        gbc.gridy = 5; gbc.weighty = 1.0; gbc.fill = GridBagConstraints.BOTH
        val envPanel = createEnvPanel()
        envPanel.preferredSize = Dimension(400, 150)
        panel.add(envPanel, gbc)

        return panel
    }

    private fun createCommandPanel(): JPanel {
        val panel = JPanel(GridBagLayout())
        val gbc = GridBagConstraints().apply {
            insets = Insets(4, 4, 4, 4)
            fill = GridBagConstraints.HORIZONTAL
            anchor = GridBagConstraints.WEST
        }

        gbc.gridx = 0; gbc.gridy = 0; gbc.weightx = 0.0
        panel.add(JLabel("Command:"), gbc)
        gbc.gridx = 1; gbc.weightx = 1.0
        panel.add(commandField, gbc)

        gbc.gridx = 0; gbc.gridy = 1; gbc.weightx = 0.0
        panel.add(JLabel("Args:"), gbc)
        gbc.gridx = 1; gbc.weightx = 1.0
        argsField.toolTipText = "Space-separated arguments"
        panel.add(argsField, gbc)

        return panel
    }

    private fun createUrlPanel(): JPanel {
        val panel = JPanel(GridBagLayout())
        val gbc = GridBagConstraints().apply {
            insets = Insets(4, 4, 4, 4)
            fill = GridBagConstraints.HORIZONTAL
            anchor = GridBagConstraints.WEST
        }

        gbc.gridx = 0; gbc.gridy = 0; gbc.weightx = 0.0
        panel.add(JLabel("URL:"), gbc)
        gbc.gridx = 1; gbc.weightx = 1.0
        urlField.toolTipText = "HTTP/HTTPS URL for the MCP server"
        panel.add(urlField, gbc)

        return panel
    }

    private fun createEnvPanel(): JPanel {
        val panel = JPanel(BorderLayout())

        envTable.rowHeight = 24
        panel.add(JScrollPane(envTable), BorderLayout.CENTER)

        val buttonPanel = JPanel()
        val addButton = JButton("Add")
        addButton.addActionListener {
            envTableModel.addRow(arrayOf("", ""))
        }
        val removeButton = JButton("Remove")
        removeButton.addActionListener {
            val selected = envTable.selectedRow
            if (selected >= 0) {
                envTableModel.removeRow(selected)
            }
        }
        buttonPanel.add(addButton)
        buttonPanel.add(removeButton)
        panel.add(buttonPanel, BorderLayout.SOUTH)

        return panel
    }

    fun getServerName(): String = nameField.text.trim()

    fun getServerConfig(): ServerConfig? {
        val type = typeCombo.selectedItem as CommandType
        val env = collectEnvVars().takeIf { it.isNotEmpty() }
        val description = descriptionField.text.trim().takeIf { it.isNotEmpty() }

        if (type == CommandType.URL) {
            val url = urlField.text.trim()
            if (url.isEmpty()) return null
            return ServerConfig(url = url, description = description, env = env)
        }

        val command = if (type == CommandType.CUSTOM) {
            val cmd = commandField.text.trim()
            if (cmd.isEmpty()) return null
            cmd
        } else {
            type.command
        }

        val args = parseArgs(argsField.text)
        return ServerConfig(command = command, args = args, description = description, env = env)
    }

    private fun collectEnvVars(): Map<String, String> {
        return (0 until envTableModel.rowCount).mapNotNull { i ->
            val key = envTableModel.getValueAt(i, 0)?.toString()?.trim().orEmpty()
            val value = envTableModel.getValueAt(i, 1)?.toString()?.trim().orEmpty()
            if (key.isNotEmpty()) key to value else null
        }.toMap()
    }

    private fun parseArgs(text: String): List<String>? {
        return text.trim()
            .split(Regex("\\s+"))
            .filter { it.isNotEmpty() }
            .takeIf { it.isNotEmpty() }
    }

    override fun doValidate(): ValidationInfo? {
        if (nameField.text.isBlank()) {
            return ValidationInfo("Server name is required", nameField)
        }

        val type = typeCombo.selectedItem as CommandType
        if (type == CommandType.URL && urlField.text.isBlank()) {
            return ValidationInfo("URL is required", urlField)
        }
        if (type == CommandType.CUSTOM && commandField.text.isBlank()) {
            return ValidationInfo("Command is required", commandField)
        }

        return null
    }
}
