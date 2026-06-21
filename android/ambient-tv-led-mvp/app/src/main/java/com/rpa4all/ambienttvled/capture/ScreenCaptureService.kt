package com.rpa4all.ambienttvled.capture

import android.app.Activity
import android.content.pm.ServiceInfo
import android.app.Service
import android.content.Context
import android.content.Intent
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import com.rpa4all.ambienttvled.AppConfig
import com.rpa4all.ambienttvled.ControllerMode
import com.rpa4all.ambienttvled.color.FrameColorAnalyzer
import com.rpa4all.ambienttvled.light.LightController
import com.rpa4all.ambienttvled.light.SimulatedLightController
import com.rpa4all.ambienttvled.light.TuyaCloudLightController
import com.rpa4all.ambienttvled.light.TuyaCommandProfile
import com.rpa4all.ambienttvled.model.RgbColor
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicBoolean

class ScreenCaptureService : Service() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val analyzer = FrameColorAnalyzer(AppConfig.analysisConfig)
    private val isProcessingFrame = AtomicBoolean(false)

    private var mediaProjection: MediaProjection? = null
    private var imageReader: ImageReader? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var controller: LightController? = null
    private var lastSentAtMs: Long = 0L
    private var lastSentColor: RgbColor? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START_CAPTURE -> {
                val resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, Activity.RESULT_CANCELED)
                val projectionData = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    intent.getParcelableExtra(EXTRA_PROJECTION_DATA, Intent::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    intent.getParcelableExtra(EXTRA_PROJECTION_DATA)
                }

                if (projectionData == null || resultCode != Activity.RESULT_OK) {
                    CaptureStateBroadcaster.send(
                        context = this,
                        status = "Projection permission missing",
                        controllerName = "Unavailable",
                    )
                    stopSelf()
                    return START_NOT_STICKY
                }

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    startForeground(
                        NOTIFICATION_ID,
                        NotificationFactory.build(this),
                        ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION,
                    )
                } else {
                    startForeground(NOTIFICATION_ID, NotificationFactory.build(this))
                }
                startCapture(resultCode, projectionData)
            }

            ACTION_STOP_CAPTURE -> {
                shutdown("Stopped")
                stopSelf()
            }
        }

        return START_STICKY
    }

    override fun onCreate() {
        super.onCreate()
        NotificationFactory.ensureChannel(this)
    }

    override fun onDestroy() {
        shutdown("Service destroyed")
        serviceScope.cancel()
        super.onDestroy()
    }

    private fun startCapture(resultCode: Int, projectionData: Intent) {
        shutdown("Restarting")
        analyzer.reset()
        lastSentAtMs = 0L
        lastSentColor = null

        controller = when (AppConfig.controllerMode) {
            ControllerMode.SIMULATED -> SimulatedLightController()
            ControllerMode.TUYA_CLOUD -> TuyaCloudLightController(
                config = AppConfig.tuyaConfig,
                commandProfile = TuyaCommandProfile.defaultRgbStrip(),
            )
        }

        val lightController = controller ?: return
        serviceScope.launch {
            val result = lightController.connect()
            if (result.isFailure) {
                CaptureStateBroadcaster.send(
                    context = this@ScreenCaptureService,
                    status = "Controller connect failed: ${result.exceptionOrNull()?.message}",
                    controllerName = lightController.name,
                )
            }
        }

        val projectionManager = getSystemService(MediaProjectionManager::class.java)
        mediaProjection = projectionManager.getMediaProjection(resultCode, projectionData)

        val captureConfig = AppConfig.captureConfig
        imageReader = ImageReader.newInstance(
            captureConfig.sampleWidth,
            captureConfig.sampleHeight,
            android.graphics.PixelFormat.RGBA_8888,
            2,
        )

        virtualDisplay = mediaProjection?.createVirtualDisplay(
            "AmbientTvLedMvpCapture",
            captureConfig.sampleWidth,
            captureConfig.sampleHeight,
            resources.displayMetrics.densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader?.surface,
            null,
            null,
        )

        imageReader?.setOnImageAvailableListener({ reader ->
            if (!isProcessingFrame.compareAndSet(false, true)) {
                reader.acquireLatestImage()?.close()
                return@setOnImageAvailableListener
            }

            val image = reader.acquireLatestImage()
            if (image == null) {
                isProcessingFrame.set(false)
                return@setOnImageAvailableListener
            }

            serviceScope.launch {
                try {
                    val frame = BitmapFrameExtractor.extract(
                        image = image,
                        targetWidth = captureConfig.sampleWidth,
                        targetHeight = captureConfig.sampleHeight,
                    )
                    val color = analyzer.analyze(frame.pixels, frame.width, frame.height)
                    maybeSendColor(color)
                } catch (t: Throwable) {
                    CaptureStateBroadcaster.send(
                        context = this@ScreenCaptureService,
                        status = "Capture error: ${t.message}",
                        controllerName = lightController.name,
                    )
                } finally {
                    image.close()
                    isProcessingFrame.set(false)
                }
            }
        }, null)

        CaptureStateBroadcaster.send(
            context = this,
            status = "Capturing",
            controllerName = lightController.name,
        )
    }

    private suspend fun maybeSendColor(color: RgbColor) {
        val captureConfig = AppConfig.captureConfig
        val now = SystemClock.elapsedRealtime()
        val minIntervalMs = 1000L / captureConfig.maxUpdatesPerSecond.coerceAtLeast(1)
        val previous = lastSentColor

        if (previous != null && previous.distanceTo(color) < captureConfig.minColorDistance) {
            CaptureStateBroadcaster.send(
                context = this,
                status = "Capturing (color held)",
                controllerName = controller?.name ?: "-",
                color = previous,
            )
            return
        }

        if (now - lastSentAtMs < minIntervalMs) {
            CaptureStateBroadcaster.send(
                context = this,
                status = "Capturing (rate limited)",
                controllerName = controller?.name ?: "-",
                color = previous ?: color,
            )
            return
        }

        lastSentAtMs = now
        lastSentColor = color

        val result = controller?.setColor(color, captureConfig.brightness)
        val status = if (result?.isSuccess == true) "Capturing" else "Controller update failed"

        CaptureStateBroadcaster.send(
            context = this,
            status = status,
            controllerName = controller?.name ?: "-",
            color = color,
        )
    }

    private fun shutdown(reason: String) {
        imageReader?.setOnImageAvailableListener(null, null)
        imageReader?.close()
        imageReader = null

        virtualDisplay?.release()
        virtualDisplay = null

        mediaProjection?.stop()
        mediaProjection = null

        val lightController = controller
        controller = null
        if (lightController != null) {
            serviceScope.launch {
                lightController.turnOff()
                lightController.close()
            }
        }

        CaptureStateBroadcaster.send(
            context = this,
            status = reason,
            controllerName = lightController?.name ?: "-",
            color = lastSentColor ?: RgbColor.BLACK,
        )

        lastSentAtMs = 0L
        lastSentColor = null
        analyzer.reset()
    }

    companion object {
        const val ACTION_START_CAPTURE = "com.rpa4all.ambienttvled.action.START_CAPTURE"
        const val ACTION_STOP_CAPTURE = "com.rpa4all.ambienttvled.action.STOP_CAPTURE"
        const val ACTION_STATE_UPDATE = "com.rpa4all.ambienttvled.action.STATE_UPDATE"

        const val EXTRA_RESULT_CODE = "extra_result_code"
        const val EXTRA_PROJECTION_DATA = "extra_projection_data"
        const val EXTRA_STATUS = "extra_status"
        const val EXTRA_CONTROLLER_NAME = "extra_controller_name"
        const val EXTRA_COLOR_HEX = "extra_color_hex"
        const val EXTRA_COLOR_INT = "extra_color_int"

        private const val NOTIFICATION_ID = 1001

        fun newStartIntent(
            context: Context,
            resultCode: Int,
            projectionData: Intent,
        ): Intent = Intent(context, ScreenCaptureService::class.java).apply {
            action = ACTION_START_CAPTURE
            putExtra(EXTRA_RESULT_CODE, resultCode)
            putExtra(EXTRA_PROJECTION_DATA, projectionData)
        }

        fun newStopIntent(context: Context): Intent =
            Intent(context, ScreenCaptureService::class.java).apply {
                action = ACTION_STOP_CAPTURE
            }
    }
}
