package com.example.indoorpositioning

import android.content.Context
import org.json.JSONObject
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.abs

data class MapRoom(val id: String, val x: Double, val y: Double, val width: Double, val side: String)

data class MapMatchingSnapshot(
    val available: Boolean = false,
    val calibrated: Boolean = false,
    val tracking: Boolean = false,
    val floor: Int = 4,
    val routeId: String = "",
    val rawX: Double = 0.0,
    val rawY: Double = 0.0,
    val matchedX: Double = 0.0,
    val matchedY: Double = 0.0,
    val corridorLabel: String = "지도 데이터 로드 중",
    val correctionMeters: Double = 0.0,
    val totalSteps: Int? = null,
    val mainLength: Double = 135.407,
    val startX: Double = 70.804,
    val rooms: List<MapRoom> = emptyList(),
    val nearestRoomLabel: String? = null,
    val nearestRoomDistanceMeters: Double? = null,
    val destinationLabel: String? = null,
    val destinationDistanceMeters: Double? = null,
    val arrived: Boolean = false,
    val startLabel: String = "기준점",
    val directionLabel: String = "선택 경로",
    val mapUnitsPerStep: Double? = null,
    val directionStatus: String = "진행 방향 대기",
    val bufferedDirectionSteps: Int = 0,
    val note: String = "1~4층 시험 경로를 선택하세요.",
)

internal data class CorridorDirectionDecision(
    val directionSign: Int,
    val appliedSteps: Int,
    val pendingSteps: Int,
    val status: String,
)

/**
 * Holds the first opposite-direction steps instead of immediately moving the
 * estimate in the old direction. Three consecutive opposite steps confirm a
 * turn; a cancelled candidate is replayed in the confirmed direction.
 */
internal class CorridorDirectionTracker(
    private val requiredOppositeSteps: Int = 3,
) {
    private var confirmedSign = 1
    private var candidateSign: Int? = null
    private var candidateSteps = 0

    fun reset() {
        confirmedSign = 1
        candidateSign = null
        candidateSteps = 0
    }

    fun observe(observedSign: Int?): CorridorDirectionDecision {
        if (observedSign == null || observedSign == confirmedSign) {
            val replaySteps = candidateSteps + 1
            candidateSign = null
            candidateSteps = 0
            return CorridorDirectionDecision(
                directionSign = confirmedSign,
                appliedSteps = replaySteps,
                pendingSteps = 0,
                status = if (replaySteps > 1) "방향 유지 · 보류 걸음 복원" else "진행 방향 확정",
            )
        }

        if (candidateSign == observedSign) candidateSteps += 1 else {
            candidateSign = observedSign
            candidateSteps = 1
        }
        if (candidateSteps < requiredOppositeSteps) {
            return CorridorDirectionDecision(
                directionSign = confirmedSign,
                appliedSteps = 0,
                pendingSteps = candidateSteps,
                status = "방향 전환 확인 중 $candidateSteps/$requiredOppositeSteps",
            )
        }

        confirmedSign = observedSign
        val replaySteps = candidateSteps
        candidateSign = null
        candidateSteps = 0
        return CorridorDirectionDecision(
            directionSign = confirmedSign,
            appliedSteps = replaySteps,
            pendingSteps = 0,
            status = "방향 전환 확정 · 보류 $replaySteps 걸음 반영",
        )
    }
}

internal data class RouteTrackingConfig(
    val floor: Int,
    val routeId: String,
    val startLabel: String,
    val directionLabel: String,
    val targetHeadingDegrees: Double,
    val mapUnitsPerStep: Double,
    val startX: Double? = null,
)

