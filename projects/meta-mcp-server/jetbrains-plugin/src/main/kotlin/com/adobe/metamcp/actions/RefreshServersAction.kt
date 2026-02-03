package com.adobe.metamcp.actions

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent

/**
 * Action to refresh the servers list
 */
class RefreshServersAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        // This action can be triggered from menu/toolbar
        // The actual refresh is handled by the panels
    }
}
