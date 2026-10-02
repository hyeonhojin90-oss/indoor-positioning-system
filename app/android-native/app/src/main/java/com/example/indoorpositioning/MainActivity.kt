package com.example.indoorpositioning

import android.Manifest
import android.graphics.Paint
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.content.Context
import android.content.pm.PackageManager
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.getValue
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.example.indoorpositioning.ui.theme.IndoorPositioningPrototypeTheme
import org.json.JSONObject
import java.util.Locale
import kotlinx.coroutines.delay
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.round
import kotlin.math.roundToInt

class MainActivity : ComponentActivity() {
    private var sensorSnapshot by mutableStateOf(SensorSnapshot())
    private var mapMatchingSnapshot by mutableStateOf(MapMatchingSnapshot())
    private var recordingSnapshot by mutableStateOf(RecordingSnapshot())
    private var wifiCalibrationSnapshot by mutableStateOf(WifiCalibrationSnapshot())
    private var bleSurveySnapshot by mutableStateOf(BleSurveySnapshot())
    private var guidanceApSnapshot by mutableStateOf(GuidanceApSnapshot())
    private var routeFusionSnapshot by mutableStateOf(RouteFusionSnapshot())
    private var routeFusionStatus by mutableStateOf("모드 4 엔진 준비 중")
    private var permissionSummary by mutableStateOf("권한 확인 전")
    private var lastRecordedBleStatus: String? = null
    private lateinit var sensorMonitor: SensorMonitor
    private lateinit var floorMapMatcher: FloorMapMatcher
    private lateinit var measurementRecorder: MeasurementRecorder
    private var pendingRouteAp: JSONObject? = null
    private var collectingRoute = false
    private lateinit var wifiFingerprintScanner: WifiFingerprintScanner
    private lateinit var bleEnvironmentScanner: BleEnvironmentScanner
    private lateinit var guidanceApCoordinator: GuidanceApCoordinator
    private lateinit var routeFusionController: RouteFusionController
    private var pendingGuidanceApAnchor: GuidanceApAnchor? = null
    private var guidanceTrackingActive = false
    private var apRequestSteps = 0
    private var apRequestPose: JSONObject? = null
    private var awaitingApDecision: Pair<String, Long>? = null

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) {
        permissionSummary = permissionSummary()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        floorMapMatcher = FloorMapMatcher(this)
        measurementRecorder = MeasurementRecorder(this)
        guidanceApCoordinator = GuidanceApCoordinator()
        routeFusionController = RouteFusionController(
            context = this,
            onSnapshot = { snapshot, record ->
                routeFusionSnapshot = snapshot
                record.optJSONObject("wifiDiagnostic")?.let { diagnostic ->
                    awaitingApDecision?.takeIf { it.second == diagnostic.optLong("timestamp", -1) }?.let { waiting ->
                        guidanceApCoordinator.completeEvent(waiting.first, diagnostic.optBoolean("applied"), SystemClock.elapsedRealtime())
                        measurementRecorder.recordGuidanceEvent("ap_fingerprint_decision", diagnostic)
                        awaitingApDecision = null
                    }
                }
                if (recordingSnapshot.active) {
                    val enriched = JSONObject(record.toString())
                        .put("baseline_pdr", mapMatchingSnapshot.toLogJson())
                    measurementRecorder.recordDerived(enriched)
                }
            },
            onStatus = { routeFusionStatus = it },
        )
        wifiFingerprintScanner = WifiFingerprintScanner(
            context = this,
            onRequestStarted = { requestStartedElapsedMs ->
                wifiCalibrationSnapshot = wifiCalibrationSnapshot.copy(
                    status = "새 AP 스캔 요청됨 · 결과 대기 중",
                    requestCount = wifiCalibrationSnapshot.requestCount + 1,
                    waitingForResult = true,
                    requestStartedElapsedMs = requestStartedElapsedMs,
                    lastRequestElapsedMs = requestStartedElapsedMs,
                )
            },
        ) { accessPoints, fresh, status, requestStartedElapsedMs, resultElapsedMs ->
            val waitMs = requestStartedElapsedMs?.let { (resultElapsedMs - it).coerceAtLeast(0L) }
            wifiCalibrationSnapshot = wifiCalibrationSnapshot.copy(
                status = status,
                apCount = accessPoints.size,
                resultCount = wifiCalibrationSnapshot.resultCount + 1,
                freshResultCount = wifiCalibrationSnapshot.freshResultCount + if (fresh) 1 else 0,
                staleResultCount = wifiCalibrationSnapshot.staleResultCount + if (fresh) 0 else 1,
                waitingForResult = false,
                requestStartedElapsedMs = null,
                lastResultWaitMs = waitMs,
                lastFreshElapsedMs = if (fresh) resultElapsedMs else wifiCalibrationSnapshot.lastFreshElapsedMs,
            )
            pendingRouteAp?.put("steps_at_result", sensorSnapshot.totalSteps ?: JSONObject.NULL)
                ?.put("result_wall_time_ms", System.currentTimeMillis())
            val routeResult = pendingRouteAp
            val motionContext = pendingRouteAp ?: if (guidanceTrackingActive) JSONObject()
                .put("source", if (requestStartedElapsedMs == null) "passive" else "event")
                .put("requested_pose", if (requestStartedElapsedMs == null) JSONObject.NULL else apRequestPose ?: JSONObject.NULL)
                .put("result_pose", routeFusionSnapshot.rawJson?.let(::JSONObject) ?: JSONObject.NULL)
                .put("steps_during_scan", if (requestStartedElapsedMs == null) JSONObject.NULL else (routeFusionSnapshot.steps - apRequestSteps).coerceAtLeast(0)) else null
            if (recordingSnapshot.active) {
                recordingSnapshot = measurementRecorder.recordWifiScan(accessPoints, fresh, status, motionContext)
            }
            if (pendingRouteAp != null) {
                pendingRouteAp = null
            }
            if (collectingRoute && routeResult != null && fresh) {
                routeFusionController.onWifi(accessPoints, true, resultElapsedMs,
                    (routeFusionSnapshot.steps - routeResult.optInt("fusion_steps_at_request")).coerceAtLeast(0))
            }
            pendingGuidanceApAnchor?.let { anchor ->
                guidanceApSnapshot = guidanceApCoordinator.onResult(anchor, fresh, accessPoints.size)
                awaitingApDecision = if (fresh) routeFusionController.onWifi(accessPoints, fresh, resultElapsedMs,
                    (routeFusionSnapshot.steps - apRequestSteps).coerceAtLeast(0))?.let { anchor.id to it } else null
                if (awaitingApDecision == null) guidanceApCoordinator.completeEvent(anchor.id, false, resultElapsedMs,
                    retryAllowed = requestStartedElapsedMs != null && !status.contains("제한") && !status.contains("권한"))
                measurementRecorder.recordGuidanceEvent(
                    event = "guidance_ap_result",
                    details = JSONObject()
                        .put("anchor_id", anchor.id)
                        .put("anchor_label", anchor.label)
                        .put("fresh", fresh)
                        .put("access_point_count", accessPoints.size)
                        .put("status", status),
                )
                pendingGuidanceApAnchor = null
            }
            if (guidanceTrackingActive && fresh && requestStartedElapsedMs == null && awaitingApDecision == null) {
                routeFusionController.onWifi(accessPoints, true, resultElapsedMs, movedSteps = -1)
            }
        }
        bleEnvironmentScanner = BleEnvironmentScanner(
            context = this,
            onObservation = { observation ->
                measurementRecorder.recordBleObservation(observation)
                routeFusionController.onBle(observation)
            },
            onSnapshot = { snapshot ->
                runOnUiThread {
                    bleSurveySnapshot = snapshot
                    if (recordingSnapshot.active && snapshot.status != lastRecordedBleStatus) {
                        measurementRecorder.recordBleScanStatus(snapshot)
                        lastRecordedBleStatus = snapshot.status
                    }
                }
            },
        )
        sensorMonitor = SensorMonitor(
            context = this,
            onUpdate = {
                sensorSnapshot = it
                mapMatchingSnapshot = floorMapMatcher.update(it)
                routeFusionController.onHeading(it.headingDegrees, it.headingSensorTimestampNs)?.let(measurementRecorder::recordSample)
                val guidancePosition = mapMatchingSnapshot.withFusionEstimate(routeFusionSnapshot)
                val headingFresh = it.headingSensorTimestampNs?.let { stamp -> SystemClock.elapsedRealtimeNanos() - stamp in 0..1_500_000_000L } == true
                val uncertain = routeFusionSnapshot.reason.startsWith("recovery_required") ||
                    routeFusionSnapshot.rawJson?.let { json -> JSONObject(json).optDouble("modeWeight", 1.0) < .55 } == true
                if (guidanceTrackingActive) guidanceApCoordinator.updateWithMotion(guidancePosition, SystemClock.elapsedRealtime(),
                    if (routeFusionSnapshot.active) routeFusionSnapshot.steps else it.totalSteps ?: 0,
                    it.headingDegrees?.toDouble()?.takeIf { headingFresh }, uncertain)?.let { anchor ->
                    pendingGuidanceApAnchor = anchor
                    apRequestSteps = routeFusionSnapshot.steps
                    apRequestPose = routeFusionSnapshot.rawJson?.let(::JSONObject)
                    measurementRecorder.recordGuidanceEvent(
                        event = "guidance_ap_anchor_enter",
                        details = JSONObject()
                            .put("anchor_id", anchor.id)
                            .put("anchor_label", anchor.label)
                            .put("request_reason", anchor.reason)
                            .put("event_attempt", anchor.attempt)
                            .put("mode4_x", routeFusionSnapshot.x ?: JSONObject.NULL)
                            .put("mode4_y", routeFusionSnapshot.y ?: JSONObject.NULL),
                    )
                    if (!wifiFingerprintScanner.scan(reserveEmergency = anchor.reason != "tracking_uncertain")) {
                        guidanceApCoordinator.completeEvent(anchor.id, false, SystemClock.elapsedRealtime(), retryAllowed = false)
                        guidanceApSnapshot = guidanceApCoordinator.onRequestUnavailable(anchor)
                        measurementRecorder.recordGuidanceEvent(
                            event = "guidance_ap_request_unavailable",
                            details = JSONObject().put("anchor_id", anchor.id),
                        )
                        pendingGuidanceApAnchor = null
                    } else {
                        guidanceApSnapshot = guidanceApCoordinator.snapshot()
                    }
                }
                if (guidanceTrackingActive) guidanceApSnapshot = guidanceApCoordinator.snapshot()
                measurementRecorder.updateRouteContext(
                    totalSteps = it.totalSteps,
                    matchedX = if (mapMatchingSnapshot.tracking) mapMatchingSnapshot.matchedX else null,
                    matchedY = if (mapMatchingSnapshot.tracking) mapMatchingSnapshot.matchedY else null,
                )
            },
            onRawSample = { sample ->
                measurementRecorder.recordSample(sample)
                routeFusionController.onRawSample(sample)
            },
        )
        permissionSummary = permissionSummary()
        val navigationDestinations = loadNavigationDestinations(this)
        val collectionPresets = loadRouteCollectionPresets(this)
        mapMatchingSnapshot = floorMapMatcher.configureRoute(4, "4F_CORE_TO_RIGHT_STAIRS")

        setContent {
            IndoorPositioningPrototypeTheme {
                Box {
                    IndoorPositioningScreen(
                    permissionSummary = permissionSummary,
                    sensorSnapshot = sensorSnapshot,
                    mapMatchingSnapshot = mapMatchingSnapshot,
                    routeFusionSnapshot = routeFusionSnapshot,
                    routeFusionStatus = routeFusionStatus,
                    recordingSnapshot = recordingSnapshot,
                    wifiCalibrationSnapshot = wifiCalibrationSnapshot,
                    guidanceApSnapshot = guidanceApSnapshot,
                    bleSurveySnapshot = bleSurveySnapshot,
                    destinations = navigationDestinations,
                    collectionPresets = collectionPresets,
                    onRequestPermissions = ::requestIndoorPermissions,
                    onSelectDestination = { destination ->
                        stopActiveGuidance()
                        guidanceTrackingActive = false
                        pendingGuidanceApAnchor = null
                        guidanceApSnapshot = guidanceApCoordinator.resetSession()
                        mapMatchingSnapshot = floorMapMatcher.configureDestination(
                            floor = destination.floor,
                            routeId = navigationRouteId(destination),
                            roomLabel = destination.label,
                            roomX = destination.x,
                        )
                    },
                    onCalibrateMapHeading = {
                        mapMatchingSnapshot = floorMapMatcher.calibrateCurrentHeading(sensorSnapshot.headingDegrees)
                    },
                    onResetMapMatching = {
                        stopActiveGuidance()
                        guidanceTrackingActive = false
                        pendingGuidanceApAnchor = null
                        guidanceApSnapshot = guidanceApCoordinator.resetSession()
                        mapMatchingSnapshot = floorMapMatcher.reset()
                    },
                    onStartMapMatching = {
                        pendingGuidanceApAnchor = null
                        routeFusionSnapshot = RouteFusionSnapshot()
                        guidanceApSnapshot = guidanceApCoordinator.resetSession()
                        mapMatchingSnapshot = floorMapMatcher.startTracking(sensorSnapshot.totalSteps)
                        guidanceTrackingActive = mapMatchingSnapshot.tracking
                        if (guidanceTrackingActive) {
                            wifiFingerprintScanner.passiveEnabled = true
                            recordingSnapshot = measurementRecorder.start(
                                label = RecordingLabel(
                                    floor = mapMatchingSnapshot.floor.toString(),
                                    location = mapMatchingSnapshot.startLabel,
                                    destination = mapMatchingSnapshot.destinationLabel ?: mapMatchingSnapshot.directionLabel,
                                    event = "안내 시작",
                                    routeId = "F${mapMatchingSnapshot.floor}_GUIDANCE_FUSION_V1",
                                    lapIndex = 0,
                                    lapTotal = 0,
                                ),
                                totalSteps = sensorSnapshot.totalSteps,
                            )
                            if (recordingSnapshot.active) {
                                routeFusionController.start(mapMatchingSnapshot.floor, mapMatchingSnapshot.startX, "F${mapMatchingSnapshot.floor}_GUIDANCE_FUSION_V1")
                                startRouteBleCollection()
                                measurementRecorder.recordGuidanceEvent("guidance_start", mapMatchingSnapshot.toLogJson())
                            }
                        }
                    },
                    onStopMapMatching = {
                        measurementRecorder.recordGuidanceEvent("guidance_stop", mapMatchingSnapshot.toLogJson())
                        routeFusionController.stop()
                        routeFusionSnapshot = RouteFusionSnapshot(ready = true, zoneLabel = "모드 4 중지", reason = "stopped")
                        bleEnvironmentScanner.stop()
                        guidanceTrackingActive = false
                        wifiFingerprintScanner.passiveEnabled = false
                        wifiFingerprintScanner.cancelPending()
                        awaitingApDecision = null
                        mapMatchingSnapshot = floorMapMatcher.stopTracking(sensorSnapshot.totalSteps)
                        pendingGuidanceApAnchor = null
                        guidanceApSnapshot = guidanceApCoordinator.stop()
                        if (recordingSnapshot.active) recordingSnapshot = measurementRecorder.stop(sensorSnapshot.totalSteps)
                    },
                    onStartCollection = { preset ->
                        guidanceTrackingActive = false
                        wifiFingerprintScanner.cancelPending()
                        pendingRouteAp = null
                        collectingRoute = true
                        routeFusionSnapshot = RouteFusionSnapshot()
                        mapMatchingSnapshot = floorMapMatcher.configureRoute(preset.floor.toIntOrNull() ?: 0, preset.id)
                        if (mapMatchingSnapshot.available) {
                            mapMatchingSnapshot = floorMapMatcher.calibrateCurrentHeading(sensorSnapshot.headingDegrees)
                            mapMatchingSnapshot = floorMapMatcher.startTracking(sensorSnapshot.totalSteps)
                        }
                        recordingSnapshot = measurementRecorder.start(
                            label = RecordingLabel(
                                floor = preset.floor,
                                location = preset.startLocation,
                                destination = preset.destination,
                                event = "시작",
                                routeId = preset.id,
                                lapIndex = 0,
                                lapTotal = preset.points.size,
                            ),
                            totalSteps = sensorSnapshot.totalSteps,
                        )
                        if (recordingSnapshot.active) {
                            routeFusionController.start(
                                floor = preset.floor.toIntOrNull() ?: 0,
                                x = mapMatchingSnapshot.startX,
                                routeId = preset.id,
                            )
                            startRouteBleCollection()
                            requestRouteAp("start", preset.startLocation)
                        }
                    },
                    onRecordCollectionPoint = { preset, point, pointIndex ->
                        val lapWallTimeMs = System.currentTimeMillis()
                        recordingSnapshot = measurementRecorder.recordLabel(
                            label = RecordingLabel(
                                floor = preset.floor,
                                location = routePointLocation(point),
                                destination = preset.destination,
                                event = if (pointIndex == preset.points.lastIndex) "도착" else "랜드마크",
                                routeId = preset.id,
                                lapIndex = pointIndex + 1,
                                lapTotal = preset.points.size,
                            ),
                            totalSteps = sensorSnapshot.totalSteps,
                            fusionMode4 = routeFusionSnapshot.rawJson?.let(::JSONObject),
                            lapWallTimeMs = lapWallTimeMs,
                        )
                        routeFusionController.captureLap(pointIndex + 1, lapWallTimeMs)
                        if (pointIndex == preset.points.lastIndex) {
                            requestRouteAp("end", routePointLocation(point))
                        }
                    },
                    onStopCollection = { finishCollection() },
                    onStartAnchorCollection = { floor, anchorType, detail ->
                        guidanceTrackingActive = false
                        collectingRoute = false
                        val location = listOf(anchorType, detail.trim()).filter(String::isNotBlank).joinToString(" · ")
                        recordingSnapshot = measurementRecorder.start(
                            label = RecordingLabel(
                                floor = floor.toString(),
                                location = location,
                                destination = "다중 센서+AP+BLE 구역 판별 기준점",
                                event = "기준점 측정 시작",
                                routeId = "F${floor}_MULTISENSOR_RADIO_ZONE_ANCHOR_V2",
                                lapIndex = 0,
                                lapTotal = 0,
                            ),
                            totalSteps = sensorSnapshot.totalSteps,
                        )
                        wifiCalibrationSnapshot = WifiCalibrationSnapshot(status = "다중 센서 기록 중 · 첫 AP 스캔 요청 준비")
                        if (recordingSnapshot.active) {
                            routeFusionController.stop()
                            lastRecordedBleStatus = null
                            bleSurveySnapshot = bleEnvironmentScanner.start()
                            wifiFingerprintScanner.scan()
                        }
                    },
                    onScanAnchorWifi = { wifiFingerprintScanner.scan() },
                    )
                    RouteFusionWebHost(routeFusionController)
                }
            }
        }
    }

    private fun requestRouteAp(phase: String, location: String) {
        // Keep the request location even if a later lap changes the current route label.
        if (pendingRouteAp != null) {
            measurementRecorder.recordGuidanceEvent("route_ap_superseded", pendingRouteAp!!)
            wifiFingerprintScanner.cancelPending()
        }
        pendingRouteAp = JSONObject().put("phase", phase).put("location", location)
            .put("requested_wall_time_ms", System.currentTimeMillis())
            .put("steps_at_request", sensorSnapshot.totalSteps ?: JSONObject.NULL)
            .put("fusion_steps_at_request", routeFusionSnapshot.steps)
            .put("requested_pose", routeFusionSnapshot.rawJson?.let(::JSONObject) ?: JSONObject.NULL)
        measurementRecorder.recordGuidanceEvent("route_endpoint_ap_request", pendingRouteAp!!)
        wifiCalibrationSnapshot = WifiCalibrationSnapshot(status = "$location · AP 결과 대기: 그 위치에서 잠시 기다려 주세요")
        if (!wifiFingerprintScanner.scan()) {
            measurementRecorder.recordGuidanceEvent("route_endpoint_ap_unavailable", pendingRouteAp!!)
            pendingRouteAp = null
        }
    }

    private fun finishCollection() {
        pendingRouteAp?.let {
            measurementRecorder.recordGuidanceEvent("route_endpoint_ap_cancelled_on_stop", it)
        }
        collectingRoute = false
        wifiFingerprintScanner.cancelPending()
        pendingRouteAp = null
        wifiCalibrationSnapshot = wifiCalibrationSnapshot.copy(
            waitingForResult = false,
            requestStartedElapsedMs = null,
            status = "측정 종료 · 대기 중 AP 취소 · 수집한 데이터 저장",
        )
        routeFusionController.stop()
        routeFusionSnapshot = RouteFusionSnapshot(ready = true, zoneLabel = "모드 4 중지", reason = "stopped")
        bleEnvironmentScanner.stop()
        mapMatchingSnapshot = floorMapMatcher.stopTracking(sensorSnapshot.totalSteps)
        recordingSnapshot = measurementRecorder.stop(sensorSnapshot.totalSteps)
    }

    override fun onStart() {
        super.onStart()
        sensorMonitor.start()
    }

    override fun onStop() {
        if (guidanceTrackingActive) stopActiveGuidance()
        else if (recordingSnapshot.active) finishCollection()
        sensorMonitor.stop()
        super.onStop()
    }

    override fun onDestroy() {
        routeFusionController.close()
        bleEnvironmentScanner.close()
        wifiFingerprintScanner.close()
        super.onDestroy()
    }

    private fun startRouteBleCollection() {
        lastRecordedBleStatus = null
        bleSurveySnapshot = bleEnvironmentScanner.start()
    }

    private fun stopActiveGuidance() {
        if (!guidanceTrackingActive && !recordingSnapshot.active) return
        guidanceTrackingActive = false
        wifiFingerprintScanner.passiveEnabled = false
        wifiFingerprintScanner.cancelPending()
        pendingGuidanceApAnchor = null; awaitingApDecision = null
        guidanceApSnapshot = guidanceApCoordinator.stop()
        routeFusionController.stop()
        routeFusionSnapshot = RouteFusionSnapshot(ready = true, zoneLabel = "모드 4 중지", reason = "stopped")
        bleEnvironmentScanner.stop()
        if (recordingSnapshot.active) recordingSnapshot = measurementRecorder.stop(sensorSnapshot.totalSteps)
    }

    private fun requestIndoorPermissions() {
        val permissions = buildList {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                add(Manifest.permission.ACTIVITY_RECOGNITION)
            }
            add(Manifest.permission.ACCESS_COARSE_LOCATION)
            add(Manifest.permission.ACCESS_FINE_LOCATION)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                add(Manifest.permission.BLUETOOTH_SCAN)
                add(Manifest.permission.BLUETOOTH_CONNECT)
            }
        }
        permissionLauncher.launch(permissions.toTypedArray())
    }

    private fun permissionSummary(): String {
        val activityGranted = Build.VERSION.SDK_INT < Build.VERSION_CODES.Q ||
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.ACTIVITY_RECOGNITION,
            ) == PackageManager.PERMISSION_GRANTED

        val locationGranted = ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED

        val bluetoothGranted = Build.VERSION.SDK_INT < Build.VERSION_CODES.S || (
            ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_SCAN) == PackageManager.PERMISSION_GRANTED &&
                ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED
            )

        val missing = buildList {
            if (!activityGranted) add("활동 인식")
            if (!locationGranted) add("AP·BLE 스캔용 위치")
            if (!bluetoothGranted) add("주변 BLE 기기")
        }
        return if (missing.isEmpty()) "센서·AP·BLE 수집 권한 허용됨" else "권한 필요: ${missing.joinToString()}"
    }
}