internal fun routeTrackingConfig(routeId: String, floor: Int): RouteTrackingConfig? {
    val reverse = routeId.endsWith("_REVERSE")
    val baseRouteId = routeId.removeSuffix("_REVERSE")
    val normalStartLabel = if (floor == 1) "정문·메인복도 진입점" else "코어복도 출구 중앙점"
    val config = when (baseRouteId) {
        "1F_MAIN_ENTRANCE_TURN_LEFT" -> Triple("정문 기준 왼쪽 끝 계단 입구", 180.0, 70.804 / 74.0)
        "1F_MAIN_ENTRANCE_TURN_RIGHT" -> Triple("정문 기준 오른쪽 끝 계단 입구", 0.0, (135.407 - 70.804) / 66.0)
        "2F_CORE_TO_RIGHT_STAIRS" -> Triple("오른쪽 계단 입구", 180.0, 70.804 / 65.0)
        "2F_CORE_TO_LEFT_STAIRS" -> Triple("왼쪽 계단 입구", 0.0, (135.407 - 70.804) / 60.0)
        "3F_CORE_TO_RIGHT_STAIRS" -> Triple("오른쪽 계단 입구", 180.0, 70.804 / 70.0)
        "3F_CORE_TO_LEFT_STAIRS" -> Triple("왼쪽 계단 입구", 0.0, (135.407 - 70.804) / 66.0)
        "4F_CORE_TO_RIGHT_STAIRS" -> Triple("오른쪽 계단 입구", 180.0, 70.804 / 60.0)
        "4F_CORE_TO_LEFT_STAIRS" -> Triple("왼쪽 계단 입구", 0.0, (135.407 - 70.804) / 53.0)
        else -> return null
    }
    val reverseStartX = when {
        !reverse -> null
        baseRouteId.contains("TO_RIGHT_STAIRS") || baseRouteId.endsWith("TURN_LEFT") -> 0.0
        baseRouteId.contains("TO_LEFT_STAIRS") || baseRouteId.endsWith("TURN_RIGHT") -> 135.407
        else -> null
    }
    return RouteTrackingConfig(
        floor = floor,
        routeId = routeId,
        startLabel = if (reverse) config.first else normalStartLabel,
        directionLabel = if (reverse) normalStartLabel else config.first,
        targetHeadingDegrees = if (reverse) (config.second + 180.0) % 360.0 else config.second,
        mapUnitsPerStep = config.third,
        startX = reverseStartX,
    )
}

class FloorMapMatcher(context: Context) {
    private data class Point(val x: Double, val y: Double)
    private data class Segment(val start: Point, val end: Point, val label: String)
    private data class FloorMap(
        val floor: Int,
        val mainLength: Double,
        val start: Point,
        val rooms: List<MapRoom>,
        val segments: List<Segment>,
    )

    private val appContext = context.applicationContext
    private var floorMap: FloorMap? = null
    private var routeConfig: RouteTrackingConfig? = null
    private var rawPosition = Point(DEFAULT_START_X, 0.0)
    private var matchedPosition = rawPosition
    private var lastStepCount: Int? = null
    private var headingOffsetDegrees: Double? = null
    private var isTracking = false
    private var currentCorridor = "메인 복도 기준점"
    private var lastCorrectionMeters = 0.0
    private var loadError: String? = null
    private var destinationLabel: String? = null
    private var destinationX: Double? = null
    private val directionTracker = CorridorDirectionTracker()
    private var directionStatus = "진행 방향 대기"
    private var bufferedDirectionSteps = 0

    init {
        configureRoute(4, "4F_CORE_TO_RIGHT_STAIRS")
    }

    fun configureRoute(floor: Int, routeId: String): MapMatchingSnapshot {
        isTracking = false
        lastStepCount = null
        headingOffsetDegrees = null
        destinationLabel = null
        destinationX = null
        directionTracker.reset()
        directionStatus = "진행 방향 대기"
        bufferedDirectionSteps = 0
        routeConfig = routeTrackingConfig(routeId, floor)
        floorMap = if (floor in 1..4 && routeConfig != null) loadFloor(floor) else null
        val mapStart = floorMap?.start ?: Point(DEFAULT_START_X, 0.0)
        val start = routeConfig?.startX?.let { Point(it, 0.0) } ?: mapStart
        rawPosition = start
        matchedPosition = start
        currentCorridor = if (floor == 1) "1층 정문·메인복도 진입점" else "${floor}층 메인 복도 코어 출구"
        lastCorrectionMeters = 0.0
        if (floorMap != null) snapRawPosition()
        return snapshot(null)
    }

