package com.tandem.reader.service

import android.view.accessibility.AccessibilityNodeInfo

/** Flattens the visible text of an accessibility node tree in traversal (reading) order. */
object VisibleTextExtractor {

    private const val MAX_CHARS = 8000

    fun extract(root: AccessibilityNodeInfo?): String {
        if (root == null) return ""
        val sb = StringBuilder()
        collect(root, sb)
        return sb.toString()
    }

    private fun collect(node: AccessibilityNodeInfo?, sb: StringBuilder) {
        if (node == null || sb.length >= MAX_CHARS) return
        if (node.isVisibleToUser) {
            val text = node.text ?: node.contentDescription
            if (!text.isNullOrBlank()) {
                sb.append(text).append(' ')
            }
        }
        for (i in 0 until node.childCount) {
            collect(node.getChild(i), sb)
        }
    }
}
