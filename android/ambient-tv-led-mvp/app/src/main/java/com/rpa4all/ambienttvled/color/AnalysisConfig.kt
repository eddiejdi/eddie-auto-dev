package com.rpa4all.ambienttvled.color

data class AnalysisConfig(
    val edgeCropPercent: Float,
    val blackThreshold: Int,
    val whiteThreshold: Int,
    val smoothingAlpha: Float,
)
