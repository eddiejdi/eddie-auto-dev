package com.rpa4all.ambienttvled

import com.rpa4all.ambienttvled.color.AnalysisConfig
import com.rpa4all.ambienttvled.light.TuyaCloudConfig
import com.rpa4all.ambienttvled.model.CaptureConfig

enum class ControllerMode {
    SIMULATED,
    TUYA_CLOUD,
}

object AppConfig {
    val controllerMode: ControllerMode = ControllerMode.SIMULATED

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

    val tuyaConfig = TuyaCloudConfig(
        baseUrl = "https://openapi.tuyaus.com",
        clientId = "YOUR_CLIENT_ID",
        clientSecret = "YOUR_CLIENT_SECRET",
        deviceId = "YOUR_DEVICE_ID",
        projectId = "YOUR_PROJECT_ID",
    )
}
