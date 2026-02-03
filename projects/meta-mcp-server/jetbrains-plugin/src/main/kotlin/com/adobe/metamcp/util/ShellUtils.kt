package com.adobe.metamcp.util

/**
 * Utility functions for shell command execution
 */
object ShellUtils {
    private val isWindows = System.getProperty("os.name").lowercase().contains("win")
    private val isMac = System.getProperty("os.name").lowercase().contains("mac")

    /**
     * Build a command list that wraps a shell command in a login shell.
     * This ensures PATH is loaded from user profile (nvm, homebrew, etc.)
     */
    fun buildLoginShellCommand(command: String): List<String> {
        return when {
            isWindows -> listOf("cmd", "/c", command)
            isMac -> listOf("/bin/zsh", "-l", "-c", command)
            else -> listOf("/bin/bash", "-l", "-c", command)
        }
    }

    /**
     * Build a command list that wraps individual command parts in a login shell.
     * Use this when you have separate command and arguments.
     */
    fun buildLoginShellCommand(vararg command: String): List<String> {
        return when {
            isWindows -> listOf("cmd", "/c") + command.toList()
            isMac -> listOf("/bin/zsh", "-l", "-c", command.joinToString(" "))
            else -> listOf("/bin/bash", "-l", "-c", command.joinToString(" "))
        }
    }
}
