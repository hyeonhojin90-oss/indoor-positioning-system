package com.example.indoorpositioning

import org.junit.Test

import org.junit.Assert.*

/**
 * Example local unit test, which will execute on the development machine (host).
 *
 * See [testing documentation](http://d.android.com/tools/testing).
 */
class ExampleUnitTest {
    @Test
    fun routePointLocationDoesNotDuplicateAlreadyFormattedPosition() {
        assertEquals("오른쪽 끝 화장실 통로 앞", routePointLocation("오른쪽 끝 화장실 통로 앞"))
        assertEquals("코어복도 출구 중앙점", routePointLocation("코어복도 출구 중앙점"))
        assertEquals("4204 앞", routePointLocation("4204"))
    }
    @Test
    fun floorTwoStudyAndExtensionDoNotRouteThrough2107() {
        val routes = specialRoutePresets(2)
        assertFalse(routes.any { it.id == "2F_2107_OPEN" })
        assertFalse(routes.any { it.id == "2F_STUDY_V3" })
        val revised = routes.filter { it.id.endsWith("_V3") }
        assertEquals(1, revised.size)
        val extension = routes.first { it.id == "2F_EXTENSION_V3" }
        assertTrue(extension.startLocation.contains("TDM"))
        assertFalse(revised.flatMap { it.points }.any { it.contains("2107") })
        assertFalse(revised.flatMap { it.points }.any { it.contains("책상공간") })
    }

    @Test
    fun floorTwoAnchorsAndExtensionRouteUseSpecificCollectionLocations() {
        assertFalse(sensorAnchorTypesForFloor(2).any { it.startsWith("2107 진입 전") })
        assertFalse(sensorAnchorTypesForFloor(2).any { it.startsWith("2105-2 앞") })
        assertTrue(sensorAnchorTypesForFloor(2).any { it.startsWith("기둥·TDM 사이") })
        assertTrue(sensorAnchorTypesForFloor(2).any { it.startsWith("2105-1 앞") })
        assertEquals("f2_extension_2104_1", zoneIdForLabel("2104-1 앞 · 2104-1 가로폭 중앙 정면 · 증축복도 중앙선"))
        assertEquals("f2_extension_2105_1", zoneIdForLabel("2105-1 앞 · 2105-1 가로폭 중앙 정면 · 증축복도 중앙선"))
        val extension = specialRoutePresets(2).first { it.id == "2F_EXTENSION_V3" }
        assertEquals(
            listOf(
                "기둥·TDM 사이 · 메인복도와 증축복도 중심축 교차점",
                "TDM 옆 · TDM 외벽 가로폭 중앙 정면 · 증축복도 중앙선",
                "2105-1·2104-1 사이 · 증축복도 중앙선",
                "2105-2·2104-2 사이 · 증축복도 중앙선",
                "증축복도 계단 진입 전 · 복도 중앙선",
            ),
            extension.points,
        )
    }

    @Test
    fun floorTwoAnchorGroupsSeparateBothMainCorridorsAndExtension() {
        val groups = sensorAnchorGroupsForFloor(2)
        assertEquals(listOf("왼쪽복도", "코어", "오른쪽 메인복도", "증축복도", "복도 내부 · 위치 직접 입력"), groups.keys.toList())
        assertTrue(groups.getValue("왼쪽복도").all { it.startsWith("왼쪽") })
        assertTrue(groups.getValue("코어").single().startsWith("코어 교차점"))
        assertTrue(groups.getValue("오른쪽 메인복도").any { it.startsWith("기둥·TDM 사이") })
        assertEquals(1, groups.getValue("증축복도").size)
        assertTrue(groups.getValue("증축복도").single().startsWith("2105-1 앞"))
        assertEquals(groups.values.flatten(), sensorAnchorTypesForFloor(2))
    }

