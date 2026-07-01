package com.rpa4all.ambienttvled.light

data class HomeAssistantConfig(
    val haBaseUrl: String,
    val entityId: String,
    val volumeEntityId: String,
    val vaultUrl: String,
    val vaultBearer: String,
    val haTokenPath: String = "authentik/eddie/home_assistant_token",
) {
    fun hasPlaceholders(): Boolean =
        listOf(haBaseUrl, entityId, vaultBearer).any { it.isBlank() || it.startsWith("YOUR_") }
}