    fun configureDestination(
        floor: Int,
        routeId: String,
        roomLabel: String,
        roomX: Double,
    ): MapMatchingSnapshot {
        configureRoute(floor, routeId)
        routeConfig = routeConfig?.copy(directionLabel = roomLabel)
        destinationLabel = roomLabel
        destinationX = roomX
        return snapshot(null)
    }

    fun update(sensor: SensorSnapshot): MapMatchingSnapshot {
        val totalSteps = sensor.totalSteps
        if (totalSteps != null) {
            val previous = lastStepCount
            lastStepCount = totalSteps
            if (isTracking && previous != null && totalSteps > previous && headingOffsetDegrees != null) {
                repeat(min(totalSteps - previous, MAX_STEPS_PER_UPDATE)) { moveOneStep(sensor.headingDegrees) }
            }
        }
        return snapshot(totalSteps)
    }

    fun calibrateCurrentHeading(headingDegrees: Int?): MapMatchingSnapshot {
        val config = routeConfig ?: return snapshot(lastStepCount)
            .copy(note = "이 경로는 아직 실시간 정합 시험을 지원하지 않습니다.")
        if (headingDegrees == null) return snapshot(lastStepCount).copy(note = "방향 센서 값이 들어온 뒤 보정할 수 있습니다.")
        headingOffsetDegrees = config.targetHeadingDegrees - headingDegrees.toDouble()
        directionTracker.reset()
        directionStatus = "진행 방향 확정"
        bufferedDirectionSteps = 0
        return snapshot(lastStepCount).copy(note = "현재 방향을 ${config.directionLabel} 쪽 지도 방향으로 보정했습니다.")
    }

    fun reset(): MapMatchingSnapshot {
        val mapStart = floorMap?.start ?: Point(DEFAULT_START_X, 0.0)
        val start = routeConfig?.startX?.let { Point(it, 0.0) } ?: mapStart
        rawPosition = start
        matchedPosition = start
        lastStepCount = null
        isTracking = false
        directionTracker.reset()
        directionStatus = "진행 방향 대기"
        bufferedDirectionSteps = 0
        currentCorridor = if (floorMap?.floor == 1) "1층 정문·메인복도 진입점" else "${floorMap?.floor ?: "선택"}층 메인 복도 코어 출구"
        lastCorrectionMeters = 0.0
        if (floorMap != null) snapRawPosition()
        return snapshot(null).copy(note = "${routeConfig?.startLabel ?: "기준점"}으로 초기화했습니다.")
    }

    fun startTracking(currentSteps: Int?): MapMatchingSnapshot {
        val config = routeConfig ?: return snapshot(currentSteps)
            .copy(note = "1~4층의 좌·우 메인복도 경로를 선택하세요.")
        if (headingOffsetDegrees == null) return snapshot(currentSteps)
            .copy(note = "먼저 ${config.directionLabel} 쪽을 보고 지도 방향을 보정하세요.")
        isTracking = true
        lastStepCount = currentSteps
        return snapshot(currentSteps).copy(note = "실시간 정합 중입니다. ${config.directionLabel} 쪽으로 걸으세요.")
    }

    fun stopTracking(currentSteps: Int?): MapMatchingSnapshot {
        isTracking = false
        lastStepCount = currentSteps
        return snapshot(currentSteps).copy(note = "정합을 중지했습니다. 현재 강의실 후보와 좌표를 확인하세요.")
    }

