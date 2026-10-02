"""Rename 2F route laps after the 2210-1 and 2205 server-room correction."""
from pathlib import Path


PROJECT = Path(r"C:\Users\20222967\AndroidStudioProjects\IndoorPositioningPrototype")
MAIN = PROJECT / "app/src/main/java/com/example/indoorpositioning/MainActivity.kt"
TEST = PROJECT / "app/src/test/java/com/example/indoorpositioning/ExampleUnitTest.kt"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match in {path}; found {count}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


replace_once(MAIN, '        "2205 앞",\n', '        "2205 서버실 앞",\n')
replace_once(
    TEST,
    'listOf("2211 문 1", "2211 문 2", "2210-1 문 1", "2107 진입 가능점", "2210-1 문 2 · 2107 끝점", "2205 앞"),',
    'listOf("2211 문 1", "2211 문 2", "2210-1 문 1", "2107 진입 가능점", "2210-1 문 2 · 2107 끝점", "2205 서버실 앞"),',
)

print(MAIN)
print(TEST)
