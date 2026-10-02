package com.example.indoorpositioning

import android.Manifest
import android.bluetooth.BluetoothManager
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import java.security.MessageDigest

data class BleEnvironmentObservation(
    val anonymousId: String,
    val identifierSource: String,
    val rssiDbm: Int,
    val txPowerDbm: Int?,
    val serviceUuids: List<String>,
    val manufacturerDataPresent: Boolean,
    val manufacturerPayloadHashes: List<String>,
    val serviceDataHashes: List<String>,
    val connectable: Boolean,
    val scanTimestampNs: Long,
)

data class BleSurveySnapshot(
    val active: Boolean = false,
    val status: String = "BLE 스캔 대기",
    val transmitterCount: Int = 0,
    val observationCount: Int = 0,
)

internal fun anonymousBleId(value: String): String {
    val digest = MessageDigest.getInstance("SHA-256")
        .digest("IT_BUILDING_ANDROID_BLE_SURVEY_V1:$value".toByteArray(Charsets.UTF_8))
    return digest.take(8).joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
}

// Diagnostic candidates only. Advertisement payloads may contain rotating
// bytes; these hashes are not treated as stable positioning IDs until a
// separate-day repeatability test passes. Never persist the raw payload.
internal fun anonymousBlePayloadId(kind: String, source: String, payload: ByteArray): String {
    val prefix = "IT_BUILDING_ANDROID_BLE_PAYLOAD_V1:$kind:$source:".toByteArray(Charsets.UTF_8)
    val digest = MessageDigest.getInstance("SHA-256").digest(prefix + payload)
    return digest.take(8).joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
}

internal class BleObservationPolicy(private val minimumIntervalMs: Long = 1_000L) {
    private val lastRecordedAt = mutableMapOf<String, Long>()

    fun shouldRecord(identifier: String, nowMs: Long): Boolean {
        val previous = lastRecordedAt[identifier]
        if (previous != null && nowMs - previous < minimumIntervalMs) return false
        lastRecordedAt[identifier] = nowMs
        return true
    }

    fun reset() = lastRecordedAt.clear()
}