    private fun loadFloor(floor: Int): FloorMap? = try {
        val base = appContext.assets.open("data/maps/floor-04.json").bufferedReader().use { JSONObject(it.readText()) }
        val current = appContext.assets.open("data/maps/floor-${floor.toString().padStart(2, '0')}.json")
            .bufferedReader().use { JSONObject(it.readText()) }
        val layout = base.getJSONObject("layout_dimensions")
        val routing = current.optJSONObject("routing")
        val startJson = if (floor == 1) routing?.optJSONObject("main_entrance_junction") else routing?.optJSONObject("hub_junction")
        val start = startJson?.toPoint() ?: Point(DEFAULT_START_X, 0.0)
        loadError = null
        FloorMap(
            floor = floor,
            mainLength = layout.getDouble("main_length"),
            start = start,
            rooms = parseRooms(current),
            segments = parseSegments(base, floor),
        )
    } catch (error: Exception) {
        loadError = error.message ?: error.javaClass.simpleName
        null
    }

    private fun moveOneStep(headingDegrees: Int?) {
        val config = routeConfig ?: return
        if (headingDegrees == null) return
        val mapHeadingDegrees = headingDegrees + (headingOffsetDegrees ?: return)
        val observedSign = corridorDirectionSign(mapHeadingDegrees, config.targetHeadingDegrees)
        val decision = directionTracker.observe(observedSign)
        directionStatus = decision.status
        bufferedDirectionSteps = decision.pendingSteps
        if (decision.appliedSteps == 0) return
        val routeHeading = Math.toRadians(config.targetHeadingDegrees)
        val distance = config.mapUnitsPerStep * decision.appliedSteps * decision.directionSign
        rawPosition = Point(
            rawPosition.x + cos(routeHeading) * distance,
            rawPosition.y + sin(routeHeading) * distance,
        )
        snapRawPosition()
    }

    private fun corridorDirectionSign(mapHeadingDegrees: Double, targetHeadingDegrees: Double): Int? {
        val delta = ((mapHeadingDegrees - targetHeadingDegrees + 540.0) % 360.0) - 180.0
        return when {
            abs(delta) <= DIRECTION_AXIS_TOLERANCE_DEGREES -> 1
            abs(abs(delta) - 180.0) <= DIRECTION_AXIS_TOLERANCE_DEGREES -> -1
            else -> null
        }
    }

    private fun snapRawPosition() {
        val best = floorMap?.segments.orEmpty()
            .map { segment -> segment to closestPoint(rawPosition, segment) }
            .minByOrNull { (_, candidate) -> distance(rawPosition, candidate) }
            ?: return
        matchedPosition = best.second
        currentCorridor = best.first.label
        lastCorrectionMeters = distance(rawPosition, matchedPosition)
    }