    @Test
    fun anchorCollectionLocationsRequireRepeatablePhysicalReferences() {
        assertTrue(anchorDetailRequired("오른쪽 강의실 라인"))
        assertFalse(anchorDetailRequired("오른쪽 계단 앞 · 출입문 정면 · 메인복도 중앙선"))
        assertTrue(anchorCollectionInstruction("오른쪽 계단 내부 · 출입문 통과 후 첫 계단참 중앙").contains("첫 계단참"))
        assertFalse(sensorAnchorTypesForFloor(2).any { it.startsWith("왼쪽 계단 내부") })
        listOf(1, 4, 5, 6, 7, 8, 9, 10).forEach { floor ->
            val anchors = sensorAnchorTypesForFloor(floor)
            assertEquals(6, anchors.size)
            assertEquals(2, anchors.count { anchorDetailRequired(it) })
        }
        assertTrue(sensorAnchorTypesForFloor(3).any { it.contains("강의실 라인") })
    }

    @Test
    fun oppositeStepsAreBufferedUntilThirdStepConfirmsTurn() {
        val tracker = CorridorDirectionTracker(requiredOppositeSteps = 3)
        assertEquals(1, tracker.observe(1).appliedSteps)

        val first = tracker.observe(-1)
        val second = tracker.observe(-1)
        val third = tracker.observe(-1)

        assertEquals(0, first.appliedSteps)
        assertEquals(1, first.pendingSteps)
        assertEquals(0, second.appliedSteps)
        assertEquals(2, second.pendingSteps)
        assertEquals(-1, third.directionSign)
        assertEquals(3, third.appliedSteps)
        assertEquals(0, third.pendingSteps)
    }

    @Test
    fun cancelledTurnReplaysBufferedStepsInConfirmedDirection() {
        val tracker = CorridorDirectionTracker(requiredOppositeSteps = 3)
        tracker.observe(1)
        tracker.observe(-1)
        tracker.observe(-1)
        val cancelled = tracker.observe(1)

        assertEquals(1, cancelled.directionSign)
        assertEquals(3, cancelled.appliedSteps)
        assertTrue(cancelled.status.contains("복원"))
    }

    @Test
    fun guidanceApRequestsOnlyOnAnchorEntryAndUsesCooldownForReentry() {
        val coordinator = GuidanceApCoordinator(duplicateCooldownMs = 30_000L)
        val core = MapMatchingSnapshot(available = true, tracking = true, floor = 4, matchedX = 70.804, startX = 70.804)
        assertEquals("F4_CORE", coordinator.update(core, 1_000L)?.id)
        assertNull(coordinator.update(core, 2_000L))

        val outside = core.copy(matchedX = 40.0)
        assertNull(coordinator.update(outside, 3_000L))
        assertNull(coordinator.update(core, 20_000L))
        assertTrue(coordinator.snapshot().status.contains("재요청까지"))

        coordinator.update(outside, 21_000L)
        assertEquals("F4_CORE", coordinator.update(core, 31_000L)?.id)
    }

    @Test
    fun floorTwoGuidanceAddsExtensionEntryNear2204() {
        val coordinator = GuidanceApCoordinator()
        val map = MapMatchingSnapshot(
            available = true,
            tracking = true,
            floor = 2,
            matchedX = 9.435,
            startX = 70.804,
            rooms = listOf(MapRoom("2204", 9.435, 0.0, 7.661, "lower")),
        )
        assertEquals("F2_EXTENSION_ENTRY", coordinator.update(map, 10_000L)?.id)
    }

    @Test
    fun floorThreeGuidanceAndCollectionUse3203ExtensionEntry() {
        val anchorLabel = sensorAnchorTypesForFloor(3).first { it.startsWith("3203 문 정면") }
        assertTrue(anchorLabel.contains("증축복도 진입 가능 구간 기준점"))
        assertEquals("f3_extension_entry", zoneIdForLabel(anchorLabel))

        val coordinator = GuidanceApCoordinator()
        val map = MapMatchingSnapshot(
            available = true,
            tracking = true,
            floor = 3,
            matchedX = 13.433,
            startX = 70.804,
            rooms = listOf(MapRoom("3203", 13.433, 0.0, 15.659, "lower")),
        )
        val trigger = coordinator.update(map.copy(matchedX = 9.0), 10_000L)
        assertEquals("F3_EXTENSION_ENTRY", trigger?.id)
        assertTrue(trigger?.label?.contains("3203~화장실 통로 사이") == true)
        assertNull(coordinator.update(map.copy(matchedX = 4.0), 11_000L))
    }

