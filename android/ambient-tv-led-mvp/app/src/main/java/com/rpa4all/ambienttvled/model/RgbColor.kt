package com.rpa4all.ambienttvled.model

import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.random.Random

data class RgbColor(
    val red: Int,
    val green: Int,
    val blue: Int,
) {
    init {
        require(red in 0..255)
        require(green in 0..255)
        require(blue in 0..255)
    }

    fun toHexString(): String = "#%02X%02X%02X".format(red, green, blue)

    fun toAndroidColor(): Int = (0xFF shl 24) or (red shl 16) or (green shl 8) or blue

    fun blendToward(target: RgbColor, alpha: Float): RgbColor {
        val safeAlpha = alpha.coerceIn(0f, 1f)
        fun channel(from: Int, to: Int): Int =
            (from + ((to - from) * safeAlpha)).roundToInt().coerceIn(0, 255)

        return RgbColor(
            red = channel(red, target.red),
            green = channel(green, target.green),
            blue = channel(blue, target.blue),
        )
    }

    fun distanceTo(other: RgbColor): Double {
        val dr = (red - other.red).toDouble()
        val dg = (green - other.green).toDouble()
        val db = (blue - other.blue).toDouble()
        return (dr.pow(2) + dg.pow(2) + db.pow(2)).pow(0.5)
    }

    fun toHsvPayload(): String {
        val (h, s, v) = toHsv()
        val hue = h.roundToInt()
        val saturation = (s * 1000).roundToInt()
        val value = (v * 1000).roundToInt()
        return """{"h":$hue,"s":$saturation,"v":$value}"""
    }

    private fun toHsv(): Triple<Float, Float, Float> {
        val r = red / 255f
        val g = green / 255f
        val b = blue / 255f

        val max = maxOf(r, g, b)
        val min = minOf(r, g, b)
        val delta = max - min

        val hue = when {
            delta == 0f -> 0f
            max == r -> 60f * (((g - b) / delta) % 6f)
            max == g -> 60f * (((b - r) / delta) + 2f)
            else -> 60f * (((r - g) / delta) + 4f)
        }.let { if (it < 0f) it + 360f else it }

        val saturation = if (max == 0f) 0f else delta / max
        val value = max
        return Triple(hue, saturation, value)
    }

    companion object {
        val BLACK = RgbColor(0, 0, 0)

        fun fromArgb(argb: Int): RgbColor = RgbColor(
            red = (argb shr 16) and 0xFF,
            green = (argb shr 8) and 0xFF,
            blue = argb and 0xFF,
        )

        fun random(): RgbColor = RgbColor(
            red = Random.nextInt(256),
            green = Random.nextInt(256),
            blue = Random.nextInt(256),
        )
    }
}
