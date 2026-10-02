package com.example.indoorpositioning

import kotlin.math.abs

internal data class EventApRequest(val id: String, val reason: String, val label: String, val attempt: Int)

/** Request causes are independent of fingerprint acceptance and estimated anchor proximity. */
internal class EventApPolicy {
    private data class Event(val id: String, val reason: String, val label: String, val created: Long,
        var attempts: Int = 0, var nextAt: Long = 0, var waiting: Boolean = false)
    private var baseline: Double? = null
    private var candidate: Double? = null
    private var candidateAt = 0L
    private var candidateSteps = 0
    private var lastSampleAt: Long? = null
    private var lastSteps = 0
    private var lastTurnAt: Long? = null
    private var uncertainAt: Long? = null
    private var lastUncertainAt: Long? = null
    private var event: Event? = null
    private var serial = 0

    fun reset() {
        baseline = null; candidate = null; lastSampleAt = null; lastTurnAt = null
        uncertainAt = null; lastUncertainAt = null; event = null; serial = 0; lastSteps = 0
    }

    fun update(now: Long, steps: Int, heading: Double?, uncertain: Boolean,
               anchorId: String? = null, anchorLabel: String? = null): EventApRequest? {
        if (lastSampleAt?.let { now < it || now - it > 2_000L } == true || steps < lastSteps) {
            candidate = null; baseline = heading
        }
        lastSampleAt = now; lastSteps = steps
        if (event?.let { now - it.created > 45_000L } == true) event = null
        var turn = false
        if (heading != null && heading.isFinite()) {
            val h = (heading % 360 + 360) % 360
            val base = baseline
            if (base == null) baseline = h
            else if (difference(h, base) < 35) {
                candidate = null
            } else if (difference(h, base) >= 60) {
                if (candidate == null || difference(h, candidate!!) > 25) {
                    candidate = h; candidateAt = now; candidateSteps = steps
                } else if (now - candidateAt >= 800 && steps - candidateSteps >= 2) {
                    turn = lastTurnAt?.let { now - it >= 30_000L } ?: true
                    if (turn) lastTurnAt = now
                    baseline = h; candidate = null
                }
            }
        } else candidate = null
        if (!uncertain) uncertainAt = null
        else if (uncertainAt == null) uncertainAt = now
        val uncertaintyEvent = uncertainAt?.let { now - it >= 4_000L } == true &&
            (lastUncertainAt?.let { now - it >= 60_000L } ?: true)
        if (event == null) {
            val cause = when {
                turn -> "walking_turn" to "걸음 동반 방향 전환"
                uncertaintyEvent -> "tracking_uncertain" to "위치 추정 불확실"
                anchorId != null -> "anchor_entry" to (anchorLabel ?: anchorId)
                else -> null
            }
            if (cause != null) {
                if (uncertaintyEvent) lastUncertainAt = now
                event = Event(anchorId ?: "event-${++serial}", cause.first, cause.second, now, nextAt = now)
            }
        }
        val current = event ?: return null
        if (current.waiting || current.attempts >= 2 || now < current.nextAt) return null
        current.attempts++; current.waiting = true
        return EventApRequest(current.id, current.reason, current.label, current.attempts)
    }

    fun result(id: String, sufficient: Boolean, now: Long, retryAllowed: Boolean = true) {
        val current = event?.takeIf { it.id == id } ?: return
        if (sufficient || !retryAllowed || current.attempts >= 2) event = null
        else { current.waiting = false; current.nextAt = now + 15_000L }
    }
    private fun difference(a: Double, b: Double) = abs((a - b + 540) % 360 - 180)
}

internal data class ApBudgetDecision(val allowed: Boolean, val remainingMs: Long = 0, val reason: String = "allowed")

/** Shared across scanner instances and screens; resetting a session must not clear the OS budget. */
internal class ApScanBudget(private val windowMs: Long = 120_000L, private val maximum: Int = 4) {
    private val requests = ArrayDeque<Long>()
    private var owner: Any? = null
    @Synchronized fun acquire(requester: Any, now: Long, reserveEmergency: Boolean = false): ApBudgetDecision {
        while (requests.isNotEmpty() && now - requests.first() >= windowMs) requests.removeFirst()
        if (owner != null) return ApBudgetDecision(false, 1_000, "scan_pending")
        val limit = if (reserveEmergency) maximum - 1 else maximum
        if (requests.size >= limit) return ApBudgetDecision(false, windowMs - (now - requests.first()), "rolling_budget")
        val gap = requests.lastOrNull()?.let { 5_000L - (now - it) } ?: 0
        if (gap > 0) return ApBudgetDecision(false, gap, "minimum_gap")
        requests.addLast(now); owner = requester
        return ApBudgetDecision(true)
    }
    @Synchronized fun finish(requester: Any) { if (owner === requester) owner = null }
}

internal object AppApScanBudget { val shared = ApScanBudget() }