data class SensorSnapshot(
    val pressureHpa: Float? = null,
    val magneticTotalUt: Float? = null,
    val headingDegrees: Int? = null,
    val headingSensorTimestampNs: Long? = null,
    val totalSteps: Int? = null,
    val hasPressureSensor: Boolean = false,
    val hasStepCounter: Boolean = false,
    val hasRotationVector: Boolean = false,
    val hasMagneticField: Boolean = false,
    val latestUiSensorName: String? = null,
)

internal data class FloorTrackingSnapshot(
    val calibrated: Boolean = false,
    val anchorFloor: Int? = null,
    val anchorPressureHpa: Float? = null,
    val currentFloor: Int? = null,
    val filteredPressureHpa: Float? = null,
    val pressureDeltaHpa: Float? = null,
    val candidateFloor: Int? = null,
    val stableSamples: Int = 0,
    val experimentalAbsoluteFloor: Int? = null,
    val historicalReferencePressureHpa: Float? = null,
    val historicalDifferenceHpa: Float? = null,
    val note: String = "현재 층과 기압을 기준으로 설정하세요.",
)

internal data class HistoricalFloorEstimate(
    val floor: Int,
    val referencePressureHpa: Float,
    val differenceHpa: Float,
)

private val historicalFloorPressuresHpa = mapOf(
    1 to 998.59f,
    2 to 998.11f,
    3 to 997.66f,
    4 to 997.22f,
    5 to 996.77f,
    6 to 996.32f,
    7 to 995.88f,
    8 to 995.43f,
    9 to 994.98f,
    10 to 994.53f,
)

