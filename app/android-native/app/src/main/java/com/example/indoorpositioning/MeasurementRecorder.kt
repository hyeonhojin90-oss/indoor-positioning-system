package com.example.indoorpositioning

import android.content.ContentValues
import android.content.Context
import android.os.Build
import android.os.SystemClock
import android.provider.MediaStore
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class RecordingLabel(
    val floor: String,
    val location: String,
    val destination: String,
    val event: String,
    val routeId: String,
    val lapIndex: Int,
    val lapTotal: Int,
)

data class RecordingSnapshot(
    val active: Boolean = false,
    val fileName: String? = null,
    val samples: Int = 0,
    val labels: Int = 0,
    val status: String = "보정 데이터 측정 대기",
)

data class RawSensorSample(
    val sensorTimestampNs: Long,
    val sensorName: String,
    val values: List<Float>,
)

internal fun zoneIdForLabel(location: String): String? = when (location.substringBefore(" · ").trim()) {
    "오른쪽 강의실 라인" -> "main_right"
    "왼쪽 강의실 라인" -> "main_left"
    "오른쪽 계단 앞" -> "stairs_right"
    "왼쪽 계단 앞" -> "stairs_left"
    "오른쪽 계단 내부" -> "stairs_right_inside"
    "왼쪽 계단 내부" -> "stairs_left_inside"
    "2107 진입 전" -> "f2_2107_entry_main"
    "책상공간 진입 전" -> "f2_study_entry_main"
    "기둥·TDM 사이" -> "f2_extension_entry"
    "책상공간 내" -> "f2_study_inside" // Legacy label.
    "책상공간 내부" -> "f2_study_inside"
    "TDM 옆" -> "f2_extension_tdm_side"
    "2104-1 앞" -> "f2_extension_2104_1"
    "2104-2 앞" -> "f2_extension_2104_2"
    "2105-1 앞" -> "f2_extension_2105_1"
    "2105-2 앞" -> "f2_extension_2105_2"
    "3203 문 정면" -> "f3_extension_entry"
    "코어 교차점" -> "core_junction"
    else -> null // Legacy generic corridor labels do not establish a side.
}

internal fun schemaVersionForRouteId(routeId: String): Int = when {
    routeId.contains("MULTISENSOR_RADIO_ZONE_ANCHOR_V2") -> 7
    routeId.contains("FUSION_FREE") -> 6
    routeId.contains("ZONE_ANCHOR") -> 5
    else -> 9
}

class MeasurementRecorder(private val context: Context) {
    private var writer: BufferedWriter? = null
    private var fileName: String? = null
    private var startedAtMs = 0L
    private var startStepCounter: Int? = null
    private var sampleCount = 0
    private var labelCount = 0
    private var wifiScanCount = 0
    private var bleObservationCount = 0
    private var currentLabel: RecordingLabel? = null
    private var currentTotalSteps: Int? = null
    private var currentMatchedX: Double? = null
    private var currentMatchedY: Double? = null