    private fun snapshot(totalSteps: Int?): MapMatchingSnapshot {
        val config = routeConfig
        val map = floorMap
        if (config == null) {
            return MapMatchingSnapshot(
                floor = map?.floor ?: 0,
                note = "실시간 정합은 현재 1~4층 좌·우 메인복도 경로만 지원합니다.",
            )
        }
        if (map == null) {
            return MapMatchingSnapshot(
                floor = config.floor,
                routeId = config.routeId,
                startLabel = config.startLabel,
                directionLabel = config.directionLabel,
                note = "${config.floor}층 지도 데이터를 읽지 못했습니다: ${loadError ?: "원인 미상"}",
            )
        }
        val calibrated = headingOffsetDegrees != null
        val nearestRoom = map.rooms.minByOrNull { room -> hypot(matchedPosition.x - room.x, matchedPosition.y - room.y) }
        val nearestDistance = nearestRoom?.let { hypot(matchedPosition.x - it.x, matchedPosition.y - it.y) }
        val destinationDistance = destinationX?.let { abs(matchedPosition.x - it) }
        val arrived = destinationDistance != null && destinationDistance <= ARRIVAL_RADIUS_MAP_UNITS
        return MapMatchingSnapshot(
            available = true,
            calibrated = calibrated,
            tracking = isTracking,
            floor = map.floor,
            routeId = config.routeId,
            rawX = rawPosition.x,
            rawY = rawPosition.y,
            matchedX = matchedPosition.x,
            matchedY = matchedPosition.y,
            corridorLabel = currentCorridor,
            correctionMeters = lastCorrectionMeters,
            totalSteps = totalSteps,
            mainLength = map.mainLength,
            startX = map.start.x,
            rooms = map.rooms,
            nearestRoomLabel = nearestRoom?.id,
            nearestRoomDistanceMeters = nearestDistance,
            destinationLabel = destinationLabel,
            destinationDistanceMeters = destinationDistance,
            arrived = arrived,
            startLabel = config.startLabel,
            directionLabel = config.directionLabel,
            mapUnitsPerStep = config.mapUnitsPerStep,
            directionStatus = directionStatus,
            bufferedDirectionSteps = bufferedDirectionSteps,
            note = when {
                arrived -> "${destinationLabel ?: "목적지"}에 도착했습니다."
                !calibrated -> "${config.startLabel}에 선 뒤 ${config.directionLabel} 쪽을 보고 방향 보정을 누르세요."
                isTracking && bufferedDirectionSteps > 0 -> directionStatus
                isTracking -> "실시간 정합 중: 걸음마다 메인복도 중심선으로 보정합니다."
                else -> "지도 방향 보정 완료. 실시간 정합 시작을 누르세요."
            },
        )
    }

    private fun parseSegments(map: JSONObject, floor: Int): List<Segment> {
        val corridors = map.getJSONArray("corridors")
        return buildList {
            for (index in 0 until corridors.length()) {
                val corridor = corridors.getJSONObject(index)
                val path = corridor.getJSONArray("path")
                for (pointIndex in 0 until path.length() - 1) {
                    val label = corridor.optString("label", "복도").replace("4층", "${floor}층")
                    add(Segment(path.getJSONObject(pointIndex).toPoint(), path.getJSONObject(pointIndex + 1).toPoint(), label))
                }
            }
        }
    }

    private fun parseRooms(map: JSONObject): List<MapRoom> {
        val rooms = map.getJSONArray("rooms")
        return buildList {
            for (index in 0 until rooms.length()) {
                val room = rooms.getJSONObject(index)
                if (!room.has("x") || room.optBoolean("provisional", false)) continue
                add(
                    MapRoom(
                        id = room.getString("id"),
                        x = room.optDouble("front_x", room.getDouble("x")),
                        y = room.optDouble("front_y", 0.0),
                        width = room.optDouble("width", 4.5),
                        side = room.optString("side", "upper"),
                    ),
                )
            }
        }
    }

    private fun JSONObject.toPoint() = Point(getDouble("x"), getDouble("y"))

    private fun closestPoint(point: Point, segment: Segment): Point {
        val dx = segment.end.x - segment.start.x
        val dy = segment.end.y - segment.start.y
        val lengthSquared = dx * dx + dy * dy
        val ratio = if (lengthSquared == 0.0) 0.0 else ((point.x - segment.start.x) * dx + (point.y - segment.start.y) * dy) / lengthSquared
        val bounded = ratio.coerceIn(0.0, 1.0)
        return Point(segment.start.x + dx * bounded, segment.start.y + dy * bounded)
    }

    private fun distance(first: Point, second: Point) = hypot(first.x - second.x, first.y - second.y)

    private companion object {
        const val DEFAULT_START_X = 70.804
        const val MAX_STEPS_PER_UPDATE = 8
        const val ARRIVAL_RADIUS_MAP_UNITS = 2.5
        const val DIRECTION_AXIS_TOLERANCE_DEGREES = 45.0
    }
}
