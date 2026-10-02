package com.example.indoorpositioning

import android.annotation.SuppressLint
import android.content.Context
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.security.MessageDigest

data class RouteFusionSnapshot(
    val ready: Boolean = false,
    val active: Boolean = false,
    val floor: Int? = null,
    val x: Double? = null,
    val y: Double? = null,
    val zoneLabel: String = "모드 4 준비 중",
    val reason: String = "runtime_loading",
    val steps: Int = 0,
    val magneticApplied: Int = 0,
    val magneticEvaluated: Int = 0,
    val magneticStrategy: String = "v2",
    val bleApplied: Int = 0,
    val bleEvaluated: Int = 0,
    val radioEvidence: List<String> = emptyList(),
    val wifiAnchorLabel: String? = null,
    val wifiAnchorWeight: Double? = null,
    val rawJson: String? = null,
)

internal fun anonymousWifiId(value: String): String {
    val digest = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
    return "ap_" + digest.take(5).joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
}

internal fun wifiScanEnvelope(points: List<WifiAccessPointSample>, fresh: Boolean, resultElapsedMs: Long, movedSteps: Int = 0): JSONObject {
    val latestUs = points.maxOfOrNull { it.scanTimestampUs } ?: resultElapsedMs * 1_000
    val measuredWallMs = System.currentTimeMillis() - (resultElapsedMs - latestUs / 1_000).coerceAtLeast(0)
    val rssi = JSONObject()
    points.filter { latestUs - it.scanTimestampUs <= 2_000_000L }.forEach { rssi.put(anonymousWifiId(it.bssid), it.rssiDbm) }
    return JSONObject().put("fresh", fresh).put("timestamp", measuredWallMs).put("rssi", rssi)
        .put("quality", if (movedSteps < 0) .5 else 1.0 / (1.0 + movedSteps))
        .put("steps_during_scan", if (movedSteps < 0) JSONObject.NULL else movedSteps).put("scan_timestamp_us", latestUs)
}

/**
 * Runs the shared JavaScript mode-4 engine for route collection and guidance.
 * The WebView has no user-facing content; Compose attaches it as a 1 dp host so
 * Android and the offline replay use the same navigation, magnetic and radio code.
 */