    fun start(label: RecordingLabel, totalSteps: Int?): RecordingSnapshot {
        if (writer != null) return current("이미 측정 중입니다.")
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            return RecordingSnapshot(status = "Android 10 이상에서 Downloads 저장을 지원합니다.")
        }
        return try {
            val name = "indoor_positioning_${SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())}.jsonl"
            val values = ContentValues().apply {
                put(MediaStore.MediaColumns.DISPLAY_NAME, name)
                put(MediaStore.MediaColumns.MIME_TYPE, "application/x-ndjson")
                put(MediaStore.MediaColumns.RELATIVE_PATH, "Download/IndoorPositioning")
            }
            val uri = context.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                ?: return RecordingSnapshot(status = "Downloads 파일을 만들지 못했습니다.")
            val stream = context.contentResolver.openOutputStream(uri, "w")
                ?: return RecordingSnapshot(status = "Downloads 파일을 열지 못했습니다.")
            writer = stream.bufferedWriter()
            fileName = name
            startedAtMs = System.currentTimeMillis()
            startStepCounter = totalSteps
            sampleCount = 0
            labelCount = 0
            wifiScanCount = 0
            bleObservationCount = 0
            currentLabel = label
            currentTotalSteps = totalSteps
            currentMatchedX = null
            currentMatchedY = null
            writeLine(
                JSONObject()
                    .put("kind", "session_start")
                    .put("schema_version", schemaVersionForRouteId(label.routeId))
                    .put("platform", "android")
                    .put("wall_time_ms", startedAtMs)
                    .put("device", "${Build.MANUFACTURER} ${Build.MODEL}")
                    .put("android_api", Build.VERSION.SDK_INT)
                    .put("start_step_counter", totalSteps ?: JSONObject.NULL)
                    .put(
                        "radio_observation",
                        if (label.routeId.contains("MULTISENSOR_RADIO_ZONE_ANCHOR_V2")) {
                            JSONObject()
                                .put("nearby_wifi_scan_supported", true)
                                .put("nearby_ble_scan_supported", true)
                                .put("ble_identifier", "sha256_prefix_16")
                                .put("ble_raw_address_saved", false)
                                .put("ble_advertised_name_saved", false)
                        } else JSONObject()
                            .put("mode", "moving_route_timeseries")
                            .put("wifi_scheduled", true)
                            .put("wifi_policy", if (label.routeId.contains("GUIDANCE_FUSION")) "guidance_anchors" else "route_start_and_final_lap")
                            .put("ble_continuous", true),
                    )
                    .put("label", labelJson(label)),
            )
            current("연속 경로 측정 중 · 각 지점에서 랩을 기록하세요.")
        } catch (error: Exception) {
            writer?.close()
            writer = null
            RecordingSnapshot(status = "측정을 시작하지 못했습니다: ${error.message ?: error.javaClass.simpleName}")
        }
    }

    fun recordSample(sample: RawSensorSample) {
        if (writer == null) return
        val sensorWallTimeMs = System.currentTimeMillis() -
            (SystemClock.elapsedRealtimeNanos() - sample.sensorTimestampNs) / 1_000_000L
        writeLine(
            JSONObject()
                .put("kind", "sample")
                .put("wall_time_ms", System.currentTimeMillis())
                .put("sensor_timestamp_ns", sample.sensorTimestampNs)
                .put("sensor_wall_time_ms", sensorWallTimeMs)
                .put("sensor", sample.sensorName)
                .put("values", JSONArray(sample.values)),
        )
        sampleCount += 1
    }

    fun recordDerived(record: JSONObject) {
        if (writer == null) return
        writeLine(record.put("session_elapsed_ms", System.currentTimeMillis() - startedAtMs))
    }

    fun updateRouteContext(totalSteps: Int?, matchedX: Double?, matchedY: Double?) {
        if (writer == null) return
        currentTotalSteps = totalSteps
        currentMatchedX = matchedX
        currentMatchedY = matchedY
    }

    fun recordWifiScan(
        accessPoints: List<WifiAccessPointSample>,
        fresh: Boolean,
        status: String,
        endpointContext: JSONObject? = null,
    ): RecordingSnapshot {
        if (writer == null) return RecordingSnapshot(status = "먼저 다중 센서+AP 기준점 측정을 시작하세요.")
        wifiScanCount += 1
        writeLine(
            JSONObject()
                .put("kind", "wifi_scan")
                .put("wall_time_ms", System.currentTimeMillis())
                .put("session_elapsed_ms", System.currentTimeMillis() - startedAtMs)
                .put("fresh_results", fresh)
                .put("endpoint_context", endpointContext ?: JSONObject.NULL)
                .put("access_point_count", accessPoints.size)
                .put("route_context", routeContextJson())
                .put(
                    "access_points",
                    JSONArray().apply {
                        accessPoints.forEach { accessPoint ->
                            put(
                                JSONObject()
                                    .put("bssid", accessPoint.bssid)
                                    .put("ssid", accessPoint.ssid)
                                    .put("rssi_dbm", accessPoint.rssiDbm)
                                    .put("frequency_mhz", accessPoint.frequencyMhz)
                                    .put("scan_timestamp_us", accessPoint.scanTimestampUs),
                            )
                        }
                    },
                ),
        )
        return current("$status · AP ${accessPoints.size}개")
    }

    fun recordBleObservation(observation: BleEnvironmentObservation) {
        if (writer == null) return
        bleObservationCount += 1
        writeLine(
            JSONObject()
                .put("kind", "ble_observation")
                .put("wall_time_ms", System.currentTimeMillis())
                .put("session_elapsed_ms", System.currentTimeMillis() - startedAtMs)
                .put("anonymous_id", observation.anonymousId)
                .put("identifier_source", observation.identifierSource)
                .put("rssi_dbm", observation.rssiDbm)
                .put("tx_power_dbm", observation.txPowerDbm ?: JSONObject.NULL)
                .put("service_uuids", JSONArray(observation.serviceUuids))
                .put("manufacturer_data_present", observation.manufacturerDataPresent)
                .put("manufacturer_payload_hashes", JSONArray(observation.manufacturerPayloadHashes))
                .put("service_data_hashes", JSONArray(observation.serviceDataHashes))
                .put("ble_identity_diagnostics_version", 1)
                .put("connectable", observation.connectable)
                .put("scan_timestamp_ns", observation.scanTimestampNs)
                .put("route_context", routeContextJson()),
        )
    }

    fun recordBleScanStatus(snapshot: BleSurveySnapshot) {
        if (writer == null) return
        writeLine(
            JSONObject()
                .put("kind", "ble_scan_status")
                .put("wall_time_ms", System.currentTimeMillis())
                .put("session_elapsed_ms", System.currentTimeMillis() - startedAtMs)
                .put("active", snapshot.active)
                .put("status", snapshot.status)
                .put("transmitter_count", snapshot.transmitterCount)
                .put("observation_count", snapshot.observationCount),
        )
    }

    fun recordLabel(
        label: RecordingLabel,
        totalSteps: Int?,
        fusionMode4: JSONObject? = null,
        lapWallTimeMs: Long = System.currentTimeMillis(),
    ): RecordingSnapshot {
        if (writer == null) return RecordingSnapshot(status = "먼저 측정을 시작하세요.")
        labelCount += 1
        currentLabel = label
        currentTotalSteps = totalSteps
        writeLine(
            JSONObject()
                .put("kind", "label")
                .put("wall_time_ms", lapWallTimeMs)
                .put("session_elapsed_ms", lapWallTimeMs - startedAtMs)
                .put("total_steps", totalSteps ?: JSONObject.NULL)
                .put(
                    "steps_since_start",
                    if (totalSteps != null && startStepCounter != null) totalSteps - startStepCounter!! else JSONObject.NULL,
                )
                .put("label_index", labelCount)
                .put("label", labelJson(label))
                .put("baseline_pdr", routeContextJson())
                .put("fusion_mode4", fusionMode4 ?: JSONObject.NULL)
                .put("fusion_prediction_age_ms", fusionMode4?.optLong("wall_time_ms")?.let { lapWallTimeMs - it } ?: JSONObject.NULL),
        )
        return current("${label.location} 기록 완료 · 랩 $labelCount/${label.lapTotal}")
    }

    fun recordGuidanceEvent(event: String, details: JSONObject = JSONObject()) {
        if (writer == null) return
        writeLine(
            JSONObject()
                .put("kind", "guidance_event")
                .put("wall_time_ms", System.currentTimeMillis())
                .put("session_elapsed_ms", System.currentTimeMillis() - startedAtMs)
                .put("event", event)
                .put("route_context", routeContextJson())
                .put("details", details),
        )
    }

    fun stop(totalSteps: Int?): RecordingSnapshot {
        if (writer == null) return RecordingSnapshot(status = "진행 중인 측정이 없습니다.")
        val finishedName = fileName
        writeLine(
            JSONObject()
                .put("kind", "session_end")
                .put("wall_time_ms", System.currentTimeMillis())
                .put("session_elapsed_ms", System.currentTimeMillis() - startedAtMs)
                .put("total_steps", totalSteps ?: JSONObject.NULL)
                .put(
                    "steps_since_start",
                    if (totalSteps != null && startStepCounter != null) totalSteps - startStepCounter!! else JSONObject.NULL,
                )
                .put("samples", sampleCount)
                .put("labels", labelCount)
                .put("wifi_scans", wifiScanCount)
                .put("ble_observations", bleObservationCount),
        )
        writer?.flush()
        writer?.close()
        writer = null
        fileName = null
        currentLabel = null
        currentTotalSteps = null
        currentMatchedX = null
        currentMatchedY = null
        return RecordingSnapshot(
            fileName = finishedName,
            samples = sampleCount,
            labels = labelCount,
            status = "저장 완료: Downloads/IndoorPositioning/$finishedName",
        )
    }

    private fun current(status: String) = RecordingSnapshot(
        active = writer != null,
        fileName = fileName,
        samples = sampleCount,
        labels = labelCount,
        status = status,
    )

    private fun labelJson(label: RecordingLabel) = JSONObject()
        .put("floor", label.floor)
        .put("location", label.location)
        .put("destination", label.destination)
        .put("event", label.event)
        .put("route_id", label.routeId)
        .put("zone_id", if (label.routeId.contains("ZONE_ANCHOR")) zoneIdForLabel(label.location) ?: JSONObject.NULL else JSONObject.NULL)
        .put("lap_index", label.lapIndex)
        .put("lap_total", label.lapTotal)

    private fun routeContextJson(): Any {
        val label = currentLabel ?: return JSONObject.NULL
        if (label.routeId.contains("MULTISENSOR_RADIO_ZONE_ANCHOR_V2")) return JSONObject.NULL
        return JSONObject()
            .put("route_id", label.routeId)
            .put("last_lap_index", label.lapIndex)
            .put("last_lap_location", label.location)
            .put("total_steps", currentTotalSteps ?: JSONObject.NULL)
            .put(
                "steps_since_start",
                if (currentTotalSteps != null && startStepCounter != null) currentTotalSteps!! - startStepCounter!! else JSONObject.NULL,
            )
            .put("matched_x", currentMatchedX ?: JSONObject.NULL)
            .put("matched_y", currentMatchedY ?: JSONObject.NULL)
    }

    private fun writeLine(json: JSONObject) {
        writer?.apply {
            write(json.toString())
            newLine()
        }
    }
}