internal fun estimateFloorFromHistoricalPressure(pressureHpa: Float): HistoricalFloorEstimate {
    val nearest = historicalFloorPressuresHpa.minBy { (_, referencePressure) ->
        kotlin.math.abs(pressureHpa - referencePressure)
    }
    return HistoricalFloorEstimate(
        floor = nearest.key,
        referencePressureHpa = nearest.value,
        differenceHpa = pressureHpa - nearest.value,
    )
}

internal class BarometricFloorTracker(
    private val pressurePerFloorHpa: Float = 0.44f,
    private val requiredStableSamples: Int = 3,
    private val smoothingWindow: Int = 3,
) {
    private val recentPressures = ArrayDeque<Float>()
    private var anchorFloor: Int? = null
    private var anchorPressureHpa: Float? = null
    private var confirmedFloor: Int? = null
    private var candidateFloor: Int? = null
    private var candidateSamples = 0

    fun calibrate(floor: Int, pressureHpa: Float): FloorTrackingSnapshot {
        require(floor in 1..10)
        recentPressures.clear()
        repeat(smoothingWindow) { recentPressures.addLast(pressureHpa) }
        anchorFloor = floor
        anchorPressureHpa = pressureHpa
        confirmedFloor = floor
        candidateFloor = floor
        candidateSamples = requiredStableSamples
        return snapshot(pressureHpa, floor, "${floor}층을 기압 기준으로 설정했습니다.")
    }

    fun update(pressureHpa: Float): FloorTrackingSnapshot {
        recentPressures.addLast(pressureHpa)
        while (recentPressures.size > smoothingWindow) recentPressures.removeFirst()
        val filteredPressure = recentPressures.average().toFloat()
        val historicalEstimate = estimateFloorFromHistoricalPressure(filteredPressure)
        val baseFloor = anchorFloor
        val basePressure = anchorPressureHpa
        if (baseFloor == null || basePressure == null) {
            return FloorTrackingSnapshot(
                filteredPressureHpa = filteredPressure,
                experimentalAbsoluteFloor = historicalEstimate.floor,
                historicalReferencePressureHpa = historicalEstimate.referencePressureHpa,
                historicalDifferenceHpa = historicalEstimate.differenceHpa,
                note = "입력 없는 자동 추정은 과거 기압표와 비교한 참고값입니다.",
            )
        }

        val floorOffset = round((basePressure - filteredPressure) / pressurePerFloorHpa).toInt()
        val estimatedFloor = (baseFloor + floorOffset).coerceIn(1, 10)
        if (candidateFloor == estimatedFloor) {
            candidateSamples += 1
        } else {
            candidateFloor = estimatedFloor
            candidateSamples = 1
        }
        if (candidateSamples >= requiredStableSamples) confirmedFloor = estimatedFloor

        val note = when {
            confirmedFloor == estimatedFloor -> "기압 변화가 ${confirmedFloor}층과 일치합니다."
            else -> "${estimatedFloor}층 후보 확인 중 ($candidateSamples/$requiredStableSamples)"
        }
        return snapshot(filteredPressure, estimatedFloor, note)
    }

    private fun snapshot(filteredPressure: Float, estimatedFloor: Int, note: String) = FloorTrackingSnapshot(
        calibrated = true,
        anchorFloor = anchorFloor,
        anchorPressureHpa = anchorPressureHpa,
        currentFloor = confirmedFloor,
        filteredPressureHpa = filteredPressure,
        pressureDeltaHpa = anchorPressureHpa?.let { filteredPressure - it },
        candidateFloor = estimatedFloor,
        stableSamples = candidateSamples.coerceAtMost(requiredStableSamples),
        experimentalAbsoluteFloor = estimateFloorFromHistoricalPressure(filteredPressure).floor,
        historicalReferencePressureHpa = estimateFloorFromHistoricalPressure(filteredPressure).referencePressureHpa,
        historicalDifferenceHpa = estimateFloorFromHistoricalPressure(filteredPressure).differenceHpa,
        note = note,
    )
}

private class SensorMonitor(
    context: Context,
    private val onUpdate: (SensorSnapshot) -> Unit,
    private val onRawSample: (RawSensorSample) -> Unit,
) : SensorEventListener {
    private val sensorManager = context.getSystemService(SensorManager::class.java)
    private val pressureSensor = sensorManager.getDefaultSensor(Sensor.TYPE_PRESSURE)
    private val stepCounter = sensorManager.getDefaultSensor(Sensor.TYPE_STEP_COUNTER)
    private val rotationVector = sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)
    private val accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    private val gyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
    private val magneticField = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)
    private var snapshot = SensorSnapshot(
        hasPressureSensor = pressureSensor != null,
        hasStepCounter = stepCounter != null,
        hasRotationVector = rotationVector != null,
        hasMagneticField = magneticField != null,
    )

    fun start() {
        pressureSensor?.let { sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL) }
        stepCounter?.let { sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL) }
        rotationVector?.let { sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME) }
        accelerometer?.let { sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME) }
        gyroscope?.let { sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME) }
        magneticField?.let { sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME) }
        onUpdate(snapshot)
    }

    fun stop() = sensorManager.unregisterListener(this)

    override fun onSensorChanged(event: SensorEvent) {
        val sensorName = when (event.sensor.type) {
            Sensor.TYPE_PRESSURE -> "pressure_hpa"
            Sensor.TYPE_STEP_COUNTER -> "step_counter"
            Sensor.TYPE_ROTATION_VECTOR -> "rotation_vector"
            Sensor.TYPE_ACCELEROMETER -> "accelerometer_mps2"
            Sensor.TYPE_GYROSCOPE -> "gyroscope_radps"
            Sensor.TYPE_MAGNETIC_FIELD -> "magnetic_field_ut"
            else -> null
        }
        sensorName?.let {
            onRawSample(
                RawSensorSample(
                    sensorTimestampNs = event.timestamp,
                    sensorName = it,
                    values = event.values.map(Float::toFloat),
                ),
            )
        }
        snapshot = when (event.sensor.type) {
            Sensor.TYPE_PRESSURE -> snapshot.copy(pressureHpa = event.values[0], latestUiSensorName = sensorName)
            Sensor.TYPE_STEP_COUNTER -> snapshot.copy(totalSteps = event.values[0].roundToInt(), latestUiSensorName = sensorName)
            Sensor.TYPE_ROTATION_VECTOR -> snapshot.copy(
                headingDegrees = headingFromRotationVector(event.values),
                headingSensorTimestampNs = event.timestamp,
                latestUiSensorName = sensorName,
            )
            Sensor.TYPE_MAGNETIC_FIELD -> snapshot.copy(
                magneticTotalUt = kotlin.math.sqrt(
                    event.values.take(3).sumOf { value -> value.toDouble() * value.toDouble() },
                ).toFloat(),
                latestUiSensorName = sensorName,
            )
            else -> return
        }
        onUpdate(snapshot)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    private fun headingFromRotationVector(values: FloatArray): Int {
        val matrix = FloatArray(9)
        val orientation = FloatArray(3)
        SensorManager.getRotationMatrixFromVector(matrix, values)
        SensorManager.getOrientation(matrix, orientation)
        return ((Math.toDegrees(orientation[0].toDouble()) + 360.0) % 360.0).roundToInt()
    }

}

