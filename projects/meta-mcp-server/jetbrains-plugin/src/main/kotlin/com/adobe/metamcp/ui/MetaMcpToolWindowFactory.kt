package com.adobe.metamcp.ui

import com.adobe.metamcp.ui.panels.CatalogPanel
import com.adobe.metamcp.ui.panels.ServersPanel
import com.adobe.metamcp.ui.panels.SetupPanel
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import javax.swing.JTabbedPane

/**
 * Tool Window Factory for Meta-MCP
 * Creates the main tool window with 3 tabs: Servers, Catalog, Setup
 */
class MetaMcpToolWindowFactory : ToolWindowFactory, DumbAware {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val contentFactory = ContentFactory.getInstance()

        // Create tabbed pane
        val tabbedPane = JTabbedPane()

        // Add tabs
        tabbedPane.addTab("Servers", ServersPanel(project))
        tabbedPane.addTab("Catalog", CatalogPanel(project))
        tabbedPane.addTab("Setup", SetupPanel(project))

        // Add to tool window
        val content = contentFactory.createContent(tabbedPane, "", false)
        toolWindow.contentManager.addContent(content)
    }

    override fun shouldBeAvailable(project: Project): Boolean = true
}
