package com.example.indoorpositioning

import org.junit.Assert.*
import org.junit.Test

class EventApPolicyTest {
    @Test fun turnWorksAwayFromAnchorsAndAcrossNorth() {
        val p = EventApPolicy()
        assertNull(p.update(0, 0, 350.0, false))
        assertNull(p.update(500, 1, 75.0, false))
        assertNull(p.update(1_000, 2, 77.0, false))
        val request = p.update(1_500, 3, 75.0, false)
        assertEquals("walking_turn", request?.reason)
        assertEquals(1, request?.attempt)
    }
    @Test fun stationaryRotationAndContinuousSpinningDoNotScan() {
        val p = EventApPolicy()
        p.update(0, 0, 0.0, false)
        repeat(20) { assertNull(p.update((it + 1) * 200L, 0, 90.0, false)) }
        p.reset(); p.update(0, 0, 0.0, false)
        repeat(20) { assertNull(p.update((it + 1) * 200L, it / 3, ((it + 1) * 45.0) % 360, false)) }
    }
    @Test fun acceptedEventStopsAndAmbiguousEventGetsOnlyOneRetry() {
        val p = EventApPolicy()
        val first = p.update(0, 0, null, false, "core", "코어")!!
        p.result(first.id, false, 1_000)
        assertNull(p.update(15_999, 0, null, false))
        val second = p.update(16_000, 0, null, false)!!
        assertEquals(2, second.attempt)
        p.result(second.id, false, 17_000)
        assertNull(p.update(35_000, 0, null, false))
        val next = p.update(40_000, 0, null, false, "stairs", "계단")!!
        p.result(next.id, true, 41_000)
        assertNull(p.update(60_000, 0, null, false))
    }
    @Test fun permissionOrBudgetDenialDoesNotCauseRetryStorm() {
        val p = EventApPolicy()
        val first = p.update(0, 0, null, false, "core")!!
        p.result(first.id, false, 1, retryAllowed = false)
        repeat(100) { assertNull(p.update(it * 500L + 2, 0, null, false)) }
    }
    @Test fun uncertaintyRequiresPersistenceAndDoesNotNeedAnchor() {
        val p = EventApPolicy()
        repeat(4) { assertNull(p.update(it * 1_000L, it, null, true)) }
        assertEquals("tracking_uncertain", p.update(4_000, 4, null, true)?.reason)
    }
    @Test fun staleHeadingGapCannotConfirmTurn() {
        val p = EventApPolicy()
        p.update(0, 0, 0.0, false); p.update(500, 1, 90.0, false)
        assertNull(p.update(10_000, 4, 90.0, false))
        assertNull(p.update(11_000, 6, null, false))
    }
    @Test fun budgetIsSharedAndPendingOwnerCannotBeClearedByOtherScreen() {
        val b = ApScanBudget(); val a = Any(); val c = Any()
        assertTrue(b.acquire(a, 0).allowed)
        assertFalse(b.acquire(c, 6_000).allowed)
        b.finish(c); assertFalse(b.acquire(c, 6_000).allowed)
        b.finish(a); assertTrue(b.acquire(c, 6_000).allowed)
    }
    @Test fun rollingBudgetAndEmergencyReserveSurviveScreenChanges() {
        val b = ApScanBudget(); val owner = Any()
        listOf(0L, 5_000L, 10_000L).forEach { assertTrue(b.acquire(owner, it, true).allowed); b.finish(owner) }
        assertFalse(b.acquire(Any(), 15_000, true).allowed)
        assertTrue(b.acquire(owner, 15_000).allowed); b.finish(owner)
        assertFalse(b.acquire(owner, 119_999).allowed)
        assertTrue(b.acquire(owner, 120_000).allowed)
    }
    @Test fun sessionResetCannotUseAnOldHeadingOrPendingEvent() {
        val p = EventApPolicy(); p.update(0, 0, 0.0, false, "core")
        p.reset(); assertNull(p.update(20_000, 10, 90.0, false))
    }
    @Test fun coordinatorTurnWorksInCorridorWithoutAnchor() {
        val c = GuidanceApCoordinator()
        val m = MapMatchingSnapshot(available = true, tracking = true, matchedX = 40.0)
        assertNull(c.updateWithMotion(m, 0, 0, 355.0, false))
        assertNull(c.updateWithMotion(m, 500, 1, 85.0, false))
        assertEquals("walking_turn", c.updateWithMotion(m, 1_500, 3, 85.0, false)?.reason)
        c.stop(); assertNull(c.updateWithMotion(m.copy(tracking = false), 2_000, 4, 85.0, false))
    }
}
