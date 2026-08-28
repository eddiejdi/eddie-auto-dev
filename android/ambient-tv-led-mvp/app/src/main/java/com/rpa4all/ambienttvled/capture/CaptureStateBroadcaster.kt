package com.rpa4all.ambienttvled.capture

import android.content.Context
import android.content.Intent
import com.rpa4all.ambienttvled.model.RgbColor

object CaptureStateBroadcaster {
    fun send(
        context: Context,
        status: String,
        controllerName: String,
        color: RgbColor = RgbColor.BLACK,
    ) {
        val intent = Intent(ScreenCaptureService.ACTION_STATE_UPDATE).apply {
            `package` = context.packageName
            putExtra(ScreenCaptureService.EXTRA_STATUS, status)
            putExtra(ScreenCaptureService.EXTRA_CONTROLLER_NAME, controllerName)
            putExtra(ScreenCaptureService.EXTRA_COLOR_HEX, color.toHexString())
            putExtra(ScreenCaptureService.EXTRA_COLOR_INT, color.toAndroidColor())
        }
        context.sendBroadcast(intent)
    }
}
