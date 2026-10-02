# 실내측위 Android 앱

현재 Android Studio에서 개발한 앱의 저장소용 소스다. 버전은 `1.0.20261002.1` / versionCode `8`이다. 지도와 측위 JavaScript는 복제하지 않고 저장소의 `indoor/web`를 APK 자산으로 함께 사용한다.

## 열기와 빌드

1. 저장소를 복제하고 `git lfs pull`로 지도·측정 자료를 받는다.
2. Android Studio에서 이 폴더를 연다.
3. 프로젝트에서 요구하는 Android SDK 37과 Java 25를 준비한다. SDK 경로는 Android Studio에서 설정하거나 `ANDROID_HOME` 환경 변수로 지정한다.
4. 이 폴더에서 실행한다.

```powershell
.\gradlew.bat testDebugUnitTest lintDebug assembleDebug
```

APK 출력은 `app/build/outputs/apk/debug/app-debug.apk`이다. `local.properties`, 개인 서명키, IDE 설정, 빌드 캐시는 저장소에 포함하지 않는다. Windows에서는 한글이 없는 짧은 복제 경로(예: `C:\projects\indoor-nav-it4f`)를 권장한다.

## 구현 및 검증 범위

공용 1~10층 지도, PDR·지도 제약, 자기장 격자/V2·BLE 보정, 경로 라벨 및 센서 기준점 수집, AP 기준점 접근·회전·불확실성 검색 조건이 포함된다. 층별 자료 보유와 보정 적용 범위가 다르므로 전 층의 현장 정확도를 확인한 것으로 해석하지 않는다. 최신 설치·실험 상태는 [전체 진행상황](../../docs/CURRENT_STATUS.md)과 [합의 미완료 항목](../../docs/INDOOR_AGREEMENT_AUDIT_20261002.md)을 따른다.

## 소스 동기화

원본 Android Studio 프로젝트는 변경하지 않았다. 저장소 루트의 `tools/sync_android_source.py`가 소스 파일을 복사하며, `app/build.gradle.kts`의 자산 경로 한 곳을 저장소 기준으로 바꾼다. Gradle 설정 두 파일의 끝 빈 줄도 정리한다. 파일별 원본·복사본 SHA256과 변경 범위는 `SOURCE_MANIFEST.json`에 기록한다. 이후 원본에서 개발한 변경은 다음 명령으로 다시 동기화한다.

```powershell
python tools/sync_android_source.py --source C:\path\to\IndoorPositioningPrototype
```
