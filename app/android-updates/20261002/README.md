# AP 이벤트 업데이트 — 2026-10-02

최신 APK: `exports/android/indoor-20261002-event-ap.apk`, versionCode8/1.0.20261002.1.
운영 기본 좌표와 고정보폭을 유지하고 공용 지도 제약 및 AP회전/불확실성 요청을 포함했다. 보고서 HWPX와 원시 센서 자료는 수정하지 않았다.

전체 상태는 `docs/CURRENT_STATUS.md`, 합의 누락/보류 구분과 AP수치는 `docs/INDOOR_AGREEMENT_AUDIT_20261002.md`를 따른다.

## 변경 소스와 검증

`source/`에는 실제 Android프로젝트에 반영된 Kotlin6개와 추가 단위 시험1개의 사본, `build.gradle.kts`에는 빌드 설정 사본이 있다. 실제 개발 경로는 `C:\Users\20222967\AndroidStudioProjects\IndoorPositioningPrototype`이다. 공용 웹 자산은 `indoor/web`에서 APK로 읽으므로 별도 수동 복제를 하지 않는다.

`verification.json`은 Kotlin/설정 실제 반영, Android단위37개, Lint오류0/경고20, APK ZIP CRC/핵심 자산34개와 소스 SHA, 브라우저 검사와 변경 전 보존 파일 SHA를 기록한다. APK v2서명과 versionCode도 SDK도구로 확인했다. 현재 adb기기는 없으며 설치·실제 회전 스캔/위치 정확도를 검증한 것은 아니다.

주요 검사 명령(저장소에서):

```powershell
$env:NODE_PATH = 'C:\Users\20222967\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
node indoor\tools\test_event_ap_browser_20261002.cjs
node indoor\tools\test_wifi_anchor_fusion.cjs
```

브라우저 검사는 `indoor/web`을 `127.0.0.1:4175`로 제공한 상태에서 실행한다. 실제 센서 대신 테스트 브리지를 쓰며 기준점 지문, 중복·이동 품질·거리/복도 거절·AP On/Off를 확인한다.

## 설치 및 복구

갤럭시 USB디버깅을 연결한 후:

```powershell
& 'C:\Users\20222967\AppData\Local\Android\Sdk\platform-tools\adb.exe' install -r 'C:\Users\20222967\Documents\ChatGPT\자율설계 2\exports\android\indoor-20261002-event-ap.apk'
```

`before/`는 수정 전 Android소스/빌드 설정과 AP후보 조건의 공용 엔진 사본이다. 복구할 때는 대상 파일과 현재 변경을 비교한 뒤 필요한 파일만 복원하고 다시 빌드한다. 다른 대화의 변경이나 최신 지도 제약을 함께 되돌리지 않는다. 이전 APK도 삭제하지 않았다. 자유 시험에서 AP사용 체크를 끄면 AP제외 조건으로 비교할 수 있다.
