"""Keep Android 2F route helpers consistent with corrected room identifiers."""
from pathlib import Path


PROJECT = Path(r"C:\Users\20222967\AndroidStudioProjects\IndoorPositioningPrototype")
MAIN = PROJECT / "app/src/main/java/com/example/indoorpositioning/MainActivity.kt"
TEST = PROJECT / "app/src/test/java/com/example/indoorpositioning/ExampleUnitTest.kt"


def replace_exact(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"Expected exactly one match in {path}: {old!r}; found {count}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


replace_exact(
    MAIN,
    [
        ('val openSpaceEntryX = byId["2210"]?.x ?: return emptyList()',
         'val openSpaceEntryX = byId["2210-1"]?.x ?: return emptyList()'),
        ('.filterNot { it in setOf("2211", "2210", "2210-1") }',
         '.filterNot { it in setOf("2211", "2210-1", "2205") }'),
        ('"2210 문 1",\n        "2107 진입 가능점",\n        "2210 문 2 · 2107 끝점",\n        "2210-1 앞",',
         '"2210-1 문 1",\n        "2107 진입 가능점",\n        "2210-1 문 2 · 2107 끝점",\n        "2205 앞",'),
    ],
)

replace_exact(
    TEST,
    [
        ('NavigationDestination(2, "2210", "2210", 38.47),\n            NavigationDestination(2, "2210-1", "2210-1", 24.69),\n            NavigationDestination(2, "2205", "2205", 17.12),',
         'NavigationDestination(2, "2210-1", "2210-1", 38.47),\n            NavigationDestination(2, "2205", "서버실 2205", 20.84),'),
        ('assertEquals((24.69 + 17.12) / 2.0, approaches.getValue("STUDY").x, 1e-9)',
         'assertEquals((38.47 + 20.84) / 2.0, approaches.getValue("STUDY").x, 1e-9)'),
        ('listOf("2211 문 1", "2211 문 2", "2210 문 1", "2107 진입 가능점", "2210 문 2 · 2107 끝점", "2210-1 앞"),\n            floorTwoRightMainPoints(listOf("2211", "2210", "2210-1", "2205", "2204"), "오른쪽 계단 입구").take(6),',
         'listOf("2211 문 1", "2211 문 2", "2210-1 문 1", "2107 진입 가능점", "2210-1 문 2 · 2107 끝점", "2205 앞"),\n            floorTwoRightMainPoints(listOf("2211", "2210-1", "2205", "2204"), "오른쪽 계단 입구").take(6),'),
    ],
)

print(MAIN)
print(TEST)