internal data class NavigationDestination(
    val floor: Int,
    val id: String,
    val label: String,
    val x: Double,
)

internal data class RouteCollectionPreset(
    val id: String,
    val label: String,
    val floor: String,
    val startLocation: String,
    val destination: String,
    val points: List<String>,
)

private data class RouteMapPoint(val id: String, val x: Double, val side: String)

private fun loadNavigationDestinations(context: Context): List<NavigationDestination> = (1..4).flatMap { floor ->
    val map = context.assets.open("data/maps/floor-${floor.toString().padStart(2, '0')}.json")
        .bufferedReader().use { JSONObject(it.readText()) }
    val rooms = map.getJSONArray("rooms")
    val destinations = buildList {
        for (index in 0 until rooms.length()) {
            val room = rooms.getJSONObject(index)
            if (!room.has("x") || room.optBoolean("provisional", false)) continue
            add(
                NavigationDestination(
                    floor = floor,
                    id = room.getString("id"),
                    label = room.optString("label", room.getString("id")),
                    x = room.optDouble("front_x", room.getDouble("x")),
                ),
            )
        }
    }
    if (floor == 2) destinations + floorTwoMainCorridorApproachDestinations(destinations) else destinations
}.sortedWith(compareBy<NavigationDestination> { it.floor }.thenBy { it.x })

internal fun floorTwoMainCorridorApproachDestinations(
    measuredRooms: List<NavigationDestination>,
): List<NavigationDestination> {
    val byId = measuredRooms.associateBy { it.id }
    val studyApproachX = listOfNotNull(byId["2210-1"]?.x, byId["2205"]?.x).average()
        .takeIf { it.isFinite() } ?: return emptyList()
    val extensionEntryX = byId["2204"]?.x ?: return emptyList()
    val openSpaceEntryX = byId["2210-1"]?.x ?: return emptyList()
    return listOf(
        NavigationDestination(2, "2107", "2107 진입부", openSpaceEntryX),
        NavigationDestination(2, "STUDY", "책상공간 근처", studyApproachX),
        NavigationDestination(2, "M-SPACE", "M-space 근처", studyApproachX),
        NavigationDestination(2, "TDM", "TDM 진입부", extensionEntryX),
    )
}

internal fun navigationRouteId(destination: NavigationDestination): String {
    val isNegativeXWing = destination.x < 70.804
    return when {
        destination.floor == 1 && isNegativeXWing -> "1F_MAIN_ENTRANCE_TURN_LEFT"
        destination.floor == 1 -> "1F_MAIN_ENTRANCE_TURN_RIGHT"
        isNegativeXWing -> "${destination.floor}F_CORE_TO_RIGHT_STAIRS"
        else -> "${destination.floor}F_CORE_TO_LEFT_STAIRS"
    }
}

private fun loadRouteCollectionPresets(context: Context): List<RouteCollectionPreset> {
    val base = context.assets.open("data/maps/floor-04.json").bufferedReader().use { JSONObject(it.readText()) }
    val layout = base.getJSONObject("layout_dimensions")
    val coreCenterX = layout.getDouble("left_corridor_length") + layout.getDouble("hub_outer_width") / 2.0
    return (1..10).flatMap { floor ->
        val map = context.assets.open("data/maps/floor-${floor.toString().padStart(2, '0')}.json")
            .bufferedReader().use { JSONObject(it.readText()) }
        val rooms = map.getJSONArray("rooms")
        val roomPositions = buildList {
            for (index in 0 until rooms.length()) {
                val room = rooms.getJSONObject(index)
                if (room.has("x") && !room.optBoolean("provisional", false)) {
                    add(RouteMapPoint(room.getString("id"), room.getDouble("x"), room.optString("side", "lower")))
                }
            }
        }
        val rightRooms = roomPositions.filter { it.x < coreCenterX }
        val rightWing = preferredRightRoomRow(floor, rightRooms).sortedByDescending { it.x }
        val leftWing = preferredRoomRow(roomPositions.filter { it.x > coreCenterX }).sortedBy { it.x }
        val mainRoutes = if (floor == 1) {
            val entranceLeftWing = rightRooms.filter { it.side == "lower" }.sortedByDescending { it.x }
            firstFloorMainEntranceRoutes(entranceLeftWing, leftWing)
        } else {
            listOf(
                routePreset(floor, "RIGHT", "오른쪽 계단 입구", rightWing),
                routePreset(floor, "LEFT", "왼쪽 계단 입구", leftWing),
            )
        }
        mainRoutes + specialRoutePresets(floor)
    }
}

private fun preferredRoomRow(rooms: List<RouteMapPoint>): List<RouteMapPoint> {
    val upperRooms = rooms.filter { it.side == "upper" }
    return upperRooms.ifEmpty { rooms.filter { it.side == "lower" } }
}

private fun preferredRightRoomRow(floor: Int, rooms: List<RouteMapPoint>): List<RouteMapPoint> {
    val preferredSide = if (floor in setOf(2, 3, 4, 5)) "lower" else "upper"
    val preferredRooms = rooms.filter { it.side == preferredSide }
    return preferredRooms.ifEmpty { preferredRoomRow(rooms) }
}

internal fun sensorAnchorGroupsForFloor(floor: Int): Map<String, List<String>> = when (floor) {
    2 -> linkedMapOf(
        "왼쪽복도" to listOf(
            "왼쪽 계단 앞 · 출입문 정면 · 메인복도 중앙선",
        ),
        "코어" to listOf(
            "코어 교차점 · 코어복도와 오른쪽 메인복도 중심축 교차점",
        ),
        "오른쪽 메인복도" to listOf(
            "기둥·TDM 사이 · 메인복도와 증축복도 중심축 교차점",
            "오른쪽 계단 앞 · 출입문 정면 · 메인복도 중앙선",
            "오른쪽 계단 내부 · 출입문 통과 후 첫 계단참 중앙",
        ),
        "증축복도" to listOf(
            "2105-1 앞 · 2105-1 가로폭 중앙 정면 · 증축복도 중앙선",
        ),
    )
    3 -> linkedMapOf(
        "전체" to listOf(
            "오른쪽 강의실 라인",
            "왼쪽 강의실 라인",
            "3203 문 정면 · 증축복도 진입 가능 구간 기준점 · 메인복도 중앙선",
            "왼쪽 계단 앞 · 출입문 정면 · 메인복도 중앙선",
            "오른쪽 계단 앞 · 출입문 정면 · 메인복도 중앙선",
            "오른쪽 계단 내부 · 출입문 통과 후 첫 계단참 중앙",
            "코어 교차점 · 코어복도와 메인복도 중심축 교차점",
        ),
    )
    else -> linkedMapOf(
        "전체" to listOf(
            "코어 교차점 · 코어복도와 메인복도 중심축 교차점",
            "왼쪽 계단 앞 · 출입문 정면 · 메인복도 중앙선",
            "오른쪽 계단 앞 · 출입문 정면 · 메인복도 중앙선",
            "오른쪽 계단 내부 · 출입문 통과 후 첫 계단참 중앙",
        ),
    )
}.let { groups ->
    if (floor == 3) groups else groups + linkedMapOf(
        "복도 내부 · 위치 직접 입력" to listOf("왼쪽 강의실 라인", "오른쪽 강의실 라인"),
    )
}

internal fun sensorAnchorTypesForFloor(floor: Int): List<String> =
    sensorAnchorGroupsForFloor(floor).values.flatten()

internal fun anchorDetailRequired(anchorType: String): Boolean =
    anchorType == "오른쪽 강의실 라인" || anchorType == "왼쪽 강의실 라인"

internal fun anchorDetailMatchesFloor(
    floor: Int?,
    anchorType: String,
    detail: String,
    validRoomIds: Set<String>? = null,
): Boolean {
    if (!anchorDetailRequired(anchorType)) return true
    if (floor == null) return false
    val roomNumber = Regex("""(?<!\d)(\d{4}(?:-\d+)?)(?!\d)""").find(detail)?.groupValues?.get(1)
        ?: return false
    return roomNumber.startsWith(floor.toString()) && (validRoomIds == null || roomNumber in validRoomIds)
}

internal fun anchorCollectionInstruction(anchorType: String): String = when {
    anchorDetailRequired(anchorType) ->
        "세부 위치에 '강의실 문 정면 · 복도 중앙선'을 적으세요. 예: 4204 문 정면 · 복도 중앙선"
    anchorType.contains("계단 내부") ->
        "출입문을 통과한 뒤 첫 계단참의 중앙에 서서, 계단 진행 방향을 보고 측정하세요."
    else ->
        "발 위치를 선택한 중앙선·정면 기준에 맞추고, 휴대폰을 세로로 든 채 진행 방향을 보고 측정하세요."
}

