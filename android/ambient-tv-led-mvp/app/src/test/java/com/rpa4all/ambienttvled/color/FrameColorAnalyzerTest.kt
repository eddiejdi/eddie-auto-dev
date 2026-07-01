package com.rpa4all.ambienttvled.color

import com.rpa4all.ambienttvled.model.RgbColor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FrameColorAnalyzerTest {
    @Test
    fun averagesSimpleSolidColor() {
        val analyzer = FrameColorAnalyzer(
            AnalysisConfig(
                edgeCropPercent = 0f,
                blackThreshold = 0,
                whiteThreshold = 255,
                smoothingAlpha = 1f,
            ),
        )

        val red = 0x00FF0000
        val pixels = IntArray(16) { red }

        val result = analyzer.analyze(pixels, 4, 4)

        assertEquals(RgbColor(255, 0, 0), result)
    }

    @Test
    fun ignoresBlackBorderBars() {
        val analyzer = FrameColorAnalyzer(
            AnalysisConfig(
                edgeCropPercent = 0f,
                blackThreshold = 15,
                whiteThreshold = 255,
                smoothingAlpha = 1f,
            ),
        )

        val black = 0x00000000
        val green = 0x0000FF00
        val pixels = intArrayOf(
            black, black, black, black,
            black, green, green, black,
            black, green, green, black,
            black, black, black, black,
        )

        val result = analyzer.analyze(pixels, 4, 4)

        assertEquals(RgbColor(0, 255, 0), result)
    }

    @Test
    fun smoothingMovesGradually() {
        val analyzer = FrameColorAnalyzer(
            AnalysisConfig(
                edgeCropPercent = 0f,
                blackThreshold = 0,
                whiteThreshold = 255,
                smoothingAlpha = 0.5f,
            ),
        )

        val red = IntArray(4) { 0x00FF0000 }
        val blue = IntArray(4) { 0x000000FF }

        analyzer.analyze(red, 2, 2)
        val result = analyzer.analyze(blue, 2, 2)

        assertTrue(result.red in 120..135)
        assertTrue(result.blue in 120..135)
        assertEquals(0, result.green)
    }
}
