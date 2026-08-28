package com.rpa4all.ambienttvled.light

import com.rpa4all.ambienttvled.model.RgbColor

data class TuyaDpCommand(
    val code: String,
    val value: Any,
)

class TuyaCommandProfile(
    private val commandBuilder: (RgbColor, Int) -> List<TuyaDpCommand>,
) {
    fun commandsFor(color: RgbColor, brightness: Int): List<TuyaDpCommand> {
        return commandBuilder(color, brightness.coerceIn(1, 1000))
    }

    companion object {
        fun defaultRgbStrip(): TuyaCommandProfile {
            return TuyaCommandProfile { color, brightness ->
                val scaledBrightness = (brightness * 10).coerceIn(10, 1000)
                listOf(
                    TuyaDpCommand(code = "switch_led", value = true),
                    TuyaDpCommand(code = "work_mode", value = "colour"),
                    TuyaDpCommand(code = "bright_value_v2", value = scaledBrightness),
                    TuyaDpCommand(code = "colour_data_v2", value = color.toHsvPayload()),
                )
            }
        }
    }
}
