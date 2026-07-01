package com.rpa4all.ambienttvled.light

data class TuyaCloudConfig(
    val baseUrl: String,
    val clientId: String,
    val clientSecret: String,
    val deviceId: String,
    val projectId: String,
) {
    fun hasPlaceholders(): Boolean {
        return listOf(baseUrl, clientId, clientSecret, deviceId, projectId).any {
            it.isBlank() || it.startsWith("YOUR_")
        }
    }
}
