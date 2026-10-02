"""Add the confirmed 4F right-end restroom passage to Android route laps."""
from pathlib import Path


PROJECT = Path(r"C:\Users\20222967\AndroidStudioProjects\IndoorPositioningPrototype")
MAIN = PROJECT / "app/src/main/java/com/example/indoorpositioning/MainActivity.kt"
TEST = PROJECT / "app/src/test/java/com/example/indoorpositioning/ExampleUnitTest.kt"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match in {path}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    MAIN,
    '''private fun routePreset(
    floor: Int,
    sideId: String,
    stairs: String,
    orderedRooms: List<RouteMapPoint>,
): RouteCollectionPreset {''',
    '''internal fun standardMainRoutePoints(
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
): RouteCollectionPreset {''',
)

replace_once(
    MAIN,
    '''        points = orderedRooms.map { it.id } + stairs,
''',
    '''        points = standardMainRoutePoints(floor, sideId, orderedRooms.map { it.id }, stairs),
''',
)

replace_once(
    TEST,
    '''    @Test
    fun unsupportedSpecialRouteDoesNotPretendToHaveLiveMapMatching() {''',
    '''    @Test
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
    fun unsupportedSpecialRouteDoesNotPretendToHaveLiveMapMatching() {''',
)

print(MAIN)
print(TEST)