    @Test
    fun floorTwoNearbySpacesUseMainCorridorApproachDestinations() {
        val measured = listOf(
            NavigationDestination(2, "2210-1", "2210-1", 38.47),
            NavigationDestination(2, "2205", "서버실 2205", 20.84),
            NavigationDestination(2, "2204", "2204", 9.435),
        )
        val approaches = floorTwoMainCorridorApproachDestinations(measured).associateBy { it.id }
        assertEquals(setOf("2107", "STUDY", "M-SPACE", "TDM"), approaches.keys)
        assertEquals((38.47 + 20.84) / 2.0, approaches.getValue("STUDY").x, 1e-9)
        assertEquals(9.435, approaches.getValue("TDM").x, 1e-9)
        assertTrue(approaches.getValue("STUDY").label.contains("근처"))
    }

    @Test
    fun guidanceCanDistinguishRightStairInteriorAfterWalkingPastEntranceLine() {
        val coordinator = GuidanceApCoordinator()
        val map = MapMatchingSnapshot(
            available = true,
            tracking = true,
            floor = 4,
            matchedX = 0.0,
            rawX = -3.0,
            startX = 70.804,
        )
        assertEquals("F4_RIGHT_STAIRS_INSIDE", coordinator.update(map, 10_000L)?.id)
    }

    @Test
    fun classroomAnchorDetailMustMatchSelectedFloor() {
        val floor5 = setOf("5119", "5209", "5227-4")
        val floor9 = setOf("9120", "9109", "9210")
        assertTrue(anchorDetailMatchesFloor(5, "왼쪽 강의실 라인", "5119 문 정면 · 복도 중앙선", floor5))
        assertTrue(anchorDetailMatchesFloor(9, "오른쪽 강의실 라인", "9120", floor9))
        assertTrue(anchorDetailMatchesFloor(5, "오른쪽 강의실 라인", "5227-4", floor5))
        assertFalse(anchorDetailMatchesFloor(9, "오른쪽 강의실 라인", "5209", floor9))
        assertFalse(anchorDetailMatchesFloor(5, "왼쪽 강의실 라인", "5519", floor5))
        assertFalse(anchorDetailMatchesFloor(5, "왼쪽 강의실 라인", "", floor5))
        assertTrue(anchorDetailMatchesFloor(9, "오른쪽 계단 앞 · 출입문 정면 · 메인복도 중앙선", "5209"))
    }
    @Test
    fun zoneLabelsPreserveSideWithoutInventingLegacySide() {
        assertEquals("main_right", zoneIdForLabel("오른쪽 강의실 라인 · 4204 앞"))
        assertEquals("main_left", zoneIdForLabel("왼쪽 강의실 라인"))
        assertEquals("stairs_right_inside", zoneIdForLabel("오른쪽 계단 내부"))
        assertNull(zoneIdForLabel("강의실 라인"))
    }

    @Test
    fun radioZoneAnchorUsesNewSchemaWithoutChangingExistingLogs() {
        assertEquals(7, schemaVersionForRouteId("F4_MULTISENSOR_RADIO_ZONE_ANCHOR_V2"))
        assertEquals(5, schemaVersionForRouteId("F4_MULTISENSOR_WIFI_ZONE_ANCHOR"))
        assertEquals(6, schemaVersionForRouteId("F4_FUSION_FREE"))
        assertEquals(9, schemaVersionForRouteId("4F_CORE_TO_RIGHT_STAIRS"))
        assertEquals(9, schemaVersionForRouteId("F4_GUIDANCE_FUSION_V1"))
    }

    @Test
    fun bleIdentifierIsStableAndDoesNotExposeRawAddress() {
        val rawAddress = "AA:BB:CC:DD:EE:FF"
        val first = anonymousBleId(rawAddress)
        val second = anonymousBleId(rawAddress)
        assertEquals(first, second)
        assertEquals(16, first.length)
        assertFalse(first.contains(rawAddress, ignoreCase = true))
        assertFalse(first.contains(":"))
    }

