package com.example.indoorpositioning

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.wifi.WifiManager
import android.os.Build
import android.os.SystemClock
import androidx.core.content.ContextCompat

data class WifiAccessPointSample(
    val bssid: String,
    val ssid: String,
    val rssiDbm: Int,
    val frequencyMhz: Int,
    val scanTimestampUs: Long,
)

data class WifiCalibrationSnapshot(
    val status: String = "AP 스캔 대기",
    val apCount: Int = 0,
    val resultCount: Int = 0,
    val freshResultCount: Int = 0,
    val staleResultCount: Int = 0,
    val requestCount: Int = 0,
    val waitingForResult: Boolean = false,
    val requestStartedElapsedMs: Long? = null,
    val lastRequestElapsedMs: Long? = null,
    val lastResultWaitMs: Long? = null,
    val lastFreshElapsedMs: Long? = null,
)

class WifiFingerprintScanner(
    context: Context,
    private val onRequestStarted: (Long) -> Unit,
    private val onResult: (List<WifiAccessPointSample>, Boolean, String, Long?, Long) -> Unit,
) {
    private val appContext = context.applicationContext
    private val wifiManager = appContext.getSystemService(WifiManager::class.java)
    private val timeoutHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private val timeoutTask = Runnable { if (pendingRequest) deliver(false, "AP 응답 시간 초과 · 새 기준지문으로 사용하지 않음") }
    private var registered = false
    private var pendingRequest = false
    private var requestStartedElapsedMs: Long? = null

    private val receiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action != WifiManager.SCAN_RESULTS_AVAILABLE_ACTION) return
            if (!pendingRequest) return
            val fresh = intent.getBooleanExtra(WifiManager.EXTRA_RESULTS_UPDATED, false)
            deliver(fresh, if (fresh) "새 AP 스캔 기록 완료" else "최근 AP 스캔 결과 기록 완료")
        }
    }

    init {
        val filter = IntentFilter(WifiManager.SCAN_RESULTS_AVAILABLE_ACTION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            appContext.registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("DEPRECATION")
            appContext.registerReceiver(receiver, filter)
        }
        registered = true
    }

    fun scan(): Boolean {
        if (ContextCompat.checkSelfPermission(appContext, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            onResult(emptyList(), false, "AP 수집에는 위치 권한이 필요합니다.", null, SystemClock.elapsedRealtime())
            return true
        }
        if (pendingRequest) return false
        pendingRequest = true
        requestStartedElapsedMs = SystemClock.elapsedRealtime()
        onRequestStarted(requestStartedElapsedMs!!)
        timeoutHandler.postDelayed(timeoutTask, 20_000L)
        @Suppress("DEPRECATION")
        val started = wifiManager.startScan()
        if (!started) {
            deliver(false, "새 스캔이 제한되어 최근 AP 결과를 기록했습니다.")
        }
        return true
    }

    fun cancelPending() {
        timeoutHandler.removeCallbacks(timeoutTask)
        pendingRequest = false
        requestStartedElapsedMs = null
    }

    fun close() {
        cancelPending()
        if (registered) {
            appContext.unregisterReceiver(receiver)
            registered = false
        }
    }

    private fun deliver(fresh: Boolean, status: String) {
        timeoutHandler.removeCallbacks(timeoutTask)
        pendingRequest = false
        val resultElapsedMs = SystemClock.elapsedRealtime()
        val requestElapsedMs = requestStartedElapsedMs
        requestStartedElapsedMs = null
        val samples = try {
            @Suppress("DEPRECATION")
            wifiManager.scanResults
                .map { result ->
                    WifiAccessPointSample(
                        bssid = result.BSSID.orEmpty(),
                        ssid = result.SSID.orEmpty(),
                        rssiDbm = result.level,
                        frequencyMhz = result.frequency,
                        scanTimestampUs = result.timestamp,
                    )
                }
                .filter { it.bssid.isNotBlank() }
                .sortedByDescending { it.rssiDbm }
        } catch (error: SecurityException) {
            onResult(emptyList(), false, "AP 결과를 읽지 못했습니다: 위치 권한을 확인하세요.", requestElapsedMs, resultElapsedMs)
            return
        }
        onResult(samples, fresh, status, requestElapsedMs, resultElapsedMs)
    }
}
