package com.rpa4all.ambienttvled.light

import com.rpa4all.ambienttvled.model.RgbColor
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

class HomeAssistantLightController(
    private val config: HomeAssistantConfig,
    private val client: OkHttpClient = OkHttpClient(),
) : LightController {
    override val name: String = "Home Assistant"

    private var haToken: String? = null

    override suspend fun connect(): Result<Unit> {
        if (config.hasPlaceholders()) {
            return Result.failure(
                IllegalStateException("Replace HomeAssistantConfig placeholders in AppConfig."),
            )
        }
        return fetchToken().map { Unit }
    }

    override suspend fun setColor(color: RgbColor, brightness: Int): Result<Unit> {
        val tokenResult = ensureToken()
        if (tokenResult.isFailure) return Result.failure(tokenResult.exceptionOrNull()!!)

        val rgbArray = JSONArray().put(color.red).put(color.green).put(color.blue)
        val body = JSONObject()
            .put("entity_id", config.entityId)
            .put("rgb_color", rgbArray)
            .put("brightness", brightness.coerceIn(0, 255))
            .toString()

        return haPost("services/light/turn_on", tokenResult.getOrThrow(), body).map { Unit }
    }

    suspend fun volumeUp(): Result<Unit> =
        if (config.useNotebookVolume()) notebookPost("up")
        else mediaService("volume_up", config.volumeEntityId)

    suspend fun volumeDown(): Result<Unit> =
        if (config.useNotebookVolume()) notebookPost("down")
        else mediaService("volume_down", config.volumeEntityId)

    suspend fun volumeSet(level: Float): Result<Unit> {
        if (config.useNotebookVolume()) {
            val pct = (level.coerceIn(0f, 1f) * 100).toInt()
            return notebookPost("set?pct=$pct")
        }
        val tokenResult = ensureToken()
        if (tokenResult.isFailure) return Result.failure(tokenResult.exceptionOrNull()!!)
        val body = JSONObject()
            .put("entity_id", config.volumeEntityId)
            .put("volume_level", level.coerceIn(0f, 1f).toDouble())
            .toString()
        return haPost("services/media_player/volume_set", tokenResult.getOrThrow(), body).map { Unit }
    }

    // Returns current volume as 0-100 int, or -1 on error
    suspend fun volumeGet(): Result<Int> = withContext(Dispatchers.IO) {
        if (!config.useNotebookVolume()) return@withContext Result.success(-1)
        val request = Request.Builder()
            .url("${config.notebookVolumeUrl}/volume")
            .get()
            .build()
        runCatching {
            client.newCall(request).execute().use { response ->
                val raw = response.body?.string().orEmpty()
                JSONObject(raw).getInt("volume_pct")
            }
        }
    }

    private suspend fun notebookPost(action: String): Result<Unit> = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("${config.notebookVolumeUrl}/volume/$action")
            .post("".toRequestBody(JSON_MEDIA_TYPE))
            .build()
        runCatching {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) error("Volume server HTTP ${response.code}")
            }
        }
    }

    private suspend fun mediaService(action: String, entityId: String): Result<Unit> {
        val tokenResult = ensureToken()
        if (tokenResult.isFailure) return Result.failure(tokenResult.exceptionOrNull()!!)
        val body = JSONObject().put("entity_id", entityId).toString()
        return haPost("services/media_player/$action", tokenResult.getOrThrow(), body).map { Unit }
    }

    override suspend fun turnOff(): Result<Unit> {
        val tokenResult = ensureToken()
        if (tokenResult.isFailure) return Result.failure(tokenResult.exceptionOrNull()!!)

        val body = JSONObject().put("entity_id", config.entityId).toString()
        return haPost("services/light/turn_off", tokenResult.getOrThrow(), body).map { Unit }
    }

    override suspend fun close() = Unit

    private suspend fun ensureToken(): Result<String> {
        val cached = haToken
        if (!cached.isNullOrBlank()) return Result.success(cached)
        return fetchToken()
    }

    private suspend fun fetchToken(): Result<String> = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("${config.vaultUrl}/secrets/${config.haTokenPath}")
            .addHeader("X-API-Key", config.vaultBearer)
            .get()
            .build()

        runCatching {
            client.newCall(request).execute().use { response ->
                val raw = response.body?.string().orEmpty()
                if (!response.isSuccessful) error("Secrets agent HTTP ${response.code}: $raw")
                val token = JSONObject(raw).getString("value")
                haToken = token
                token
            }
        }
    }

    private suspend fun haPost(
        apiPath: String,
        token: String,
        body: String,
    ): Result<JSONObject> = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("${config.haBaseUrl.trimEnd('/')}/api/$apiPath")
            .addHeader("Authorization", "Bearer $token")
            .addHeader("Content-Type", "application/json")
            .post(body.toRequestBody(JSON_MEDIA_TYPE))
            .build()

        runCatching {
            client.newCall(request).execute().use { response ->
                val raw = response.body?.string().orEmpty()
                if (!response.isSuccessful) error("HA HTTP ${response.code}: $raw")
                if (raw.startsWith("[")) JSONObject().put("result", raw)
                else JSONObject(raw)
            }
        }
    }

    companion object {
        private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
    }
}
