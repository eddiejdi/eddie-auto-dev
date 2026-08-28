package com.rpa4all.ambienttvled.color

import com.rpa4all.ambienttvled.model.RgbColor

class FrameColorAnalyzer(
    private val config: AnalysisConfig,
) {
    private var lastColor: RgbColor? = null

    fun reset() {
        lastColor = null
    }

    fun analyze(pixels: IntArray, width: Int, height: Int): RgbColor {
        if (width <= 0 || height <= 0 || pixels.isEmpty()) {
            return lastColor ?: RgbColor.BLACK
        }

        val cropX = (width * config.edgeCropPercent).toInt().coerceAtMost(width / 4)
        val cropY = (height * config.edgeCropPercent).toInt().coerceAtMost(height / 4)

        var totalRed = 0L
        var totalGreen = 0L
        var totalBlue = 0L
        var count = 0

        for (y in cropY until (height - cropY)) {
            val rowOffset = y * width
            for (x in cropX until (width - cropX)) {
                val color = RgbColor.fromArgb(pixels[rowOffset + x])
                if (isRejected(color)) {
                    continue
                }

                totalRed += color.red
                totalGreen += color.green
                totalBlue += color.blue
                count += 1
            }
        }

        val rawColor = if (count == 0) {
            lastColor ?: RgbColor.BLACK
        } else {
            RgbColor(
                red = (totalRed / count).toInt().coerceIn(0, 255),
                green = (totalGreen / count).toInt().coerceIn(0, 255),
                blue = (totalBlue / count).toInt().coerceIn(0, 255),
            )
        }

        val smoothed = lastColor?.blendToward(rawColor, config.smoothingAlpha) ?: rawColor
        lastColor = smoothed
        return smoothed
    }

    private fun isRejected(color: RgbColor): Boolean {
        val max = maxOf(color.red, color.green, color.blue)
        val min = minOf(color.red, color.green, color.blue)

        val isBlackBar = max <= config.blackThreshold
        val isNearWhiteOverlay = min >= config.whiteThreshold
        return isBlackBar || isNearWhiteOverlay
    }
}
