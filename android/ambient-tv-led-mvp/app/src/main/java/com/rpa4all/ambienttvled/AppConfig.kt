package com.rpa4all.ambienttvled

import com.rpa4all.ambienttvled.color.AnalysisConfig
import com.rpa4all.ambienttvled.light.HomeAssistantConfig
import com.rpa4all.ambienttvled.light.TuyaCloudConfig
import com.rpa4all.ambienttvled.model.CaptureConfig

enum class ControllerMode {
    SIMULATED,
    TUYA_CLOUD,
    HOME_ASSISTANT,
}

object AppConfig {
    val controllerMode: ControllerMode = ControllerMode.HOME_ASSISTANT

    val captureConfig = CaptureConfig(
        sampleWidth = 64,
        sampleHeight = 36,
        maxUpdatesPerSecond = 6,
        brightness = 80,
        minColorDistance = 10.0,
    )

    val analysisConfig = AnalysisConfig(
        edgeCropPercent = 0.08f,
        blackThreshold = 18,
        whiteThreshold = 245,
        smoothingAlpha = 0.22f,
    )

    // Home Assistant local control — free, no cloud subscription required.
    // entityId: update to the RGB LED strip entity once paired in SmartLife / tuya_local.
    val homeAssistantConfig = HomeAssistantConfig(
        haBaseUrl = "http://192.168.15.2:8123",
        entityId = "light.luz_backlight",
        volumeEntityId = "media_player.chromecastultra6507",
        vaultUrl = "http://192.168.15.2:8088",
        vaultBearer = BuildConfig.VAULT_BEARER,
    )

    val tuyaConfig = TuyaCloudConfig(
        baseUrl = "https://openapi.tuyaus.com",
        clientId = "YOUR_CLIENT_ID",
        clientSecret = "YOUR_CLIENT_SECRET",
        deviceId = "YOUR_DEVICE_ID",
        projectId = "YOUR_PROJECT_ID",
    )
}