class BleEnvironmentScanner(
    context: Context,
    private val onObservation: (BleEnvironmentObservation) -> Unit,
    private val onSnapshot: (BleSurveySnapshot) -> Unit,
) {
    private val appContext = context.applicationContext
    private val bluetoothManager = appContext.getSystemService(BluetoothManager::class.java)
    private val observationPolicy = BleObservationPolicy()
    private val transmitters = mutableSetOf<String>()
    private var active = false
    private var observationCount = 0

    private val callback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            handleResult(result)
        }

        override fun onBatchScanResults(results: MutableList<ScanResult>) {
            results.forEach(::handleResult)
        }

        override fun onScanFailed(errorCode: Int) {
            active = false
            emit("BLE 스캔 실패 · 코드 $errorCode")
        }
    }

    fun start(): BleSurveySnapshot {
        if (!appContext.packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)) {
            return emit("이 기기는 BLE 스캔을 지원하지 않습니다.")
        }
        if (!hasRequiredPermissions()) {
            return emit("BLE 수집 권한이 필요합니다.")
        }
        val adapter = bluetoothManager?.adapter
            ?: return emit("Bluetooth 어댑터를 찾지 못했습니다.")
        if (!adapter.isEnabled) return emit("Bluetooth를 켠 뒤 다시 시작하세요.")
        val scanner = try {
            adapter.bluetoothLeScanner
        } catch (_: SecurityException) {
            null
        } ?: return emit("BLE 스캐너를 열지 못했습니다.")

        if (active) stop()
        observationPolicy.reset()
        transmitters.clear()
        observationCount = 0
        active = true
        return try {
            val settings = ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .setCallbackType(ScanSettings.CALLBACK_TYPE_ALL_MATCHES)
                .build()
            scanner.startScan(null, settings, callback)
            emit("BLE 연속 스캔 중")
        } catch (_: SecurityException) {
            active = false
            emit("BLE 스캔 권한을 확인하세요.")
        } catch (error: IllegalStateException) {
            active = false
            emit("BLE 스캔을 시작하지 못했습니다: ${error.message ?: "상태 오류"}")
        }
    }

    fun stop(): BleSurveySnapshot {
        val wasActive = active
        if (wasActive && hasRequiredPermissions()) {
            try {
                bluetoothManager?.adapter?.bluetoothLeScanner?.stopScan(callback)
            } catch (_: SecurityException) {
                // Permission may have been revoked while the survey was active.
            } catch (_: IllegalStateException) {
                // Bluetooth may have been disabled while the survey was active.
            }
        }
        active = false
        return if (wasActive) emit("BLE 스캔 종료") else snapshot("BLE 스캔 대기")
    }

    fun close() = stop()

    private fun handleResult(result: ScanResult) {
        if (!active) return
        val (rawIdentifier, identifierSource) = try {
            result.device.address.orEmpty() to "device_address"
        } catch (_: SecurityException) {
            result.scanRecord?.bytes?.joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }.orEmpty() to "scan_record_fallback"
        }
        if (rawIdentifier.isBlank()) return
        val anonymousId = anonymousBleId(rawIdentifier)
        transmitters += anonymousId
        val nowMs = System.currentTimeMillis()
        if (!observationPolicy.shouldRecord(anonymousId, nowMs)) return

        val record = result.scanRecord
        val manufacturerPayloadHashes = record?.manufacturerSpecificData?.let { data ->
            (0 until data.size()).mapNotNull { index ->
                data.valueAt(index)?.takeIf { it.isNotEmpty() }?.let { payload ->
                    anonymousBlePayloadId("manufacturer", data.keyAt(index).toString(), payload)
                }
            }.distinct().sorted()
        }.orEmpty()
        val serviceDataHashes = record?.serviceData.orEmpty().mapNotNull { (uuid, payload) ->
            payload.takeIf { it.isNotEmpty() }?.let {
                anonymousBlePayloadId("service", uuid.uuid.toString(), it)
            }
        }.distinct().sorted()
        val txPower = result.txPower.takeUnless { it == ScanResult.TX_POWER_NOT_PRESENT }
        observationCount += 1
        onObservation(
            BleEnvironmentObservation(
                anonymousId = anonymousId,
                identifierSource = identifierSource,
                rssiDbm = result.rssi,
                txPowerDbm = txPower,
                serviceUuids = record?.serviceUuids.orEmpty().map { it.uuid.toString() }.distinct().sorted(),
                manufacturerDataPresent = (record?.manufacturerSpecificData?.size() ?: 0) > 0,
                manufacturerPayloadHashes = manufacturerPayloadHashes,
                serviceDataHashes = serviceDataHashes,
                connectable = result.isConnectable,
                scanTimestampNs = result.timestampNanos,
            ),
        )
        emit("BLE 연속 스캔 중")
    }

    private fun hasRequiredPermissions(): Boolean {
        val locationGranted = ContextCompat.checkSelfPermission(
            appContext,
            Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return locationGranted
        val scanGranted = ContextCompat.checkSelfPermission(
            appContext,
            Manifest.permission.BLUETOOTH_SCAN,
        ) == PackageManager.PERMISSION_GRANTED
        val connectGranted = ContextCompat.checkSelfPermission(
            appContext,
            Manifest.permission.BLUETOOTH_CONNECT,
        ) == PackageManager.PERMISSION_GRANTED
        return locationGranted && scanGranted && connectGranted
    }

    private fun emit(status: String): BleSurveySnapshot {
        val snapshot = snapshot(status)
        onSnapshot(snapshot)
        return snapshot
    }

    private fun snapshot(status: String) = BleSurveySnapshot(
            active = active,
            status = status,
            transmitterCount = transmitters.size,
            observationCount = observationCount,
        )
}
