package com.rpa4all.ambienttvled.light

import android.util.Log
import com.rpa4all.ambienttvled.model.RgbColor

class SimulatedLightController : LightController {
    override val name: String = "Simulated RGB Controller"

    override suspend fun connect(): Result<Unit> {
        Log.i(TAG, "connect()")
        return Result.success(Unit)
    }

    override suspend fun setColor(color: RgbColor, brightness: Int): Result<Unit> {
        Log.i(TAG, "setColor color=${color.toHexString()} brightness=$brightness")
        return Result.success(Unit)
    }

    override suspend fun turnOff(): Result<Unit> {
        Log.i(TAG, "turnOff()")
        return Result.success(Unit)
    }

    override suspend fun close() {
        Log.i(TAG, "close()")
    }

    companion object {
        private const val TAG = "SimulatedLightController"
    }
}
