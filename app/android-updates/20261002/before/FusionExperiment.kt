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
        active = true; pending = JSONArray()
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
        } catch (_: Exception) { /* Invalid display output is not sensor evidence. */ }
    }
    @JavascriptInterface @Synchronized
    fun stop() {
        if (!active) return
        manager.unregisterListener(this); handler.removeCallbacks(flush); bleScanner.stop()
        active = false; pending = JSONArray(); recorder.stop(null)
    }
    fun interrupt() {
        stop()
        view?.evaluateJavascript("window.experimentInterrupted && window.experimentInterrupted('화면 중단으로 측정 종료·저장했습니다. 재시작할 때 현재 위치를 지정하세요.')", null)
    }
    fun close() { stop(); bleScanner.close(); view?.removeJavascriptInterface("SensorHost"); view?.destroy(); view = null }
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
            val heading = (Math.toDegrees(angles[0].toDouble()) + 360) % 360
            row.put("sensor", "heading_degrees").put("values", JSONArray(listOf(heading))).put("accuracy", event.accuracy)
        }
        if (pending.length() < 600) pending.put(row)
    }
    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
}