internal fun specialRoutePresets(floor: Int): List<RouteCollectionPreset> = when (floor) {
    1 -> listOf(
        specialRoutePreset(
            "1F_OUTDOOR_ADMIN_CORRIDOR", "1층 본동·행정실 사이 야외복도", 1,
            "정문 출입문 앞", "야외복도 끝",
            listOf("본동·행정실 사이 야외복도 입구", "행정실 문", "야외복도 중앙", "야외복도 끝"),
        ),
    )
    2 -> listOf(
        specialRoutePreset("2F_EXTENSION_V3", "2층 기둥·TDM 사이 → 증축복도", 2, "기둥·TDM 사이 · 메인복도와 증축복도 중심축 교차점", "증축복도 계단 진입 전 · 복도 중앙선", listOf("기둥·TDM 사이 · 메인복도와 증축복도 중심축 교차점", "TDM 옆 · TDM 외벽 가로폭 중앙 정면 · 증축복도 중앙선", "2105-1·2104-1 사이 · 증축복도 중앙선", "2105-2·2104-2 사이 · 증축복도 중앙선", "증축복도 계단 진입 전 · 복도 중앙선")),
    )
    3 -> listOf(
        specialRoutePreset("3F_EXTENSION", "3층 증축부 라인 별도 측정", 3, "메인복도·증축부 교차점", "3104-1", listOf("증축부 입구", "자유공간", "3104-2", "3104-1")),
        specialRoutePreset("3F_IT_HALL", "3층 IT홀 계단 별도 측정", 3, "자유공간 IT홀 계단 아래", "IT홀 입구", listOf("IT홀 계단 아래", "IT홀 계단 위 회전점", "IT홀 입구")),
    )
    5 -> listOf(
        specialRoutePreset("5F_OUTDOOR", "5층 야외공간 별도 측정", 5, "오른쪽 복도 야외문", "야외공간 끝", listOf("야외공간 입구", "야외공간 중앙", "야외공간 끝")),
    )
    else -> emptyList()
}

private fun specialRoutePreset(
    id: String,
    label: String,
    floor: Int,
    start: String,
    destination: String,
    points: List<String>,
) = RouteCollectionPreset(id, label, floor.toString(), start, destination, points)

internal fun floorTwoRightMainPoints(orderedRoomIds: List<String>, stairs: String): List<String> {
    val remainingRooms = orderedRoomIds
        .filterNot { it in setOf("2211", "2210-1", "2205") }
        .map(::routePointLocation)
    return listOf(
        "2211 문 1",
        "2211 문 2",
        "2210-1 문 1",
        "2107 진입 가능점",
        "2210-1 문 2 · 2107 끝점",
        "2205 서버실 앞",
    ) + remainingRooms + "오른쪽 끝 화장실 통로 앞" + stairs
}

internal fun standardMainRoutePoints(
    floor: Int,
    sideId: String,
    orderedRoomIds: List<String>,
    stairs: String,
): List<String> = if (floor == 4 && sideId == "RIGHT") {
    orderedRoomIds + "오른쪽 끝 화장실 통로 앞" + stairs
} else {
    orderedRoomIds + stairs
}

private fun routePreset(
    floor: Int,
    sideId: String,
    stairs: String,
    orderedRooms: List<RouteMapPoint>,
): RouteCollectionPreset {
    if (floor == 2 && sideId == "RIGHT") {
        return RouteCollectionPreset(
            id = "2F_CORE_TO_RIGHT_STAIRS",
            label = "2층 코어 출구 → $stairs",
            floor = "2",
            startLocation = "코어·오른쪽 메인복도 교차점",
            destination = stairs,
            points = floorTwoRightMainPoints(orderedRooms.map { it.id }, stairs),
        )
    }
    return RouteCollectionPreset(
        id = "${floor}F_CORE_TO_${sideId}_STAIRS",
        label = "${floor}층 코어 출구 → $stairs",
        floor = floor.toString(),
        startLocation = "코어복도 출구 중앙점",
        destination = stairs,
        points = standardMainRoutePoints(floor, sideId, orderedRooms.map { it.id }, stairs),
    )
}

private fun firstFloorMainEntranceRoutes(
    entranceLeftWing: List<RouteMapPoint>,
    entranceRightWing: List<RouteMapPoint>,
) = listOf(
    RouteCollectionPreset(
        id = "1F_MAIN_ENTRANCE_TURN_LEFT",
        label = "1층 정문 진입 후 왼쪽 복도",
        floor = "1",
        startLocation = "정문 바깥 중앙 기준점",
        destination = "정문 기준 왼쪽 끝 계단 입구",
        points = listOf("정문 출입문", "정문·메인복도 진입점") +
            entranceLeftWing.map { it.id } + "정문 기준 왼쪽 끝 계단 입구",
    ),
    RouteCollectionPreset(
        id = "1F_MAIN_ENTRANCE_TURN_RIGHT",
        label = "1층 정문 진입 후 오른쪽 복도",
        floor = "1",
        startLocation = "정문 바깥 중앙 기준점",
        destination = "정문 기준 오른쪽 끝 계단 입구",
        points = listOf("정문 출입문", "정문·메인복도 진입점") +
            entranceRightWing.map { it.id } + "정문 기준 오른쪽 끝 계단 입구",
    ),
)

internal fun routePointLocation(point: String): String =
    if (listOf("입구", "중앙", "중앙선", "끝", "공간", "교차점", "아래", "회전점", "출입문", "진입점", "중앙점", "앞").any(point::endsWith)) point else "$point 앞"

private enum class ScreenMode { GUIDE, MAP, COLLECTION }
private enum class CollectionKind { ROUTE, ANCHOR }

private fun MapMatchingSnapshot.toLogJson(): JSONObject = JSONObject()
    .put("floor", floor)
    .put("route_id", routeId)
    .put("raw_x", rawX)
    .put("raw_y", rawY)
    .put("matched_x", matchedX)
    .put("matched_y", matchedY)
    .put("corridor", corridorLabel)
    .put("nearest_room", nearestRoomLabel ?: JSONObject.NULL)
    .put("destination", destinationLabel ?: JSONObject.NULL)
    .put("destination_distance", destinationDistanceMeters ?: JSONObject.NULL)
    .put("arrived", arrived)
    .put("direction_status", directionStatus)

