package com.rpa4all.ambienttvled.model

data class CaptureConfig(
    val sampleWidth: Int,
    val sampleHeight: Int,
    val maxUpdatesPerSecond: Int,
    val brightness: Int,
    val minColorDistance: Double,
)
