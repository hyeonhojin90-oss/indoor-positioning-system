# RoNIN Android 오프라인 추론

공식 ResNet18 모델을 우리 Android 원시 JSONL에 연결한 PC 실험이다. 앱의 PDR/파티클 기본 엔진이 아니며, 위치 라벨로 추론값을 보정하거나 종점에 맞춰 스케일을 학습하지 않는다.

## 실행

저장소 루트 PowerShell에서:

```powershell
& 'tools/passenger-counter/.venv/Scripts/python.exe' indoor/tools/ronin/run_android.py
& 'tools/passenger-counter/.venv/Scripts/python.exe' indoor/tools/ronin/test_bridge.py
```

기존 CPU PyTorch 환경(torch/numpy/scipy)을 재사용한다. `weinberg-combined-20260923/results.json`의11회 파일목록 및 실측 종점거리로 평가한다. 원본 데이터는 읽기만 한다. `--limit 1`은 연결 확인용이며 기본11회 결과 파일을 덮어쓰므로 별도 `--output`을 권장한다.

## 모델 출처

- 공식 구현: https://github.com/Sachini/ronin
- 모델 정의: https://raw.githubusercontent.com/Sachini/ronin/master/source/model_resnet1d.py
- 모델 정의 SHA256: `24a4859272d2ee469ecaef192dddcaa287d40392de21f6c55b5b9b71c76d8e57`
- 공식 데이터/모델 DOI: https://doi.org/10.20383/102.0543
- 다운로드: https://www.frdr-dfdr.ca/repo/files/8/published/publication_538/submitted_data/Pretrained_Models/ronin_resnet.zip
- 로컬 체크포인트: `indoor/data/models/ronin/ronin_resnet/checkpoint_gsn_latest.pt`
- 체크포인트 SHA256: `5ae5c9e508f2dc9609c25b59d0e3dfd770ecbcde6920cbc5be3c6d9fed8a6346`
- 코드 라이선스: vendor/LICENSE. 모델 이용조건: indoor/data/models/ronin/LICENSE.txt (비상업 연구/교육용). 모델을 APK에 포함하지 않는다.

필요 시 위공식 zip을 내려받아 모델 디렉터리에 압축해제한다. 모델 state_dict는 strict=True, torch.load는 weights_only=True로 읽는다. 랜덤 초기화 모델로 성능을 대신하지 않는다.

## 입력/출력과 한계

센서 시각을 맞춘 뒤 회전벡터(x,y,z,w)로 자이로 rad/s, 가속도 m/s²(중력포함)를 ENU 좌표로 변환한다. 200Hz 보간, 과거200개 샘플/1초 창을20Hz마다 추론한다. 출력은 수평속도2개이며 시작점 기준 ENU 궤적 NPZ와 평가 JSON을 남긴다.

원본 자이로/회전은약45Hz로, 보간해도200Hz 원본이 되는 것은 아니다. 선형보간/SLERP는 다음 센서 표본을 참조하는 오프라인 과정이다. 첫1초는 예측이 없어 소급 복원하지 않는다. 원논문의 Tango 시작축/기기별 보정값 없이 Android 좌표계를 사용하므로 도메인 차이가 남는다.

출발점→종점 변위의 크기와 실측 직선거리 차이를 평가한다. 이것은 2D 위치오차가 아니다. 실제 좌표/방향까지 평가하려면 독립 지도 방위 정합이 필요하며 이번에는 도착점으로 방향을 피팅하지 않는다. 전체 경로 길이 오차도 별도로 제공한다.