private fun MapMatchingSnapshot.withFusionEstimate(fusion: RouteFusionSnapshot): MapMatchingSnapshot {
    val fusionX = fusion.x ?: return this
    val fusionY = fusion.y ?: return this
    if (!fusion.active || fusion.floor != floor) return this
    val nearest = rooms.minByOrNull { room -> hypot(fusionX - room.x, fusionY - room.y) }
    val nearestDistance = nearest?.let { room -> hypot(fusionX - room.x, fusionY - room.y) }
    val engineLandmark = fusion.rawJson?.let(::JSONObject)?.optJSONArray("landmarks")?.optJSONObject(0)
        ?.takeIf { it.has("positionBasis") }
    val targetX = destinationLabel
        ?.let { label -> rooms.firstOrNull { it.id == label || label.startsWith(it.id) }?.x }
    val destinationDistance = targetX?.let { abs(fusionX - it) }
    return copy(
        matchedX = fusionX,
        matchedY = fusionY,
        corridorLabel = fusion.zoneLabel,
        nearestRoomLabel = engineLandmark?.optString("label") ?: nearest?.id,
        nearestRoomDistanceMeters = engineLandmark?.optDouble("distance") ?: nearestDistance,
        destinationDistanceMeters = destinationDistance ?: destinationDistanceMeters,
        arrived = destinationDistance?.let { it <= 2.5 } ?: arrived,
        note = "모드 4 추적: ${fusion.reason}",
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@androidx.compose.runtime.Composable
private fun IndoorPositioningScreen(
    permissionSummary: String,
    sensorSnapshot: SensorSnapshot,
    mapMatchingSnapshot: MapMatchingSnapshot,
    routeFusionSnapshot: RouteFusionSnapshot,
    routeFusionStatus: String,
    recordingSnapshot: RecordingSnapshot,
    wifiCalibrationSnapshot: WifiCalibrationSnapshot,
    guidanceApSnapshot: GuidanceApSnapshot,
    bleSurveySnapshot: BleSurveySnapshot,
    destinations: List<NavigationDestination>,
    collectionPresets: List<RouteCollectionPreset>,
    onRequestPermissions: () -> Unit,
    onSelectDestination: (NavigationDestination) -> Unit,
    onCalibrateMapHeading: () -> Unit,
    onResetMapMatching: () -> Unit,
    onStartMapMatching: () -> Unit,
    onStopMapMatching: () -> Unit,
    onStartCollection: (RouteCollectionPreset) -> Unit,
    onRecordCollectionPoint: (RouteCollectionPreset, String, Int) -> Unit,
    onStopCollection: () -> Unit,
    onStartAnchorCollection: (Int, String, String) -> Unit,
    onScanAnchorWifi: () -> Unit,
) {
    var screenMode by remember { mutableStateOf(ScreenMode.GUIDE) }
    var showFusionExperiment by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }
    var selectedDestination by remember { mutableStateOf<NavigationDestination?>(null) }
    val searchResults = if (query.isBlank()) {
        emptyList()
    } else {
        destinations.filter { destination ->
            destination.id.contains(query.trim(), ignoreCase = true) ||
                destination.label.contains(query.trim(), ignoreCase = true)
        }.take(10)
    }
    val primaryMapSnapshot = mapMatchingSnapshot.withFusionEstimate(routeFusionSnapshot)

    Scaffold(
        topBar = { TopAppBar(title = { Text("IT융합대학 강의실 안내") }) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                OutlinedButton(onClick = { screenMode = ScreenMode.GUIDE }, modifier = Modifier.weight(1f)) {
                    Text("강의실 안내")
                }
                OutlinedButton(onClick = { screenMode = ScreenMode.MAP }, modifier = Modifier.weight(1f)) {
                    Text("2D·3D 지도")
                }
                OutlinedButton(onClick = { screenMode = ScreenMode.COLLECTION }, modifier = Modifier.weight(1f)) {
                    Text("보정 수집")
                }
            }
            if (screenMode == ScreenMode.MAP) {
                MapBrowserContent()
                return@Column
            }
            if (screenMode == ScreenMode.COLLECTION) {
                if (!recordingSnapshot.active) {
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (showFusionExperiment) {
                            Button(onClick = { showFusionExperiment = true }, modifier = Modifier.weight(1f)) { Text("자유 위치 추적") }
                        } else {
                            OutlinedButton(onClick = { showFusionExperiment = true }, modifier = Modifier.weight(1f)) { Text("자유 위치 추적") }
                        }
                        if (!showFusionExperiment) {
                            Button(onClick = { showFusionExperiment = false }, modifier = Modifier.weight(1f)) { Text("보정 데이터 수집") }
                        } else {
                            OutlinedButton(onClick = { showFusionExperiment = false }, modifier = Modifier.weight(1f)) { Text("보정 데이터 수집") }
                        }
                    }
                }
                if (showFusionExperiment) {
                    OutlinedButton(onClick = onRequestPermissions) { Text("센서·AP·BLE 권한 확인") }
                    FusionExperimentContent()
                    return@Column
                }
                CollectionModeContent(
                    presets = collectionPresets,
                    validRoomIdsByFloor = destinations.groupBy { it.floor }.mapValues { (_, rooms) -> rooms.map { it.id }.toSet() },
                    permissionSummary = permissionSummary,
                    recordingSnapshot = recordingSnapshot,
                    wifiCalibrationSnapshot = wifiCalibrationSnapshot,
                    bleSurveySnapshot = bleSurveySnapshot,
                    sensorSnapshot = sensorSnapshot,
                    mapMatchingSnapshot = mapMatchingSnapshot,
                    routeFusionSnapshot = routeFusionSnapshot,
                    routeFusionStatus = routeFusionStatus,
                    onStart = onStartCollection,
                    onRecordPoint = onRecordCollectionPoint,
                    onStop = onStopCollection,
                    onStartAnchor = onStartAnchorCollection,
                    onScanAnchorWifi = onScanAnchorWifi,
                    onRequestPermissions = onRequestPermissions,
                )
                return@Column
            }
            Text(
                text = "강의실 찾기",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "1~4층 강의실 번호나 이름을 검색하세요.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            SectionTitle("목적지 검색")
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("예: 4210, iSPACE") },
                singleLine = true,
            )
            searchResults.forEach { destination ->
                OutlinedButton(
                    onClick = {
                        selectedDestination = destination
                        query = destination.label
                        onSelectDestination(destination)
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("${destination.floor}층 · ${destination.label}")
                }
            }

            val destination = selectedDestination
            if (destination == null) {
                StatusCard("안내 준비", "강의실을 검색하고 결과를 선택하세요.")
            } else {
                val wing = when {
                    destination.floor == 1 && destination.x < 70.804 -> "정문 기준 왼쪽 복도"
                    destination.floor == 1 -> "정문 기준 오른쪽 복도"
                    destination.x < 70.804 -> "코어 기준 오른쪽 복도"
                    else -> "코어 기준 왼쪽 복도"
                }
                StatusCard("목적지", "${destination.floor}층 · ${destination.label}")
                StatusCard(
                    "임시 경로",
                    if (destination.floor == 1) {
                        "정문·메인복도 진입점 → $wing → ${destination.label}"
                    } else {
                        "${destination.floor}층 코어복도 출구 중앙점 → $wing → ${destination.label}"
                    },
                )

                SectionTitle("안내 상태")
                StatusCard(
                    if (primaryMapSnapshot.arrived) "도착" else "현재 안내 · 모드 4",
                    if (routeFusionSnapshot.active) {
                        "${primaryMapSnapshot.floor}층 · ${routeFusionSnapshot.zoneLabel} · " +
                            "x=${format(primaryMapSnapshot.matchedX.toFloat())}, y=${format(primaryMapSnapshot.matchedY.toFloat())}\n" +
                            "자기장 ${routeFusionSnapshot.magneticApplied}/${routeFusionSnapshot.magneticEvaluated} (${if (routeFusionSnapshot.magneticStrategy == "grid_primary_v2_fallback") "격자 우선·V2 보조" else "V2"}) · " +
                            "BLE ${routeFusionSnapshot.bleApplied}/${routeFusionSnapshot.bleEvaluated} · ${routeFusionSnapshot.reason}"
                    } else "$routeFusionStatus\n${mapMatchingSnapshot.note}",
                )
                StatusCard(
                    "기존 PDR 기준선",
                    "x=${format(mapMatchingSnapshot.matchedX.toFloat())}, y=${format(mapMatchingSnapshot.matchedY.toFloat())} · ${mapMatchingSnapshot.corridorLabel}",
                )
                StatusCard(
                    "자동 AP 기준점",
                    "${guidanceApSnapshot.status}\n" +
                        (routeFusionSnapshot.wifiAnchorLabel?.let { label ->
                            "최근 지문 후보: $label" + (routeFusionSnapshot.wifiAnchorWeight?.let { " · 상대가중치 ${"%.2f".format(it)}" } ?: "") + "\n"
                        } ?: "") +
                        "요청 ${guidanceApSnapshot.requestCount}회 · 새 결과 ${guidanceApSnapshot.freshResultCount}회 · 이전 결과 ${guidanceApSnapshot.staleResultCount}회",
                )
                if (mapMatchingSnapshot.bufferedDirectionSteps > 0) {
                    StatusCard("방향 전환", mapMatchingSnapshot.directionStatus)
                }
                SensorRow("활동 인식 권한", true, permissionSummary)
                if (!permissionSummary.contains("허용됨")) {
                    Button(onClick = onRequestPermissions, modifier = Modifier.fillMaxWidth()) {
                        Text("걸음·AP·BLE 수집 권한 허용")
                    }
                }
                SensorRow("걸음 센서", sensorSnapshot.hasStepCounter, sensorSnapshot.totalSteps?.toString())
                SensorRow("방향", sensorSnapshot.hasRotationVector, sensorSnapshot.headingDegrees?.let { "$it°" })
                SensorRow("기압", sensorSnapshot.hasPressureSensor, sensorSnapshot.pressureHpa?.let { "${format(it)} hPa" })
                SensorRow(
                    "목적지까지",
                    primaryMapSnapshot.available,
                    primaryMapSnapshot.destinationDistanceMeters?.let { "지도상 ${format(it.toFloat())}" },
                )
                SensorRow(
                    "가까운 강의실",
                    primaryMapSnapshot.available,
                    primaryMapSnapshot.nearestRoomLabel,
                )
                FloorMapPreview(primaryMapSnapshot)

                Button(
                    onClick = onCalibrateMapHeading,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = sensorSnapshot.headingDegrees != null && !mapMatchingSnapshot.tracking,
                ) {
                    Text("${destination.label} 방향으로 지도 보정")
                }
                Button(
                    onClick = onStartMapMatching,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = mapMatchingSnapshot.available && mapMatchingSnapshot.calibrated && !mapMatchingSnapshot.tracking,
                ) {
                    Text("안내 시작")
                }
                Button(
                    onClick = onStopMapMatching,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = mapMatchingSnapshot.tracking,
                ) {
                    Text("안내 중지")
                }
                OutlinedButton(onClick = onResetMapMatching, modifier = Modifier.fillMaxWidth()) {
                    Text("${mapMatchingSnapshot.startLabel}으로 위치 초기화")
                }

                SectionTitle("${destination.floor}층 전체 지도")
                WebFloorMap(destination.floor)
            }
        }
    }
}

@androidx.compose.runtime.Composable
private fun RouteFusionWebHost(controller: RouteFusionController) {
    AndroidView(
        factory = { controller.view },
        modifier = Modifier.size(1.dp).alpha(0.01f),
    )
}