class RouteFusionController(
    context: Context,
    private val onSnapshot: (RouteFusionSnapshot, JSONObject) -> Unit,
    private val onStatus: (String) -> Unit,
) {
    private val handler = Handler(Looper.getMainLooper())
    private val appContext = context.applicationContext
    private var ready = false
    private var active = false
    private var pendingStart: PendingStart? = null
    private var lastHeading: Int? = null
    private var lastHeadingSentElapsedMs = 0L
    private var lastHeadingSensorTimestampNs = 0L

    private data class PendingStart(val floor: Int, val x: Double, val routeId: String)

    @SuppressLint("SetJavaScriptEnabled")
    val view: WebView = WebView(context).apply {
        settings.javaScriptEnabled = true
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        settings.domStorageEnabled = false
        addJavascriptInterface(Host(), "RouteFusionHost")
        webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest) = true

            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse {
                val url = request.url
                val target = url.path?.removePrefix("/assets/") ?: ""
                if (url.scheme != "https" || url.host != "appassets.androidplatform.net" ||
                    !url.path.orEmpty().startsWith("/assets/") || target.contains("..")) {
                    return WebResourceResponse("text/plain", "utf-8", 403, "Forbidden", emptyMap(), ByteArrayInputStream(byteArrayOf()))
                }
                return try {
                    val mime = when (target.substringAfterLast('.')) {
                        "html" -> "text/html"
                        "js" -> "text/javascript"
                        "json" -> "application/json"
                        else -> "text/plain"
                    }
                    WebResourceResponse(mime, "utf-8", appContext.assets.open(target))
                } catch (_: Exception) {
                    WebResourceResponse("text/plain", "utf-8", 404, "Not Found", emptyMap(), ByteArrayInputStream(byteArrayOf()))
                }
            }
        }
        loadUrl("https://appassets.androidplatform.net/assets/fusion-route-runtime.html")
    }

    fun start(floor: Int, x: Double, routeId: String) {
        active = true
        pendingStart = PendingStart(floor, x, routeId)
        if (ready) startPending()
        else onStatus("모드 4 엔진 로딩 후 자동 시작")
    }

    fun stop() {
        active = false
        pendingStart = null
        evaluate("window.RouteFusion && window.RouteFusion.stop()")
    }

    fun onHeading(headingDegrees: Int?, sensorTimestampNs: Long?): RawSensorSample? {
        if (!active || headingDegrees == null || sensorTimestampNs == null) return null
        val nowNs = SystemClock.elapsedRealtimeNanos()
        if (sensorTimestampNs <= lastHeadingSensorTimestampNs || sensorTimestampNs > nowNs) return null
        val nowElapsedMs = nowNs / 1_000_000L
        if (headingDegrees == lastHeading && nowElapsedMs - lastHeadingSentElapsedMs < 750L) return null
        lastHeading = headingDegrees
        lastHeadingSentElapsedMs = nowElapsedMs
        lastHeadingSensorTimestampNs = sensorTimestampNs
        val sample = RawSensorSample(sensorTimestampNs, "heading_degrees", listOf(headingDegrees.toFloat()))
        val wallTime = System.currentTimeMillis() - (nowNs - sensorTimestampNs) / 1_000_000L
        receive(JSONObject()
            .put("sensor", sample.sensorName)
            .put("time", wallTime)
            .put("values", JSONArray(sample.values)))
        return sample
    }
    fun captureLap(index: Int, pressedAtMs: Long) {
        if (!active) return
        evaluate("window.RouteFusion && window.RouteFusion.captureLap($index,$pressedAtMs)")
    }
    fun onRawSample(sample: RawSensorSample) {
        if (!active || sample.sensorName !in setOf("accelerometer_mps2", "magnetic_field_ut", "pressure_hpa")) return
        val wallTime = System.currentTimeMillis() -
            (SystemClock.elapsedRealtimeNanos() - sample.sensorTimestampNs) / 1_000_000L
        receive(JSONObject()
            .put("sensor", sample.sensorName)
            .put("time", wallTime)
            .put("values", JSONArray(sample.values)))
    }

    fun onBle(observation: BleEnvironmentObservation) {
        if (!active) return
        val wallTime = System.currentTimeMillis() -
            (SystemClock.elapsedRealtimeNanos() - observation.scanTimestampNs) / 1_000_000L
        receive(JSONObject()
            .put("sensor", "ble")
            .put("time", wallTime)
            .put("observation", JSONObject()
                .put("anonymous_id", observation.anonymousId)
                .put("rssi_dbm", observation.rssiDbm)))
    }

    fun onWifi(accessPoints: List<WifiAccessPointSample>, fresh: Boolean, resultElapsedMs: Long, movedSteps: Int = 0): Long? {
        if (!active) return null
        val scan = wifiScanEnvelope(accessPoints, fresh, resultElapsedMs, movedSteps)
        evaluate("window.RouteFusion && window.RouteFusion.wifi(${System.currentTimeMillis()},${scan})")
        return scan.getLong("timestamp")
    }

    fun close() {
        stop()
        view.removeJavascriptInterface("RouteFusionHost")
        view.destroy()
    }

    private fun receive(row: JSONObject) = evaluate("window.RouteFusion && window.RouteFusion.receive(${row})")

    private fun evaluate(script: String) {
        handler.post { if (ready) view.evaluateJavascript(script, null) }
    }

    private fun startPending() {
        val start = pendingStart ?: return
        lastHeading = null
        lastHeadingSentElapsedMs = 0L
        lastHeadingSensorTimestampNs = 0L
        val device = JSONObject.quote("${Build.MANUFACTURER} ${Build.MODEL}")
        val route = JSONObject.quote(start.routeId)
        evaluate("window.RouteFusion && window.RouteFusion.start(${start.floor},${start.x},$device,$route)")
        onStatus(if (start.floor == 4 && start.routeId.contains("TO_RIGHT_STAIRS")) "모드 4 실행 중 · PDR+지도+격자 우선·V2 보조+BLE+AP" else "모드 4 실행 중 · PDR+지도+자기장 V2+BLE+AP")
    }

    private inner class Host {
        @JavascriptInterface
        fun ready() {
            handler.post {
                ready = true
                onStatus("모드 4 준비 완료")
                if (active) startPending()
            }
        }

        @JavascriptInterface
        fun failed(message: String) {
            handler.post { onStatus("모드 4 로드 실패: $message") }
        }

        @JavascriptInterface
        fun publish(json: String) {
            if (!active || json.length > 64_000) return
            try {
                val record = JSONObject(json)
                val sequence = record.optJSONObject("sequenceStats")
                val grid = record.optJSONObject("magneticGridStats")
                val ble = record.optJSONObject("bleStats")
                val radio = record.optJSONArray("radioEvidence")
                val wifiTop = record.optJSONArray("zoneHypotheses")?.optJSONObject(0)
                val snapshot = RouteFusionSnapshot(
                    ready = true,
                    active = true,
                    floor = record.optInt("floor").takeIf { it > 0 },
                    x = record.optDouble("x").takeIf(Double::isFinite),
                    y = record.optDouble("y").takeIf(Double::isFinite),
                    zoneLabel = record.optString("zoneLabel", record.optString("zone", "구역 확인 중")),
                    reason = record.optString("reason", "tracking"),
                    steps = record.optInt("steps", 0),
                    magneticApplied = (sequence?.optInt("applied", 0) ?: 0) + (grid?.optInt("applied", 0) ?: 0),
                    magneticEvaluated = (sequence?.optInt("evaluated", 0) ?: 0) + (grid?.optInt("evaluated", 0) ?: 0),
                    magneticStrategy = record.optString("magneticStrategy", "v2"),
                    bleApplied = ble?.optInt("applied", 0) ?: 0,
                    bleEvaluated = ble?.optInt("evaluated", 0) ?: 0,
                    radioEvidence = buildList {
                        if (radio != null) for (index in 0 until radio.length()) add(radio.optString(index))
                    },
                    wifiAnchorLabel = wifiTop?.optString("anchorLabel")?.takeIf { it.isNotBlank() },
                    wifiAnchorWeight = wifiTop?.optDouble("weight")?.takeIf(Double::isFinite),
                    rawJson = json,
                )
                handler.post { onSnapshot(snapshot, record) }
            } catch (_: Exception) {
                handler.post { onStatus("모드 4 결과 해석 실패") }
            }
        }
    }
}
