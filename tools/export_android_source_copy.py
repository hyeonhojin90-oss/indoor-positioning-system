"""Create a self-contained Android Studio source copy with local web assets."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ANDROID = Path(r"C:\Users\20222967\AndroidStudioProjects\IndoorPositioningPrototype")
WEB = ROOT / "indoor/web"
EXPORTS = ROOT / "exports/source"
BASE_NAME = "IndoorPositioningPrototype-source-20260922"


def ignored(_path, names):
    blocked = {".gradle", ".idea", ".kotlin", "build"}
    return [name for name in names if name in blocked]


EXPORTS.mkdir(parents=True, exist_ok=True)
name = BASE_NAME
index = 2
while (EXPORTS / name).exists() or (EXPORTS / f"{name}.zip").exists():
    name = f"{BASE_NAME}-{index}"
    index += 1

dest = EXPORTS / name
shutil.copytree(ANDROID, dest, ignore=ignored)

for private_file in ["local.properties"]:
    target = dest / private_file
    if target.exists():
        target.unlink()

assets = dest / "app/src/main/assets"
shutil.copytree(WEB, assets)

gradle = dest / "app/build.gradle.kts"
text = gradle.read_text(encoding="utf-8")
old = '''      sourceSets {
          getByName("main") {
              // Reuse the verified web map and its authoritative data/maps/floor-XX.json files.
              // Do not also mount data/maps as an asset root: that creates duplicate stale
              // floor-XX.json files alongside the current data/maps copies.
              assets.srcDir(file("../../../Documents/ChatGPT/자율설계 2/indoor/web"))
          }
      }
'''
new = '''    sourceSets {
        getByName("main") {
            // Self-contained copy: the verified web map is bundled below src/main/assets.
            assets.setSrcDirs(listOf("src/main/assets"))
        }
    }
'''
if old not in text:
    raise RuntimeError("Expected external asset sourceSet was not found")
gradle.write_text(text.replace(old, new), encoding="utf-8")

gradle_properties = dest / "gradle.properties"
properties_text = gradle_properties.read_text(encoding="utf-8")
if "android.overridePathCheck=" not in properties_text:
    gradle_properties.write_text(
        properties_text.rstrip() + "\nandroid.overridePathCheck=true\n",
        encoding="utf-8",
    )

readme = f'''# 실내측위 Android 앱 소스 복제본

생성일: 2026-09-22

이 폴더는 `IndoorPositioningPrototype` Android Studio 프로젝트와 현재 검증된
`indoor/web` 지도·측위 엔진을 `app/src/main/assets` 아래에 함께 넣은 독립 복제본입니다.

## 열기와 빌드

1. ZIP을 `C:\\AndroidProjects`처럼 한글이 없는 짧은 경로에 풉니다.
2. Android Studio에서 압축을 푼 프로젝트 폴더를 엽니다.
3. Android SDK 경로 안내가 나오면 로컬 SDK를 선택합니다.
4. Gradle 동기화 후 `app`을 실행하거나 Windows 터미널에서 다음을 실행합니다.

```powershell
.\\gradlew.bat testDebugUnitTest assembleDebug
```

원본 PC의 `local.properties`, `.gradle`, `.idea`, `.kotlin`, `build` 폴더는 포함하지
않았습니다. 앱 패키지는 `com.example.indoorpositioning`으로 원본과 같으므로 같은
휴대폰에 설치하면 기존 앱을 업데이트합니다. 별도 앱으로 동시에 설치하려면
`applicationId`를 변경해야 합니다.

Windows의 Android Gradle/Kotlin 도구는 한글이 포함된 프로젝트 경로에서 단위 테스트
클래스를 찾지 못할 수 있습니다. 소스 문제가 아니므로 위와 같이 영문 경로에 풀어
사용하는 것을 권장합니다.

포함된 거리 기준은 1층 제외 2~10층 공통 실거리와 2·3층 증축부 survey입니다.
'''
(dest / "README_KO.md").write_text(readme, encoding="utf-8")

manifest = {
    "created": "2026-09-22",
    "source_android_project": str(ANDROID),
    "bundled_web_source": str(WEB),
    "package_id": "com.example.indoorpositioning",
    "excluded": ["local.properties", ".gradle", ".idea", ".kotlin", "build"],
    "self_contained_assets": "app/src/main/assets",
}
(dest / "SOURCE_COPY_MANIFEST.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

zip_path = EXPORTS / f"{name}.zip"
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for path in sorted(dest.rglob("*")):
        if path.is_file():
            zf.write(path, Path(name) / path.relative_to(dest))

digest = hashlib.sha256(zip_path.read_bytes()).hexdigest().upper()
print(json.dumps({
    "folder": str(dest),
    "zip": str(zip_path),
    "bytes": zip_path.stat().st_size,
    "sha256": digest,
}, ensure_ascii=False, indent=2))