@androidx.compose.runtime.Composable
private fun MapBrowserContent() {
    var floorInput by remember { mutableStateOf("4") }
    var show3d by remember { mutableStateOf(false) }
    val floor = floorInput.toIntOrNull()?.takeIf { it in 1..10 }
    SectionTitle("층별 지도 보기")
    OutlinedTextField(
        value = floorInput,
        onValueChange = { value -> floorInput = value.filter(Char::isDigit).take(2) },
        modifier = Modifier.fillMaxWidth(),
        label = { Text("층 선택 (1~10)") },
        singleLine = true,
    )
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = { show3d = false }, modifier = Modifier.weight(1f)) { Text("2D 지도") }
        Button(onClick = { show3d = true }, modifier = Modifier.weight(1f)) { Text("3D 지도") }
    }
    if (floor == null) {
        StatusCard("지도", "1~10층 중 하나를 입력하세요.")
    } else {
        StatusCard("지도", "${floor}층 ${if (show3d) "3D" else "2D"} 보기")
        if (show3d) {
            Text("3D 지도는 Three.js를 내려받기 위해 인터넷 연결이 필요합니다.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        WebFloorMap(floor, show3d)
    }
}

@androidx.compose.runtime.Composable
private fun CollectionModeContent(
    presets: List<RouteCollectionPreset>,
    validRoomIdsByFloor: Map<Int, Set<String>>,
    permissionSummary: String,
    recordingSnapshot: RecordingSnapshot,
    wifiCalibrationSnapshot: WifiCalibrationSnapshot,
    bleSurveySnapshot: BleSurveySnapshot,
    sensorSnapshot: SensorSnapshot,
    mapMatchingSnapshot: MapMatchingSnapshot,
    routeFusionSnapshot: RouteFusionSnapshot,
    routeFusionStatus: String,
    onStart: (RouteCollectionPreset) -> Unit,
    onRecordPoint: (RouteCollectionPreset, String, Int) -> Unit,
    onStop: () -> Unit,
    onStartAnchor: (Int, String, String) -> Unit,
    onScanAnchorWifi: () -> Unit,
    onRequestPermissions: () -> Unit,
) {
    var floorInput by remember { mutableStateOf("4") }
    var collectionKind by remember { mutableStateOf(CollectionKind.ROUTE) }
    var routeReversed by remember { mutableStateOf(false) }
    var selectedPreset by remember { mutableStateOf<RouteCollectionPreset?>(null) }
    var nextPointIndex by remember { mutableStateOf(0) }
    var anchorType by remember { mutableStateOf("오른쪽 강의실 라인") }
    var anchorArea by remember { mutableStateOf("전체") }
    var anchorDetail by remember { mutableStateOf("") }
    var anchorCollectionActive by remember { mutableStateOf(false) }
    val floor = floorInput.toIntOrNull()?.takeIf { it in 1..10 }
    val floorPresets = presets.filter { it.floor.toIntOrNull() == floor }

    SectionTitle("보정 데이터 수집")
    Text(
        "PDR용 가속도·자이로·걸음, 자기장·기압·방향과 Wi-Fi AP·BLE 신호를 보정 자료로 수집합니다. Wi-Fi RTT 거리측정은 사용하지 않습니다.",
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    SensorRow("수집 권한", true, permissionSummary)
    if (!permissionSummary.contains("허용됨")) {
        Button(onClick = onRequestPermissions, modifier = Modifier.fillMaxWidth()) {
            Text("걸음·AP·BLE 수집 권한 허용")
        }
    }
    Text("수집 종류", fontWeight = FontWeight.Bold)
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        val routeModifier = Modifier.weight(1f)
        val anchorModifier = Modifier.weight(1f)
        if (collectionKind == CollectionKind.ROUTE) {
            Button(onClick = { collectionKind = CollectionKind.ROUTE }, modifier = routeModifier, enabled = !recordingSnapshot.active) { Text("경로 라벨 비교") }
        } else {
            OutlinedButton(onClick = { collectionKind = CollectionKind.ROUTE }, modifier = routeModifier, enabled = !recordingSnapshot.active) { Text("경로 라벨 비교") }
        }
        if (collectionKind == CollectionKind.ANCHOR) {
            Button(onClick = { collectionKind = CollectionKind.ANCHOR }, modifier = anchorModifier, enabled = !recordingSnapshot.active) { Text("센서 기준점") }
        } else {
            OutlinedButton(onClick = { collectionKind = CollectionKind.ANCHOR }, modifier = anchorModifier, enabled = !recordingSnapshot.active) { Text("센서 기준점") }
        }
    }
    Text("층 선택", fontWeight = FontWeight.Bold)
    (1..10).chunked(5).forEach { floors ->
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            floors.forEach { selectedFloor ->
                val onSelect = {
                    if (!recordingSnapshot.active) {
                        floorInput = selectedFloor.toString()
                        selectedPreset = null
                        nextPointIndex = 0
                        val groups = sensorAnchorGroupsForFloor(selectedFloor)
                        anchorArea = groups.keys.first()
                        anchorType = groups.getValue(anchorArea).first()
                        anchorDetail = ""
                    }
                }
                if (floor == selectedFloor) {
                    Button(onClick = onSelect, modifier = Modifier.weight(1f), enabled = !recordingSnapshot.active) { Text("${selectedFloor}층") }
                } else {
                    OutlinedButton(onClick = onSelect, modifier = Modifier.weight(1f), enabled = !recordingSnapshot.active) { Text("${selectedFloor}층") }
                }
            }
        }
    }
    if (collectionKind == CollectionKind.ANCHOR) {
    SectionTitle("센서 기준점")
    Text(
        "같은 지점에서 가속도·자이로·걸음·자기장·기압·방향, AP별 BSSID·RSSI와 주변 BLE RSSI를 함께 저장합니다. 강의실 라인, 계단 앞, 계단 내부를 구분하는 학습 자료입니다.",
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    val anchorGroups = sensorAnchorGroupsForFloor(floor ?: 4)
    if (anchorGroups.size > 1) {
        Text("측정 구역", fontWeight = FontWeight.Bold)
        anchorGroups.keys.chunked(2).forEach { areas ->
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                areas.forEach { area ->
                    val selectArea = {
                        anchorArea = area
                        anchorType = anchorGroups.getValue(area).first()
                        anchorDetail = ""
                    }
                    if (anchorArea == area) {
                        Button(onClick = selectArea, modifier = Modifier.weight(1f), enabled = !recordingSnapshot.active) { Text(area) }
                    } else {
                        OutlinedButton(onClick = selectArea, modifier = Modifier.weight(1f), enabled = !recordingSnapshot.active) { Text(area) }
                    }
                }
                if (areas.size == 1) Spacer(modifier = Modifier.weight(1f))
            }
        }
    }
    Text("기준점", fontWeight = FontWeight.Bold)
    val visibleAnchorTypes = anchorGroups[anchorArea] ?: anchorGroups.values.first()
    visibleAnchorTypes.forEach { type ->
        OutlinedButton(
            onClick = {
                anchorType = type
                anchorDetail = ""
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = !recordingSnapshot.active,
        ) {
            val shortType = when (type) {
                "오른쪽 강의실 라인" -> "오른쪽 복도 내부 · 위치 메모"
                "왼쪽 강의실 라인" -> "왼쪽 복도 내부 · 위치 메모"
                else -> type.substringBefore(" · ")
            }
            Text(if (anchorType == type) "✓ $shortType" else shortType)
        }
    }
    val detailRequired = anchorDetailRequired(anchorType)
    val detailMatchesFloor = anchorDetailMatchesFloor(floor, anchorType, anchorDetail, floor?.let(validRoomIdsByFloor::get))
    StatusCard("저장되는 층", floor?.let { "${it}층" } ?: "층을 먼저 선택하세요")
    StatusCard("정확한 측정 위치", "$anchorType\n${anchorCollectionInstruction(anchorType)}")
    run {
        OutlinedTextField(
            value = anchorDetail,
            onValueChange = { anchorDetail = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text(if (detailRequired) "복도 내부 어디 앞? (필수 · 예: 4204 문 정면 · 복도 중앙선)" else "위치 메모 (선택 · 실제 서 있는 곳)") },
            singleLine = true,
            enabled = !recordingSnapshot.active,
        )
        if (detailRequired && anchorDetail.isBlank()) {
            Text("강의실 번호와 문 정면 위치를 적어야 측정을 시작할 수 있습니다.", color = MaterialTheme.colorScheme.error)
        } else if (detailRequired && !detailMatchesFloor) {
            Text("선택한 ${floor ?: "?"}층과 강의실 번호가 맞지 않습니다. 층 또는 번호를 다시 확인하세요.", color = MaterialTheme.colorScheme.error)
        }
    }
    SensorRow("현재 자기장", sensorSnapshot.hasMagneticField, sensorSnapshot.magneticTotalUt?.let { "%.1f μT".format(it) })
    var wifiClockMs by remember { mutableLongStateOf(SystemClock.elapsedRealtime()) }
    LaunchedEffect(anchorCollectionActive) {
        while (anchorCollectionActive) {
            wifiClockMs = SystemClock.elapsedRealtime()
            delay(250)
        }
    }
    val waitingSeconds = wifiCalibrationSnapshot.requestStartedElapsedMs?.let { (wifiClockMs - it).coerceAtLeast(0L) }
    val freshAgoSeconds = wifiCalibrationSnapshot.lastFreshElapsedMs?.let { (wifiClockMs - it).coerceAtLeast(0L) }
    val nextRequestRemainingMs = wifiCalibrationSnapshot.lastRequestElapsedMs?.let {
        (WIFI_SCAN_REQUEST_INTERVAL_MS - (wifiClockMs - it)).coerceAtLeast(0L)
    } ?: 0L
    val scanRequestAllowed = !wifiCalibrationSnapshot.waitingForResult && nextRequestRemainingMs == 0L
    val apTiming = when {
        wifiCalibrationSnapshot.waitingForResult && waitingSeconds != null -> "새 AP 결과 대기 ${formatWifiSeconds(waitingSeconds)}"
        wifiCalibrationSnapshot.lastResultWaitMs != null -> "마지막 응답까지 ${formatWifiSeconds(wifiCalibrationSnapshot.lastResultWaitMs)}"
        else -> "아직 AP 응답 없음"
    }
    val nextScanTiming = if (nextRequestRemainingMs > 0L) {
        "다음 새 AP 요청까지 ${formatWifiSeconds(nextRequestRemainingMs)}"
    } else {
        "지금 새 AP 요청 가능"
    }
    StatusCard(
        "AP 수집 상태",
            "${wifiCalibrationSnapshot.status}\n$apTiming · $nextScanTiming\n요청 ${wifiCalibrationSnapshot.requestCount}회 · 새 결과 ${wifiCalibrationSnapshot.freshResultCount}회 · 이전 결과 ${wifiCalibrationSnapshot.staleResultCount}회\n최근 ${wifiCalibrationSnapshot.apCount}개" +
            (freshAgoSeconds?.let { " · 마지막 새 결과 ${formatWifiSeconds(it)} 전" } ?: "") +
            "\n새 결과가 1회 이상이어야 AP 지문 후보로 셉니다.",
    )
    StatusCard(
        "BLE 수집 상태",
        "${bleSurveySnapshot.status} · 송신기 ${bleSurveySnapshot.transmitterCount}개 · 관측 ${bleSurveySnapshot.observationCount}회",
    )
    if (!anchorCollectionActive) {
        Button(
            onClick = {
                val selectedFloor = floor ?: return@Button
                anchorCollectionActive = true
                onStartAnchor(selectedFloor, anchorType, anchorDetail)
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = !recordingSnapshot.active && floor != null && detailMatchesFloor,
        ) {
            Text("${floor ?: "-"}층 다중 센서+AP+BLE 기준점 측정 시작")
        }
    } else {
        Button(
            onClick = onScanAnchorWifi,
            modifier = Modifier.fillMaxWidth(),
            enabled = scanRequestAllowed,
        ) {
            Text(
                when {
                    wifiCalibrationSnapshot.waitingForResult -> "새 AP 결과 대기 중…"
                    nextRequestRemainingMs > 0L -> "다음 AP 요청까지 ${formatWifiSeconds(nextRequestRemainingMs)}"
                    else -> "새 AP 스캔 요청 · BLE 연속 수집"
                },
            )
        }
        Button(
            onClick = {
                onStop()
                anchorCollectionActive = false
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("기준점 측정 종료 및 저장")
        }
    }
    if (anchorCollectionActive) {
        StatusCard("기준점 측정 중", "30초 동안 발 위치·진행 방향·휴대폰 세로 자세를 같게 유지하세요. AP는 시작 시와 버튼을 누를 때 저장되고 BLE는 최대 송신기별 초당 1회 연속 저장됩니다.")
        return
    }
    return
    }
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("경로 라벨 비교", modifier = Modifier.weight(1.35f).padding(top = 12.dp), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        if (!routeReversed) {
            Button(onClick = { routeReversed = false; nextPointIndex = 0 }, modifier = Modifier.weight(0.7f), enabled = !recordingSnapshot.active) { Text("정방향") }
        } else {
            OutlinedButton(onClick = { routeReversed = false; nextPointIndex = 0 }, modifier = Modifier.weight(0.7f), enabled = !recordingSnapshot.active) { Text("정방향") }
        }
        if (routeReversed) {
            Button(onClick = { routeReversed = true; nextPointIndex = 0 }, modifier = Modifier.weight(0.7f), enabled = !recordingSnapshot.active) { Text("역방향") }
        } else {
            OutlinedButton(onClick = { routeReversed = true; nextPointIndex = 0 }, modifier = Modifier.weight(0.7f), enabled = !recordingSnapshot.active) { Text("역방향") }
        }
    }
    floorPresets.forEach { preset ->
        OutlinedButton(
            onClick = {
                selectedPreset = preset
                nextPointIndex = 0
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = !recordingSnapshot.active && !anchorCollectionActive,
        ) {
            Text(preset.label)
        }
    }

    val preset = selectedPreset?.let { selected ->
        if (routeReversed) {
            selected.copy(
                id = "${selected.id}_REVERSE",
                label = "${selected.label} · 역방향",
                startLocation = selected.destination,
                destination = selected.startLocation,
                points = (if (selected.points.lastOrNull() == selected.destination) selected.points.dropLast(1) else selected.points).reversed() + selected.startLocation,
            )
        } else selected
    }
    if (preset == null) {
        StatusCard("경로 선택", if (floor == null) "층을 입력하세요." else "측정할 경로를 선택하세요.")
        return
    }
    StatusCard("선택 경로", "${preset.startLocation} → ${preset.destination}")
    StatusCard("시작·끝 AP 자동 수집", "시작점과 마지막 도착 랩에서 AP를 자동 요청합니다. 결과가 올 때까지 그 지점에 서 주세요. 중간 랩에서는 AP를 요청하지 않습니다. 종료를 누르면 즉시 저장하며 대기 중인 AP는 취소합니다.\n${wifiCalibrationSnapshot.status}")
    SectionTitle("측정 조작")
    if (!recordingSnapshot.active) {
        Button(
            onClick = {
                nextPointIndex = 0
                onStart(preset)
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("시작점 기록 및 측정 시작")
        }
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = {}, modifier = Modifier.weight(1.5f), enabled = false) {
                Text("현재 지점 기록")
            }
            OutlinedButton(onClick = {}, modifier = Modifier.weight(1f), enabled = false) {
                Text("측정 종료")
            }
        }
        Text("시작 후 현재 지점 기록과 측정 종료가 활성화됩니다.", color = MaterialTheme.colorScheme.onSurfaceVariant)
    } else {
        val nextPoint = preset.points.getOrNull(nextPointIndex)
        if (nextPoint != null) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = {
                        onRecordPoint(preset, nextPoint, nextPointIndex)
                        nextPointIndex += 1
                    },
                    modifier = Modifier.weight(1.5f),
                ) {
                    Text("현재 지점 기록 ${nextPointIndex + 1}/${preset.points.size}")
                }
                OutlinedButton(onClick = onStop, modifier = Modifier.weight(1f)) {
                    Text("측정 종료")
                }
            }
            Text("다음 랩: ${routePointLocation(nextPoint)}", color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            StatusCard("경로 랩 완료", "모든 지점을 기록했습니다. 측정을 종료해 파일을 저장하세요.")
            Button(onClick = onStop, modifier = Modifier.fillMaxWidth()) {
                Text("측정 종료 및 저장")
            }
        }
    }
    SectionTitle("현재 예측 · 모드 4")
    val fusionRoomCandidate = if (mapMatchingSnapshot.available && routeFusionSnapshot.floor == mapMatchingSnapshot.floor && routeFusionSnapshot.zoneLabel.contains("강의실 라인")) {
        mapMatchingSnapshot.withFusionEstimate(routeFusionSnapshot).nearestRoomLabel
    } else null
    if (recordingSnapshot.active && routeFusionSnapshot.active && routeFusionSnapshot.x != null && routeFusionSnapshot.y != null) {
        StatusCard(
            "${routeFusionSnapshot.floor ?: floor ?: "-"}층 · ${routeFusionSnapshot.zoneLabel}",
            (fusionRoomCandidate?.let { "지도상 가까운 강의실 후보: $it 앞 (도면 기준)\n" } ?: "") +
                "x=${format(routeFusionSnapshot.x.toFloat())}, y=${format(routeFusionSnapshot.y.toFloat())}\n" +
                "자기장 ${routeFusionSnapshot.magneticApplied}/${routeFusionSnapshot.magneticEvaluated} (${if (routeFusionSnapshot.magneticStrategy == "grid_primary_v2_fallback") "격자 우선·V2 보조" else "V2"}) · " +
                "BLE ${routeFusionSnapshot.bleApplied}/${routeFusionSnapshot.bleEvaluated} · ${routeFusionSnapshot.reason}",
        )
    } else {
        StatusCard(
            "예측 대기",
            if (recordingSnapshot.active) routeFusionStatus
            else "측정을 시작하면 모드 4(PDR+지도+자기장+BLE)의 위치를 표시합니다.",
        )
    }
    if (recordingSnapshot.active && mapMatchingSnapshot.available) {
        StatusCard(
            "비교 기준선 · 기존 PDR",
            "${mapMatchingSnapshot.floor}층 · ${mapMatchingSnapshot.corridorLabel} · " +
                "x=${format(mapMatchingSnapshot.matchedX.toFloat())}, y=${format(mapMatchingSnapshot.matchedY.toFloat())}",
        )
    }
    SensorRow("현재 걸음 센서", sensorSnapshot.hasStepCounter, sensorSnapshot.totalSteps?.toString())
    StatusCard("저장 상태", recordingSnapshot.status)
}

@androidx.compose.runtime.Composable
private fun SectionTitle(text: String) {
    Spacer(Modifier.height(4.dp))
    Text(text, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
}

@androidx.compose.runtime.Composable
private fun StatusCard(title: String, value: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(title, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text(value)
        }
    }
}

private const val WIFI_SCAN_REQUEST_INTERVAL_MS = 30_000L

private fun formatWifiSeconds(milliseconds: Long): String = "%.1f초".format(Locale.getDefault(), milliseconds / 1000.0)

@androidx.compose.runtime.Composable
private fun SensorRow(label: String, supported: Boolean, value: String?) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label)
        Text(
            text = when {
                !supported -> "센서 없음"
                value == null -> "측정 대기"
                else -> value
            },
            color = if (supported) MaterialTheme.colorScheme.primary else Color.Gray,
            fontWeight = FontWeight.Medium,
        )
    }
    HorizontalDivider()
}

