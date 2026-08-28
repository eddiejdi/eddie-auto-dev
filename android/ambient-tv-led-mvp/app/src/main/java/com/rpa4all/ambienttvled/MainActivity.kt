package com.rpa4all.ambienttvled

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Color
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.rpa4all.ambienttvled.capture.ScreenCaptureService
import com.rpa4all.ambienttvled.databinding.ActivityMainBinding
import com.rpa4all.ambienttvled.light.HomeAssistantLightController
import com.rpa4all.ambienttvled.light.SimulatedLightController
import com.rpa4all.ambienttvled.model.RgbColor
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private lateinit var projectionManager: MediaProjectionManager
    private val simulatedController = SimulatedLightController()
    private val haController = HomeAssistantLightController(AppConfig.homeAssistantConfig)

    private val stateReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action != ScreenCaptureService.ACTION_STATE_UPDATE) {
                return
            }

            val status = intent.getStringExtra(ScreenCaptureService.EXTRA_STATUS) ?: "Unknown"
            val controller = intent.getStringExtra(ScreenCaptureService.EXTRA_CONTROLLER_NAME) ?: "-"
            val hex = intent.getStringExtra(ScreenCaptureService.EXTRA_COLOR_HEX) ?: "-"

            binding.statusText.text = "Status: $status"
            binding.controllerText.text = "Controlador: $controller"
            binding.colorText.text = "Cor: $hex"

            val colorInt = intent.getIntExtra(ScreenCaptureService.EXTRA_COLOR_INT, Color.DKGRAY)
            binding.colorSwatch.setBackgroundColor(colorInt)
        }
    }

    private val screenCaptureLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode != RESULT_OK || result.data == null) {
                binding.statusText.text = "Status: Permissao negada"
                return@registerForActivityResult
            }

            val serviceIntent = ScreenCaptureService.newStartIntent(
                context = this,
                resultCode = result.resultCode,
                projectionData = result.data!!,
            )

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        projectionManager = getSystemService(MediaProjectionManager::class.java)

        binding.modeText.text = "Modo: ${AppConfig.controllerMode.name}"
        binding.startCaptureButton.setOnClickListener {
            val captureIntent = projectionManager.createScreenCaptureIntent()
            screenCaptureLauncher.launch(captureIntent)
        }

        binding.stopCaptureButton.setOnClickListener {
            startService(ScreenCaptureService.newStopIntent(this))
        }

        binding.simulateColorButton.setOnClickListener {
            val randomColor = RgbColor.random()
            binding.colorSwatch.setBackgroundColor(randomColor.toAndroidColor())
            binding.colorText.text = "Cor: ${randomColor.toHexString()}"
            binding.statusText.text = "Status: Simulacao local"
            binding.controllerText.text = "Controlador: ${simulatedController.name}"
        }

        binding.volumeUpButton.setOnClickListener {
            binding.volumeStatusText.text = "Volume: enviando Vol+ ao HA..."
            lifecycleScope.launch {
                val result = haController.volumeUp()
                binding.volumeStatusText.text = if (result.isSuccess) {
                    "Volume: Vol+ OK (${AppConfig.homeAssistantConfig.volumeEntityId})"
                } else {
                    "Volume: ERRO — ${result.exceptionOrNull()?.message}"
                }
            }
        }

        binding.volumeDownButton.setOnClickListener {
            binding.volumeStatusText.text = "Volume: enviando Vol- ao HA..."
            lifecycleScope.launch {
                val result = haController.volumeDown()
                binding.volumeStatusText.text = if (result.isSuccess) {
                    "Volume: Vol- OK (${AppConfig.homeAssistantConfig.volumeEntityId})"
                } else {
                    "Volume: ERRO — ${result.exceptionOrNull()?.message}"
                }
            }
        }
    }

    override fun onStart() {
        super.onStart()
        ContextCompat.registerReceiver(
            this,
            stateReceiver,
            IntentFilter(ScreenCaptureService.ACTION_STATE_UPDATE),
            ContextCompat.RECEIVER_NOT_EXPORTED,
        )
    }

    override fun onStop() {
        super.onStop()
        unregisterReceiver(stateReceiver)
    }
}
