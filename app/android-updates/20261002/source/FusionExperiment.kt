package com.example.indoorpositioning

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream

@Composable
internal fun FusionExperimentContent() {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val controller: FusionSensorController = remember { FusionSensorController(context) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) controller.interrupt()
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer); controller.close() }
    }
    AndroidView(modifier = Modifier.fillMaxWidth().height(620.dp), factory = {
        WebView(it).apply {
            settings.javaScriptEnabled = true
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.domStorageEnabled = false
            installSensorHost(controller)
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
                        val mime = when (target.substringAfterLast('.')) { "html" -> "text/html"; "js" -> "text/javascript"; "json" -> "application/json"; else -> "text/plain" }
                        WebResourceResponse(mime, "utf-8", context.assets.open(target))
                    } catch (_: Exception) {
                        WebResourceResponse("text/plain", "utf-8", 404, "Not Found", emptyMap(), ByteArrayInputStream(byteArrayOf()))
                    }
                }
            }
            controller.view = this
            loadUrl("https://appassets.androidplatform.net/assets/fusion-experiment.html")
        }
    })
}

private fun WebView.installSensorHost(controller: FusionSensorController) {
    addJavascriptInterface(controller, "SensorHost")
}

internal class FusionSensorController(private val context: Context) : SensorEventListener {
    var view: WebView? = null
    private val handler = Handler(Looper.getMainLooper())
    private val manager = context.getSystemService(SensorManager::class.java)
    private val recorder = MeasurementRecorder(context)
    @Volatile private var active = false
    private var pending = JSONArray()
    private val apCoordinator = GuidanceApCoordinator()
    private val apMapMatcher = FloorMapMatcher(context)
    private var apMap = MapMatchingSnapshot()
    private var apEnabled = false
    private var heading: Double? = null
    private var headingAt = 0L
    private var latestPose: JSONObject? = null
    private var apRequestPose: JSONObject? = null
    private var apRequestSteps = 0
    private var pendingAp: GuidanceApAnchor? = null
    private var awaitingApDecision: Pair<String, Long>? = null
    private val wifiScanner = WifiFingerprintScanner(context, onRequestStarted = { now ->
        synchronized(this) { if (active) recorder.recordGuidanceEvent("free_ap_requested", JSONObject().put("elapsed_ms", now)) }
    }) { points, fresh, status, requestedAt, resultAt -> synchronized(this) {
        if (active && apEnabled) {
            val moved = if (requestedAt == null) -1 else ((latestPose?.optInt("steps") ?: 0) - apRequestSteps).coerceAtLeast(0)
            recorder.recordWifiScan(points, fresh, status, JSONObject().put("source", if (requestedAt == null) "passive" else "event")
                .put("requested_pose", if (requestedAt == null) JSONObject.NULL else apRequestPose ?: JSONObject.NULL)
                .put("result_pose", latestPose ?: JSONObject.NULL).put("steps_during_scan", if (moved < 0) JSONObject.NULL else moved))
            if (fresh) {
                val scan = wifiScanEnvelope(points, true, resultAt, moved)
                if (pending.length() < 600) pending.put(JSONObject().put("sensor", "wifi").put("time", System.currentTimeMillis()).put("scan", scan))
                pendingAp?.let { awaitingApDecision = it.id to scan.getLong("timestamp") }
            } else pendingAp?.let { apCoordinator.completeEvent(it.id, false, resultAt,
                retryAllowed = requestedAt != null && !status.contains("제한") && !status.contains("권한")) }
            pendingAp = null
            if (pending.length() < 600) pending.put(JSONObject().put("sensor", "wifi_status").put("time", System.currentTimeMillis()).put("status", status))
        }
    }}
    private val bleScanner = BleEnvironmentScanner(context,
        onObservation = { observation -> synchronized(this) {
            if (active) {
                recorder.recordBleObservation(observation)
                if (pending.length() < 600) pending.put(JSONObject()
                    .put("sensor", "ble").put("time", System.currentTimeMillis())
                    .put("observation", JSONObject().put("anonymous_id", observation.anonymousId)
                        .put("rssi_dbm", observation.rssiDbm)))
            }
        }},
        onSnapshot = { snapshot -> synchronized(this) {
            if (active) {
                recorder.recordBleScanStatus(snapshot)
                if (pending.length() < 600) pending.put(JSONObject()
                    .put("sensor", "ble_status").put("time", System.currentTimeMillis())
                    .put("snapshot", JSONObject().put("active", snapshot.active).put("status", snapshot.status)
                        .put("transmitter_count", snapshot.transmitterCount).put("observation_count", snapshot.observationCount)))
            }
        }},
    )
    private val flush = object : Runnable {
        override fun run() {
            synchronized(this@FusionSensorController) {
                if (!active) return
                if (pending.length() > 0) {
                    val json = pending.toString(); pending = JSONArray()
                    view?.evaluateJavascript("window.receiveSensorBatch && window.receiveSensorBatch($json)", null)
                }
            }
            handler.postDelayed(this, 100)
        }
    }
    @JavascriptInterface @Synchronized
    fun start(floor: Int, x: Double): String {
        if (active || floor !in 1..10 || !x.isFinite() || x !in 0.0..135.407)
            return JSONObject().put("ok", false).put("message", "시작값 또는 진행 중 상태를 확인하세요.").toString()
        val result = recorder.start(RecordingLabel(floor.toString(), "비교 시험 x=$x", "자유 이동", "시작", "F${floor}_FUSION_FREE", 0, 0), null)
        if (!result.active) return JSONObject().put("ok", false).put("message", result.status).toString()
        active = true; pending = JSONArray(); apEnabled = false; heading = null; latestPose = null
        pendingAp = null; awaitingApDecision = null; apCoordinator.resetSession()
        apMap = apMapMatcher.configureRoute(floor, if (floor == 1) "1F_MAIN_ENTRANCE_TURN_RIGHT" else "${floor}F_CORE_TO_RIGHT_STAIRS")
        handler.post {
            if (active) {
                listOf(Sensor.TYPE_ACCELEROMETER, Sensor.TYPE_GYROSCOPE, Sensor.TYPE_MAGNETIC_FIELD,
                    Sensor.TYPE_ROTATION_VECTOR, Sensor.TYPE_PRESSURE).forEach { type ->
                    manager.getDefaultSensor(type)?.let { manager.registerListener(this, it, 50000) }
                }
                handler.post(flush)
                bleScanner.start()
            }
        }
        return JSONObject().put("ok", true).put("device", "${Build.MANUFACTURER} ${Build.MODEL}").toString()
    }
    @JavascriptInterface @Synchronized
    fun record(json: String) {
        if (!active || json.length > 32000) return
        try { val record = JSONObject(json)
            if (record.optString("kind") in listOf("fusion_experiment_mode", "derived_fusion", "derived_fusion_final")) recorder.recordDerived(record)
            if (record.optString("kind") == "fusion_experiment_mode") {
                apEnabled = record.optBoolean("ap_enabled", false)
                wifiScanner.passiveEnabled = apEnabled
            }
            if (record.optString("kind") == "derived_fusion") {
                latestPose = record
                record.optJSONObject("wifiDiagnostic")?.let { diagnostic ->
                    awaitingApDecision?.takeIf { it.second == diagnostic.optLong("timestamp", -1) }?.let { waiting ->
                        apCoordinator.completeEvent(waiting.first, diagnostic.optBoolean("applied"), SystemClock.elapsedRealtime())
                        recorder.recordGuidanceEvent("ap_fingerprint_decision", diagnostic)
                        awaitingApDecision = null
                    }
                }
                handler.post { updateAp() }
            }
        } catch (_: Exception) { /* Invalid display output is not sensor evidence. */ }
    }
    @JavascriptInterface @Synchronized
    fun stop() {
        if (!active) return
        manager.unregisterListener(this); handler.removeCallbacks(flush); bleScanner.stop()
        wifiScanner.passiveEnabled = false; wifiScanner.cancelPending(); apCoordinator.stop()
        active = false; apEnabled = false; pendingAp = null; awaitingApDecision = null; pending = JSONArray(); recorder.stop(null)
    }
    fun interrupt() {
        stop()
        view?.evaluateJavascript("window.experimentInterrupted && window.experimentInterrupted('화면 중단으로 측정 종료·저장했습니다. 재시작할 때 현재 위치를 지정하세요.')", null)
    }
    fun close() { stop(); bleScanner.close(); wifiScanner.close(); view?.removeJavascriptInterface("SensorHost"); view?.destroy(); view = null }
    @Synchronized private fun updateAp() {
        if (!active || !apEnabled) return
        val pose = latestPose ?: return
        val now = SystemClock.elapsedRealtime()
        if (!pose.optDouble("x").isFinite() || !pose.optDouble("y").isFinite()) return
        // The shared runtime supports 1..10 even when the legacy baseline matcher does not.
        val map = apMap.copy(available = true, floor = pose.optInt("floor"), tracking = true,
            matchedX = pose.optDouble("x"), matchedY = pose.optDouble("y"), rawX = pose.optDouble("x"))
        val uncertain = pose.optString("reason").startsWith("recovery_required") || pose.optDouble("modeWeight", 1.0) < .55
        val request = apCoordinator.updateWithMotion(map, now, pose.optInt("steps"), heading?.takeIf { now - headingAt <= 1_500L }, uncertain) ?: return
        pendingAp = request; apRequestSteps = pose.optInt("steps"); apRequestPose = JSONObject(pose.toString())
        recorder.recordGuidanceEvent("free_ap_event", JSONObject().put("request_reason", request.reason).put("event_id", request.id)
            .put("event_attempt", request.attempt).put("pose", apRequestPose))
        if (!wifiScanner.scan(reserveEmergency = request.reason != "tracking_uncertain")) {
            apCoordinator.completeEvent(request.id, false, now, retryAllowed = false); pendingAp = null
        }
    }
    @Synchronized override fun onSensorChanged(event: SensorEvent) {
        if (!active) return
        val name = when (event.sensor.type) {
            Sensor.TYPE_ACCELEROMETER -> "accelerometer_mps2"
            Sensor.TYPE_GYROSCOPE -> "gyroscope_radps"
            Sensor.TYPE_MAGNETIC_FIELD -> "magnetic_field_ut"
            Sensor.TYPE_ROTATION_VECTOR -> "rotation_vector"
            Sensor.TYPE_PRESSURE -> "pressure_hpa"
            else -> return
        }
        recorder.recordSample(RawSensorSample(event.timestamp, name, event.values.toList()))
        val time = System.currentTimeMillis() - (SystemClock.elapsedRealtimeNanos() - event.timestamp) / 1000000
        val row = JSONObject().put("sensor", name).put("time", time).put("values", JSONArray(event.values.toList()))
        if (event.sensor.type == Sensor.TYPE_ROTATION_VECTOR) {
            val matrix = FloatArray(9); val angles = FloatArray(3)
            SensorManager.getRotationMatrixFromVector(matrix, event.values); SensorManager.getOrientation(matrix, angles)
            val measuredHeading = (Math.toDegrees(angles[0].toDouble()) + 360) % 360
            heading = measuredHeading; headingAt = event.timestamp / 1_000_000
            row.put("sensor", "heading_degrees").put("values", JSONArray(listOf(measuredHeading))).put("accuracy", event.accuracy)
        }
        if (pending.length() < 600) pending.put(row)
    }
    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
}