@androidx.compose.runtime.Composable
private fun WebFloorMap(floor: Int, show3d: Boolean = false) {
    val context = LocalContext.current
    val page = if (show3d) "clay.html" else "index.html"
    val viewKey = "$floor:$page"
    AndroidView(
        modifier = Modifier
            .fillMaxWidth()
            .height(560.dp),
        factory = {
            WebView(it).apply {
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.allowFileAccess = false
                settings.allowContentAccess = false
                webViewClient = IndoorMapAssetClient(context.applicationContext)
                tag = viewKey
                loadUrl("https://appassets.androidplatform.net/assets/$page?floor=$floor&embed=1")
            }
        },
        update = { webView ->
            if (webView.tag != viewKey) {
                webView.tag = viewKey
                webView.loadUrl("https://appassets.androidplatform.net/assets/$page?floor=$floor&embed=1")
            }
        },
    )
}

private class IndoorMapAssetClient(private val context: Context) : WebViewClient() {
    override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
        val url = request.url
        if (url.scheme != "https" || url.host != "appassets.androidplatform.net") return super.shouldInterceptRequest(view, request)
        val assetPath = url.path?.removePrefix("/assets/") ?: return null
        if (assetPath.isBlank() || assetPath.contains("..")) return null
        return try {
            WebResourceResponse(mimeType(assetPath), "utf-8", context.assets.open(assetPath))
        } catch (_: Exception) {
            WebResourceResponse("text/plain", "utf-8", null)
        }
    }

    private fun mimeType(path: String): String = when (path.substringAfterLast('.', "").lowercase()) {
        "html" -> "text/html"
        "css" -> "text/css"
        "js" -> "text/javascript"
        "json" -> "application/json"
        "svg" -> "image/svg+xml"
        else -> "application/octet-stream"
    }
}

@androidx.compose.runtime.Composable
private fun FloorMapPreview(snapshot: MapMatchingSnapshot) {
    if (!snapshot.available) return
    val labelPaint = Paint().apply {
        color = android.graphics.Color.DKGRAY
        textAlign = Paint.Align.CENTER
        textSize = 20f
        isAntiAlias = true
    }
    Text("${snapshot.floor}층 현재 위치 · 파랑=정합 위치, 회색=원시 PDR", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
    Canvas(modifier = Modifier.fillMaxWidth().height(260.dp)) {
        val centerY = size.height / 2f
        fun x(value: Double) = (value / snapshot.mainLength * size.width).toFloat()
        fun y(value: Double) = centerY - (value * 8.5).toFloat()
        drawRoundRect(Color(0xFFF2F5FB), size = size)
        drawLine(Color(0xFF59667A), androidx.compose.ui.geometry.Offset(0f, centerY), androidx.compose.ui.geometry.Offset(size.width, centerY), 12f)
        if (snapshot.floor != 1) {
            drawLine(
                Color(0xFF59667A),
                androidx.compose.ui.geometry.Offset(x(snapshot.startX), y(-10.37)),
                androidx.compose.ui.geometry.Offset(x(snapshot.startX), centerY),
                12f,
            )
        }
        snapshot.rooms.forEach { room ->
            val roomWidth = (room.width / snapshot.mainLength * size.width).toFloat().coerceAtLeast(16f)
            val roomCenterY = if (room.side == "lower") centerY + 40f else centerY - 40f
            drawRoundRect(
                color = if (room.side == "lower") Color(0xFFFFE8D5) else Color(0xFFDCEBFF),
                topLeft = androidx.compose.ui.geometry.Offset(x(room.x) - roomWidth / 2f, roomCenterY - 19f),
                size = androidx.compose.ui.geometry.Size(roomWidth, 38f),
            )
            drawIntoCanvas { canvas -> canvas.nativeCanvas.drawText(room.id, x(room.x), roomCenterY + 7f, labelPaint) }
        }
        drawCircle(Color(0xFF80868B), 11f, androidx.compose.ui.geometry.Offset(x(snapshot.rawX), y(snapshot.rawY)))
        drawCircle(Color(0xFF1769E0), 13f, androidx.compose.ui.geometry.Offset(x(snapshot.matchedX), y(snapshot.matchedY)))
        drawCircle(Color.White, 4f, androidx.compose.ui.geometry.Offset(x(snapshot.matchedX), y(snapshot.matchedY)))
    }
}

private fun format(value: Float): String = String.format(Locale.US, "%.2f", value)
