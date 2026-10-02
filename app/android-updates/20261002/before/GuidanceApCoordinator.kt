package com.example.indoorpositioning

import kotlin.math.abs

internal data class GuidanceApAnchor(
    val id: String,
    val label: String,
    val x: Double,
    val radius: Double,
    val minX: Double = x - radius,
    val maxX: Double = x + radius,
)

internal data class GuidanceApSnapshot(
    val status: String = "안내 시작 후 기준점에 진입하면 AP를 한 번 요청합니다.",
    val currentAnchorId: String? = null,
    val currentAnchorLabel: String? = null,
    val requestCount: Int = 0,
    val freshResultCount: Int = 0,
    val staleResultCount: Int = 0,
)

/**
 * Issues one Wi-Fi request on an anchor-zone entry. The 30 second value is a
 * same-anchor duplicate guard, not a periodic scan interval.
 */
internal class GuidanceApCoordinator(
    private val duplicateCooldownMs: Long = 30_000L,
) {
    private val lastRequestByAnchor = mutableMapOf<String, Long>()
    private var activeAnchorId: String? = null
    private var snapshot = GuidanceApSnapshot()

    fun resetSession(): GuidanceApSnapshot {
        lastRequestByAnchor.clear()
        activeAnchorId = null
        snapshot = GuidanceApSnapshot()
        return snapshot
    }

    fun stop(): GuidanceApSnapshot {
        activeAnchorId = null
        snapshot = snapshot.copy(
            status = "자동 AP 기준점 확인 중지",
            currentAnchorId = null,
            currentAnchorLabel = null,
        )
        return snapshot
    }

    fun update(map: MapMatchingSnapshot, nowElapsedMs: Long): GuidanceApAnchor? {
        if (!map.tracking || !map.available) {
            activeAnchorId = null
            return null
        }
        val rightStairInterior = if (map.matchedX <= 2.5 && map.rawX <= -2.5) {
            GuidanceApAnchor("F${map.floor}_RIGHT_STAIRS_INSIDE", "오른쪽 계단 내부", -2.5, 2.5)
        } else null
        val anchor = rightStairInterior ?: anchorsFor(map)
            .filter { map.matchedX in it.minX..it.maxX }
            .minByOrNull { abs(map.matchedX - it.x) }
        if (anchor == null) {
            activeAnchorId = null
            snapshot = snapshot.copy(
                status = "${map.floor}층 · ${map.corridorLabel} · ${map.nearestRoomLabel} 부근 (PDR 지도 추정) · AP 기준점 밖, AP 위치 판정 보류",
                currentAnchorId = null,
                currentAnchorLabel = null,
            )
            return null
        }
        if (activeAnchorId == anchor.id) return null
        activeAnchorId = anchor.id
        val lastRequest = lastRequestByAnchor[anchor.id]
        if (lastRequest != null && nowElapsedMs - lastRequest < duplicateCooldownMs) {
            val remainingSeconds = ((duplicateCooldownMs - (nowElapsedMs - lastRequest) + 999L) / 1_000L)
            snapshot = snapshot.copy(
                status = "${anchor.label} 재진입 · 같은 기준점 재요청까지 ${remainingSeconds}초",
                currentAnchorId = anchor.id,
                currentAnchorLabel = anchor.label,
            )
            return null
        }
        lastRequestByAnchor[anchor.id] = nowElapsedMs
        snapshot = snapshot.copy(
            status = "${anchor.label} 진입 확인 · AP 1회 요청",
            currentAnchorId = anchor.id,
            currentAnchorLabel = anchor.label,
            requestCount = snapshot.requestCount + 1,
        )
        return anchor
    }

    fun onResult(anchor: GuidanceApAnchor, fresh: Boolean, apCount: Int): GuidanceApSnapshot {
        snapshot = snapshot.copy(
            status = if (fresh) {
                "${anchor.label} · 새 AP ${apCount}개를 모드 4 지문 비교에 전달"
            } else {
                "${anchor.label} · 새 AP 결과 아님 (위치 보정에 사용하지 않음)"
            },
            currentAnchorId = anchor.id,
            currentAnchorLabel = anchor.label,
            freshResultCount = snapshot.freshResultCount + if (fresh) 1 else 0,
            staleResultCount = snapshot.staleResultCount + if (fresh) 0 else 1,
        )
        return snapshot
    }

    fun onRequestUnavailable(anchor: GuidanceApAnchor): GuidanceApSnapshot {
        snapshot = snapshot.copy(
            status = "${anchor.label} · AP 요청 대기 중이어서 이번 진입은 건너뜀",
            currentAnchorId = anchor.id,
            currentAnchorLabel = anchor.label,
        )
        return snapshot
    }

    fun snapshot(): GuidanceApSnapshot = snapshot

    private fun anchorsFor(map: MapMatchingSnapshot): List<GuidanceApAnchor> = buildList {
        add(GuidanceApAnchor("F${map.floor}_CORE", "코어 기준점", map.startX, 2.5))
        add(GuidanceApAnchor("F${map.floor}_LEFT_STAIRS", "왼쪽 계단 앞", map.mainLength, 2.5))
        add(GuidanceApAnchor("F${map.floor}_RIGHT_STAIRS", "오른쪽 계단 앞", 0.0, 2.5))
        if (map.floor == 2) {
            map.rooms.firstOrNull { it.id == "2204" }?.let { room ->
                add(GuidanceApAnchor("F2_EXTENSION_ENTRY", "2204 근처 · 증축복도 진입점", room.x, 2.5))
            }
        }
        if (map.floor == 3) {
            map.rooms.firstOrNull { it.id == "3203" }?.let { room ->
                // Shared 3F/4F right-end restroom passage boundary from
                // areas-v1 side_passage.maxX. The trigger covers the corridor
                // interval before the passage, not an arbitrary radius.
                val passageBoundaryX = 5.6035
                add(
                    GuidanceApAnchor(
                        id = "F3_EXTENSION_ENTRY",
                        label = "3203~화장실 통로 사이 · 증축복도 진입 가능 구간",
                        x = (room.x + passageBoundaryX) / 2.0,
                        radius = (room.x - passageBoundaryX) / 2.0,
                        minX = passageBoundaryX,
                        maxX = room.x,
                    ),
                )
            }
        }
    }
}