    @Test
    fun bleAdvertisementPayloadCandidatesAreHashedAndKeptSeparateFromAddressIds() {
        val payload = byteArrayOf(0x01, 0x23, 0x45)
        val manufacturer = anonymousBlePayloadId("manufacturer", "76", payload)
        assertEquals(manufacturer, anonymousBlePayloadId("manufacturer", "76", payload.copyOf()))
        assertNotEquals(manufacturer, anonymousBlePayloadId("manufacturer", "77", payload))
        assertNotEquals(manufacturer, anonymousBlePayloadId("service", "76", payload))
        assertNotEquals(manufacturer, anonymousBlePayloadId("manufacturer", "76", byteArrayOf(0x01, 0x23, 0x46)))
        assertEquals(16, manufacturer.length)
        assertFalse(manufacturer.contains("012345"))
    }

    @Test
    fun wifiIdentifierMatchesBundledFingerprintPolicyWithoutExposingBssid() {
        val rawBssid = "AA:BB:CC:DD:EE:FF"
        val first = anonymousWifiId(rawBssid)
        val second = anonymousWifiId(rawBssid)
        assertEquals(first, second)
        assertTrue(first.startsWith("ap_"))
        assertEquals(13, first.length)
        assertFalse(first.contains(rawBssid, ignoreCase = true))
        assertFalse(first.contains(":"))
    }

    @Test
    fun bleObservationPolicyLimitsEachTransmitterToOncePerSecond() {
        val policy = BleObservationPolicy(minimumIntervalMs = 1_000L)
        assertTrue(policy.shouldRecord("a", 1_000L))
        assertFalse(policy.shouldRecord("a", 1_999L))
        assertTrue(policy.shouldRecord("b", 1_999L))
        assertTrue(policy.shouldRecord("a", 2_000L))
        policy.reset()
        assertTrue(policy.shouldRecord("a", 2_001L))
    }

    @Test
    fun addition_isCorrect() {
        assertEquals(4, 2 + 2)
    }

    @Test
    fun floorsOneToFourMainCorridorRoutesHaveTrackingConfiguration() {
        val routes = listOf(
            1 to "1F_MAIN_ENTRANCE_TURN_LEFT",
            1 to "1F_MAIN_ENTRANCE_TURN_RIGHT",
            2 to "2F_CORE_TO_RIGHT_STAIRS",
            2 to "2F_CORE_TO_LEFT_STAIRS",
            3 to "3F_CORE_TO_RIGHT_STAIRS",
            3 to "3F_CORE_TO_LEFT_STAIRS",
            4 to "4F_CORE_TO_RIGHT_STAIRS",
            4 to "4F_CORE_TO_LEFT_STAIRS",
        )

        routes.forEach { (floor, routeId) ->
            val config = routeTrackingConfig(routeId, floor)
            assertNotNull(routeId, config)
            assertEquals(floor, config?.floor)
            assertTrue("$routeId map stride must be positive", (config?.mapUnitsPerStep ?: 0.0) > 0.0)
        }

        val reverseRight = routeTrackingConfig("4F_CORE_TO_RIGHT_STAIRS_REVERSE", 4)
        assertNotNull(reverseRight)
        assertEquals(0.0, reverseRight?.startX ?: Double.NaN, 1e-9)
        assertEquals(0.0, reverseRight?.targetHeadingDegrees ?: Double.NaN, 1e-9)

        val reverseLeft = routeTrackingConfig("4F_CORE_TO_LEFT_STAIRS_REVERSE", 4)
        assertNotNull(reverseLeft)
        assertEquals(135.407, reverseLeft?.startX ?: Double.NaN, 1e-9)
        assertEquals(180.0, reverseLeft?.targetHeadingDegrees ?: Double.NaN, 1e-9)

        assertEquals(
            listOf("2211 문 1", "2211 문 2", "2210-1 문 1", "2107 진입 가능점", "2210-1 문 2 · 2107 끝점", "2205 서버실 앞"),
            floorTwoRightMainPoints(listOf("2211", "2210-1", "2205", "2204"), "오른쪽 계단 입구").take(6),
        )
    }

