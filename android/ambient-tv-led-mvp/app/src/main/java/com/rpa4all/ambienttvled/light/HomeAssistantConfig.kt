package com.rpa4all.ambienttvled.light

data class HomeAssistantConfig(
    val haBaseUrl: String,
    val entityId: String,
    val volumeEntityId: String,
    val vaultUrl: String,
    val vaultBearer: String,
    val haTokenPath: String = "authentik/eddie/home_assistant_token",
    // Direct volume server on the notebook (bypasses HA for volume control)
    val notebookVolumeUrl: String = "",
) {
    fun hasPlaceholders(): Boolean =
        listOf(haBaseUrl, entityId, vaultBearer).any { it.isBlank() || it.startsWith("YOUR_") }

    fun useNotebookVolume(): Boolean = notebookVolumeUrl.isNotBlank()
}
