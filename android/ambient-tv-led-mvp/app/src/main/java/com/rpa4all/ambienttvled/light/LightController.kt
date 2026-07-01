package com.rpa4all.ambienttvled.light

import com.rpa4all.ambienttvled.model.RgbColor

interface LightController {
    val name: String

    suspend fun connect(): Result<Unit>

    suspend fun setColor(color: RgbColor, brightness: Int): Result<Unit>

    suspend fun turnOff(): Result<Unit>

    suspend fun close()
}