    @Test
    fun floorFourRightRouteIncludesRestroomPassageBeforeStairs() {
        assertEquals(
            listOf("4204", "오른쪽 끝 화장실 통로 앞", "오른쪽 계단 입구"),
            standardMainRoutePoints(
                floor = 4,
                sideId = "RIGHT",
                orderedRoomIds = listOf("4213", "4204"),
                stairs = "오른쪽 계단 입구",
            ).takeLast(3),
        )
        assertEquals(
            listOf("4120", "왼쪽 계단 입구"),
            standardMainRoutePoints(4, "LEFT", listOf("4120"), "왼쪽 계단 입구"),
        )
    }

    @Test
    fun unsupportedSpecialRouteDoesNotPretendToHaveLiveMapMatching() {
        assertNull(routeTrackingConfig("1F_OUTDOOR_ADMIN_CORRIDOR", 1))
        assertNull(routeTrackingConfig("3F_IT_HALL", 3))
    }

    @Test
    fun destinationAutomaticallySelectsFloorPerspectiveCorridor() {
        assertEquals(
            "1F_MAIN_ENTRANCE_TURN_LEFT",
            navigationRouteId(NavigationDestination(1, "1210", "1210", 46.38)),
        )
        assertEquals(
            "1F_MAIN_ENTRANCE_TURN_RIGHT",
            navigationRouteId(NavigationDestination(1, "1122", "1122 · iSPACE", 96.09)),
        )
        assertEquals(
            "2F_CORE_TO_RIGHT_STAIRS",
            navigationRouteId(NavigationDestination(2, "2210", "2210", 39.96)),
        )
        assertEquals(
            "4F_CORE_TO_LEFT_STAIRS",
            navigationRouteId(NavigationDestination(4, "4124", "4124", 111.13)),
        )
    }

    @Test
    fun barometerTracksFloorChangesAfterOneKnownFloorCalibration() {
        val tracker = BarometricFloorTracker(requiredStableSamples = 3, smoothingWindow = 1)
        val calibrated = tracker.calibrate(floor = 4, pressureHpa = 997.22f)
        assertEquals(4, calibrated.currentFloor)

        repeat(2) {
            val pending = tracker.update(994.58f)
            assertEquals(4, pending.currentFloor)
            assertEquals(10, pending.candidateFloor)
        }
        val tenthFloor = tracker.update(994.58f)
        assertEquals(10, tenthFloor.currentFloor)

        repeat(3) { tracker.update(998.54f) }
        val firstFloor = tracker.update(998.54f)
        assertEquals(1, firstFloor.currentFloor)
    }

    @Test
    fun barometerDoesNotCommitOneTransientPressureSample() {
        val tracker = BarometricFloorTracker(requiredStableSamples = 3, smoothingWindow = 1)
        tracker.calibrate(floor = 4, pressureHpa = 997.22f)

        val transient = tracker.update(996.78f)
        assertEquals(4, transient.currentFloor)
        assertEquals(5, transient.candidateFloor)

        val returned = tracker.update(997.22f)
        assertEquals(4, returned.currentFloor)
    }

    @Test
    fun historicalPressureProvidesExperimentalFloorWithoutCalibration() {
        assertEquals(1, estimateFloorFromHistoricalPressure(998.59f).floor)
        assertEquals(4, estimateFloorFromHistoricalPressure(997.20f).floor)
        assertEquals(9, estimateFloorFromHistoricalPressure(995.00f).floor)
        assertEquals(10, estimateFloorFromHistoricalPressure(994.53f).floor)

        val tracker = BarometricFloorTracker(smoothingWindow = 1)
        val uncalibrated = tracker.update(994.96f)
        assertFalse(uncalibrated.calibrated)
        assertNull(uncalibrated.currentFloor)
        assertEquals(9, uncalibrated.experimentalAbsoluteFloor)
    }
}
