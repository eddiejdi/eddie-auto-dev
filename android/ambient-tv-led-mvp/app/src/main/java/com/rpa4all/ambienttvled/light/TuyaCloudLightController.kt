package com.rpa4all.ambienttvled.light

import com.rpa4all.ambienttvled.model.RgbColor
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.util.UUID
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

class TuyaCloudLightController(
    private val config: TuyaCloudConfig,
    private val commandProfile: TuyaCommandProfile,
    private val client: OkHttpClient = OkHttpClient(),
) : LightController {
    override val name: String = "Tuya Cloud RGB Controller"

    private var accessToken: String? = null
    private var tokenExpiresAtEpochMs: Long = 0L

    override suspend fun connect(): Result<Unit> {
        if (config.hasPlaceholders()) {
            return Result.failure(
                IllegalStateException("Replace AppConfig.tuyaConfig placeholders before enabling TUYA_CLOUD."),
            )
        }

        return ensureToken().map { Unit }
    }

    override suspend fun setColor(color: RgbColor, brightness: Int): Result<Unit> {
        val tokenResult = ensureToken()
        if (tokenResult.isFailure) {
            return Result.failure(tokenResult.exceptionOrNull()!!)
        }

        val token = tokenResult.getOrThrow()
        val commands = commandProfile.commandsFor(color, brightness)
        var lastError: Throwable? = null

        for (command in commands) {
            val result = postDpCommand(token, command)
            if (result.isFailure) {
                lastError = result.exceptionOrNull()
            }
        }

        return if (lastError == null) {
            Result.success(Unit)
        } else {
            Result.failure(lastError)
        }
    }

    override suspend fun turnOff(): Result<Unit> {
        val tokenResult = ensureToken()
        if (tokenResult.isFailure) {
            return Result.failure(tokenResult.exceptionOrNull()!!)
        }

        return postDpCommand(
            token = tokenResult.getOrThrow(),
            command = TuyaDpCommand(code = "switch_led", value = false),
        )
    }

    override suspend fun close() = Unit

    private suspend fun ensureToken(): Result<String> = withContext(Dispatchers.IO) {
        val now = System.currentTimeMillis()
        if (!accessToken.isNullOrBlank() && now < tokenExpiresAtEpochMs - 60_000) {
            return@withContext Result.success(accessToken!!)
        }

        val path = "/v1.0/token?grant_type=1"
        val request = signedRequest(
            method = "GET",
            pathWithQuery = path,
            body = "",
            accessToken = null,
        )

        return@withContext execute(request).mapCatching { responseJson ->
            val result = responseJson.getJSONObject("result")
            val token = result.getString("access_token")
            val ttlSeconds = when {
                result.has("expire_time") -> result.getLong("expire_time")
                result.has("expire") -> result.getLong("expire")
                else -> 7200L
            }
            accessToken = token
            tokenExpiresAtEpochMs = now + ttlSeconds * 1000L
            token
        }
    }

    private suspend fun postDpCommand(token: String, command: TuyaDpCommand): Result<Unit> =
        withContext(Dispatchers.IO) {
            val path = "/v1.0/illumination/devices/${config.deviceId}/dps"
            val bodyJson = JSONObject()
                .put("projectId", config.projectId)
                .put("dpCode", command.code)
                .put("dpValue", command.value)
                .toString()

            val request = signedRequest(
                method = "POST",
                pathWithQuery = path,
                body = bodyJson,
                accessToken = token,
            )

            return@withContext execute(request).map { Unit }
        }

    private fun signedRequest(
        method: String,
        pathWithQuery: String,
        body: String,
        accessToken: String?,
    ): Request {
        val timestamp = System.currentTimeMillis().toString()
        val nonce = UUID.randomUUID().toString()
        val bodySha256 = sha256Hex(body)
        val stringToSign = "$method\n$bodySha256\n\n$pathWithQuery"
        val signPayload = if (accessToken == null) {
            config.clientId + timestamp + nonce + stringToSign
        } else {
            config.clientId + accessToken + timestamp + nonce + stringToSign
        }

        val sign = hmacSha256Upper(signPayload, config.clientSecret)
        val requestBuilder = Request.Builder()
            .url(config.baseUrl.trimEnd('/') + pathWithQuery)
            .addHeader("client_id", config.clientId)
            .addHeader("sign", sign)
            .addHeader("sign_method", "HMAC-SHA256")
            .addHeader("t", timestamp)
            .addHeader("nonce", nonce)
            .addHeader("lang", "en")

        if (accessToken != null) {
            requestBuilder.addHeader("access_token", accessToken)
        }

        return if (method == "GET") {
            requestBuilder.get().build()
        } else {
            requestBuilder
                .addHeader("Content-Type", JSON_MEDIA_TYPE.toString())
                .method(method, body.toRequestBody(JSON_MEDIA_TYPE))
                .build()
        }
    }

    private fun execute(request: Request): Result<JSONObject> {
        client.newCall(request).execute().use { response ->
            val rawBody = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                return Result.failure(
                    IllegalStateException("Tuya HTTP ${response.code}: $rawBody"),
                )
            }

            val payload = JSONObject(rawBody)
            val success = payload.optBoolean("success", response.isSuccessful)
            if (!success) {
                val message = payload.optString("msg", "Unknown Tuya error")
                return Result.failure(IllegalStateException(message))
            }

            return Result.success(payload)
        }
    }

    private fun sha256Hex(body: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(body.toByteArray(StandardCharsets.UTF_8))
        return digest.joinToString("") { "%02x".format(it) }
    }

    private fun hmacSha256Upper(payload: String, secret: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        val keySpec = SecretKeySpec(secret.toByteArray(StandardCharsets.UTF_8), "HmacSHA256")
        mac.init(keySpec)
        val signed = mac.doFinal(payload.toByteArray(StandardCharsets.UTF_8))
        return signed.joinToString("") { "%02X".format(it) }
    }

    companion object {
        private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
    }
}
