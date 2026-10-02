## 2026-10-02 Danfo 개발 자료 전환

`called.webm`은 처음 두 고정 설정 비교 때 학습하지 않은 자료였다. 실패를 확인한 뒤 called 파생 영상의0/50/100/150 네 프레임을 train에 추가했다. 이후 이 촬영에 대한 학습/평가는 개발 실험이며 독립 블라인드 결과가 아니다. 같은 저자의 boarding 영상도 촬영 독립성이 확인되지 않아 독립 holdout을 주장하지 않는다. 원본 저작자·CC BY-SA4.0·90도 회전/음성 생략/JPEG 추출/assistant 주석 변경 내역은 `bus-portal-danfo-development-resume4-r2/provenance.json`에 보존했다. 새 주석은 동일 CC BY-SA4.0, 사람이 독립 검수한 완전 정답이 아니다.

## 2026-10-02 새 원저자 공개 버스 영상 및 문 자료 접근

Commons Danfo의 원저자Oreoluwa Adetimehin(Orekoko) own work, CC BY-SA4.0. source원본URL/저작자/라이선스URL/SHA1·SHA256/크기/실제decode759·1232프레임은 `data/commons-danfo-resume4/*.source.json` 보존. called: https://commons.wikimedia.org/wiki/File:A_passenger_currently_boarding_a_danfo_bus_after_being_called_by_the_conductor_VP8.webm , boarding: https://commons.wikimedia.org/wiki/File:A_passenger_boarding_a_danfo-bus_VP8.webm . 원본320x240/25fps를그대로보존하고명시적clockwise90·mp4v·음성제외파생은변경내용/원본계보와같은라이선스기록. 학습미사용. source독립성과완전블라인드정답정확도는구별함.

https://universe.roboflow.com/bus-door/bus-open-door 실제공개버전확인: 원본542, v1증강1626전부train/val0/test0, CC BY4.0, Front_door/Rear_door, Models0. 실제Download/yolov8 화면은 Login or create a free account 요구, 계정생성/로그인/자료다운로드 미실시. `reviews/bus-open-door-access-resume4.json` 및브라우저스크린샷 보존. 1626을독립원본/평가자료로취급하지않는다. 이전1884장 dataset0 프로젝트와다른 자료다.

## 2026-10-02 공식 OSNet 외형 특징 연구 후보

- 저자 소스: https://github.com/KaiyangZhou/deep-person-reid , pinned `f8cd150fdf77e8d9e1ed143b7f308c2c609ded50`의 osnet.py 및 MIT LICENSE.
- 저자 모델: https://huggingface.co/kaiyangzhou/osnet , pinned `a5c5cc037c24235cda3b21085b93ad77c9616224`, OSNet x025 MSMT17 combineall256x128 사전학습 가중치9336983bytes.
- 원본 파일과 MIT/modelcard·SHA/URL/크기는 `models/osnet-x025-author-resume4/source.json` 및 LICENSE/README.md 보존. author reference https://kaiyangzhou.github.io/deep-person-reid/MODEL_ZOO . 실제 source import 전 확인, strict weights_only 로드 및 파일SHA 검증.
- 현재 관측 crop 특징 추출 및 오프라인 연결 후보만 시험. Jetson/TensorRT·실시간 전체 추적·독립 정확도 미검증. 저자 feature model의 품질이 우리 카메라/집계 품질을 보장하지 않는다.

## 2026-10-01 최신 검증: 전체 ONNX 일치·큰 모델 한계·마스크 제거 실험

공식 출처: https://github.com/shijieS/people-counting-dataset (PCDS CC BY-NC-SA3.0, RGB/depth 비동기 가능, 공개 tree 조사 `reviews/pcds-public-file-inventory-r2.json`). BerlinAPC https://depositonce.tu-berlin.de/items/485b22be-83ef-4361-94d8-f91d319c5643 는 저해상도 depth 자료이며 미획득. PAMELA https://videodatasets.org/PAMELA-UANDES/whole_data.html 접근 신청 필요/연락 안 함. https://github.com/sanjarbek1030/BusOccupancyCounter 데모의 원본 영상 권리는 확인되지 않았고 Shutterstock 워터마크로 격리(`data/public-github-bus-demo-20261001-r2.source.json`), 훈련/평가/추론 미사용.

파생 box 모델은 기존 Ultralytics YOLO11s-seg의 backbone/box/class 가중치를 그대로 유지한 local architecture derivative이며 새로운 데이터로 재학습하지 않았다. 원본 모델 라이선스가 그대로 관련된다. 출처/삭제 tensor/양성 박스 계보 `models/yolo11s-seg-trained-box-detector-r2.source.json`; 원본 불변 SHA와 ONNX 계보 검증 없이는 task 차이를 비교에서 무시하지 않는다.

## 2026-10-01 새로운 공개 문 사진과 사전학습 비교

모델 예측 전에 assistant가 문 좌표를 고정한 정지 사진 진단이다. 승차 이벤트/인원 정확도를 검증하지 않는다. 원본1280px 공개 파생사진과 hash는 `data/commons-door-photos-20261001-r2/provenance.json`에 있으며 박스 표시·진단 이미지는 변형본이다. 이후 Boston/Nigeria는 보강훈련 train, Vancouver val, Kenya test에 사용했다. 다른 가려진 사진은 학습하지 않았다. 사진 split은 recording별이며 blind 검증이 아니다.

- [beijing-z184-20230417.jpg](https://commons.wikimedia.org/wiki/File:A_woman_boarding_Route_%E4%B8%93184_at_Hongda_Nanlu_Beikou_(20230417105732).jpg): N509FZ, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- [boston-mbta57-20230630.jpg](https://commons.wikimedia.org/wiki/File:Passenger_boarding_MBTA_57_bus_June_2023.jpg): 4300streetcar, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- [vancouver-boarding-20111126.jpg](https://commons.wikimedia.org/wiki/File:Boarding_the_bus..jpg): Ineslacarne, [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
- [waltham-mbta70-20260119.jpg](https://commons.wikimedia.org/wiki/File:Passengers_boarding_MBTA_route_70_bus_at_Waltham_January_2026.jpg): 4300streetcar, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- [apsrtc-boarding-20120712.jpg](https://commons.wikimedia.org/wiki/File:Passengers_boarding_on_Bus_(YS).jpg): YVSREDDY, [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).
- [nigeria-boarding-20200215.jpg](https://commons.wikimedia.org/wiki/File:Passengers_boarding_a_bus_by_Dikie_Chukwuma.jpg): Dike Chukwuma, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- [kenya-matatu-20200320.jpg](https://commons.wikimedia.org/wiki/File:Passengers_boarding_a_Matatu_at_a_bus_stop_in_Kenya.jpg): Loise W. Macharia, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

[공식 YOLOE](https://docs.ultralytics.com/models/yoloe/)의 v8.3.0 사전학습 yoloe-11s-seg.pt와 mobileclip_blt.ts, [공식 YOLO11](https://docs.ultralytics.com/models/yolo11/)의 yolo11s-seg.pt를 비교한다. 정확한 release URL·SHA는 models/*.source.json 및 mobileclip_blt.download.json에 있다. Orin 성능 미검증.

[Roboflow 버스 문1884사진](https://universe.roboflow.com/bus-door/bus-door-detection-2)은 공개raw라벨을 확인했으나 Dataset0/Model0 및 이미지 다운로드 로그인 요구로 로컬 확보하지 않았다. 공개 열람과 학습 데이터 확보를 구별한다.

## 후속 확보 자료

- [Shariar Tawsif / Pexels: Busy City Bus Stop with Passengers Boarding](https://www.pexels.com/video/busy-city-bus-stop-with-passengers-boarding-31337217/): `data/bus-pink-31337217.mp4`, 3840×2160, 30fps, 178프레임, SHA256 `2155814b2d7cd1620b7c924b1098d926f485907ea1a193238a60b8d536fc708d`. 제목과 달리 원본 검토에서 여러 사람이 하차하는 장면이다. 움직이는 문·앞사람 가림이 있어 방향 검증에 사용했다. 1280×720 파생 SHA256 `374d41fc14036a275ec9972dc8b51ee1399adcc25d4e4c007be5b5910b16f96e`. 페이지 Free to use 표시, Pexels 이용 조건 적용. 영상은 로컬 평가용이며 저장소에 재배포하지 않는다.

- [Grigoriy Bunkov / Pexels: City Bus Stop with People Boarding in Urban Area](https://www.pexels.com/video/city-bus-stop-with-people-boarding-in-urban-area-36462986/): `data/bus-city-36462986.mp4`, 1920×1080, 25fps, 761프레임, SHA256 `30448b9c906e4bde3296eb940fc9bc30a0529236f7b725faa86cefb54b733234`. 정류장으로 버스가 와서 가운데 출입구의 승·하차 후 출발하는 별도 장면이다. 1280×720 파생 SHA256 `40ab287acf679eb3a6da238724df791a6ee51ac0de128275b46d719916be1e6f`. 원본 표본 확인 전에 개발 후보 설정 해시를 고정했다(`reviews/city-36462986-heldout-manifest.json`). 페이지 Free 표시, Pexels 이용 조건 적용. 로컬 평가용이며 영상 재배포 없음.

- [OSCAR YOHANA / Pexels: City Bus Arrival and Passenger Boarding Scene](https://www.pexels.com/video/city-bus-arrival-and-passenger-boarding-scene-36445878/): 원본 `data/bus-arrival-36445878.mp4`, 3840×2160, 25fps, 528프레임, SHA256 `8d25f78567246c329d41301ea105f1216d03bcf39ae0664ccecf76217f3eaaee`. 고정 카메라에 버스와 보행자가 보이는 새 장면. 현장 목표의 뒤통수·문 전체 시점과는 다르고 정류장 가림막이 출입구를 일부 가린다. 1280×720 재인코딩 파일은 로컬 추론 시험용 파생본이며 별도 독립 장면이 아니다. 페이지에 Free 표시, Pexels 이용 조건 적용. 원본과 파생본을 저장소에 재배포하지 않는다.

- [Richard L / Pexels: People Boarding Green Double-decker Bus at Station](https://www.pexels.com/video/people-boarding-green-double-decker-bus-at-station-32245403/): 원본 `data/bus-green-32245403.mp4`, 2160×3840, 30fps, 513프레임, SHA256 `a6affff085ef74dd31df8f5d5f7ef90113b543197e5f73826d3445d684df5738`. 고정 외부 카메라에 열린 문과 여러 승객의 뒤쪽이 비교적 크게 보인다. 720×1280 재인코딩은 추론용 파생본이다. 페이지에 Free 표시, Pexels 이용 조건 적용. 원본·파생본을 저장소에 재배포하지 않는다.

- [Wikimedia Commons: A man boarding a moving bus.webm](https://commons.wikimedia.org/wiki/File:A_man_boarding_a_moving_bus.webm): Yathra Visheshangal 원작, CC BY 4.0. 로컬 독립 장면 `data/wiki-man-boarding.webm`(1280×720, 30fps, 182프레임), SHA256 `88e0f1be67eb7080e1ff0b8b42ede76d0a53dd12a5a311980a40548dcabe8f0d`. 카메라와 버스가 멀고 버스가 움직이며 한 사람이 승차한다. 사용 시 저작자·출처·라이선스를 표시하고 변형 여부를 적는다. 이번 시험의 프레임 추출·검출 표시 이미지는 변형본이다.

- [Sayed Mohamed 공개 문 YOLOv8](https://github.com/sayedmohamedscu/YOLOv8-Door-detection-for-visually-impaired-people): `doors.pt` 다운로드, 클래스 0=door 확인. 로컬 `models/doors-v8s.pt`, SHA256 `9c067270a2b98a8f35468a5f0b86acb1a6d2c4577992cfcb287a336c804d8aee`. 버스 영상에서 낮은 신뢰도로 문을 일부 찾았으나 전체 승차 집계에는 실패. 가중치 자체의 별도 이용허락 표기는 확인하지 못해 비교 실험 후보로 보존.
- [Doors detection YOLO 데이터](https://www.kaggle.com/datasets/sayedmohamed1/doors-detection): 공개 API 다운로드 성공. API 메타데이터에 CC BY 4.0 표시. 원본 65,913,001 bytes, SHA256 `2599542c50874e1e8dd23af327f30cac7555a4e1694dce5c2ca3c08c46ed7260`. 477개 이미지와 YOLO 문 라벨. 기존 train/val은 사용하지 않고 파일명 촬영 날짜로 재분할: train 337 / val 37 / test 30 / 날짜 불명 73 제외. 주로 건물·상점 문이며 버스 문 데이터가 아니다. 좌표 형식 검사와 16장 표본 검토만 했고 전체 라벨 수동 교정은 하지 않았다. 같은 건물의 다른 날짜 사진이 존재할 가능성은 남는다.
- [perseusdg 문/통로 모델](https://huggingface.co/perseusdg/doorway-door-people-window-seg): AGPL-3.0 표시, ONNX 다운로드. SHA256 `b960c75c9d5365c0fd6c6dc09e92da75342805e5a270b3724aadf6fbcc36772a`. 첫 버스 프레임에서 confidence >=0.1인 문 검출 없음. ONNX 출력/메타데이터 확인만 수행했으며 운영 파이프라인에 채택하지 않았다.
- [Laura James / Pexels 버스 영상](https://www.pexels.com/video/a-woman-wearing-face-mask-entering-a-bus-6097011/): `data/bus-6097011.mp4`, 1440×2560, 312프레임, 23.976fps. SHA256 `692f302b0f08f4d131bd7b0461c7b692524087cddfd14f4262fc15d21b65db86`. 접근하는 버스와 대기자를 촬영한다. 승차 입구가 화면 가장자리라 전신 통과·문 전체 평가에 제약. 공개 문 YOLOv8은 안정 영역 0프레임.

## 영상

1. [CityXcape / Pexels: Public Bus Loading A Passenger](https://www.pexels.com/video/public-bus-loading-a-passenger-3132290/)
   - 실제 다운로드: `data/bus-3132290.mp4`, 1920×1080, 29.97fps, 109프레임(약 3.64초).
   - 버스 밖에서 승객 등을 보는 시점. 이미 승차 중인 첫 프레임, 짧은 클립, 카메라 움직임이 있어 정차 감지나 안정적 계수 평가에는 부족하다. 문 검출 실패 분석에 사용했다.
   - SHA-256: `8fd0d9a41b9e4e0e0baec2215f6838467920e1becaae2860f1a8871ae4a69c06`.
   - 게시 페이지 Free 표시. Pexels 이용 조건 적용. 원본/파생 영상을 저장소에 재배포하지 않는다.
2. [Roboflow Supervision 공식 예제 자산](https://supervision.roboflow.com/assets/)
   - [people-walking.mp4 다운로드](https://media.roboflow.com/supervision/video-examples/people-walking.mp4).
   - `data/people-walking.mp4` 보존, 앞 240프레임으로 사람 검출·추적·수동 영역 집계 확인. 버스/문 시험 아님.
   - SHA-256: `822671fb20ed13ef9ead91d1f3678863b5aa078dd3b2ed45953fda39a61c979d`.
   - 공식 예제 제공 사실 확인. 영상 자체의 별도 재배포 권리는 확인하지 않아 로컬 평가만 수행.
3. [PCDS — 원저자 데이터셋](https://github.com/shijieS/people-counting-dataset)
   - 버스 출입구 위 Kinect에서 RGB/depth를 수집, 영상별 승·하차 인원 라벨 제공. 우리 외부 후면 카메라와 시점 차이 있음.
   - [저자 제공 데모](https://www.youtube.com/watch?v=CcpRFchOqu4).
   - 공식 원본은 Baidu 링크, Google Drive는 용량 문제로 제거됐다고 명시. 이번 작업에서는 원본 미다운로드.
   - CC BY-NC-SA 3.0, 저자 논문 인용 요구. RGB/depth 동기화 보장 없음. 문 박스 학습용 정답과 인원 정답은 별개.

## 문 데이터 후보

- [UEG bus](https://universe.roboflow.com/ueg-uvpmz/bus-tizmw-xu8j8): 게시 자료상 850장, 사람·버스·운전석문·앞문·뒷문. CC BY 4.0 표시. 모델 인터페이스는 있으나 가중치 다운로드/우리 영상 정확도는 미확인.
- [bus door detection 2](https://universe.roboflow.com/bus-door/bus-door-detection-2): 1,884장, 앞문/뒷문 등. Public Domain 표시, dataset versions 0 / models 0. 공개 이미지 목록을 완성된 다운로드 가능 학습세트로 취급하지 않는다.
- 라벨 검수·원본 다운로드·학습 분할을 아직 수행하지 않았다. 자동으로 API 계정을 생성하거나 자료를 업로드하지 않았다.

## 구현 근거

- 2026-10-01 자세 보조 비교: [공식 YOLO11 모델 문서](https://docs.ultralytics.com/models/yolo11/)와 [공식 pose 가중치](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s-pose.pt). 로컬 SHA256 `1060bda4a27012060eca246f9b2adeea22eabb045a1e58f8d229be29b7ebc2ba`. 최초 즉시 집계 방식은 실패했으나, 실제 관측 발목을 보류하고 같은 ID의 몸통 통과를 우선하는 후속 방식에서 초록 개발 영상의 갈색을 포함한 고정 부분6/6을 확인했다. 다른 모델의 추적 ID는 같다고 가정하지 않으며 독립 정확도·Orin 성공으로 취급하지 않는다.
- 같은 [공식 배포 릴리스](https://github.com/ultralytics/assets/releases/tag/v8.3.0)의 YOLO11n-pose(6,255,593바이트, SHA256 `869e83fcdffdc7371fa4e34cd8e51c838cc729571d1635e5141e3075e9319dc0`)와 YOLO11m-pose(42,459,307바이트, SHA256 `29b17eaf3a3117cbea906090dbedf9159f7c6a49db58ec8b99ed2dfde1cf6eb2`)를 전체 초록 개발 촬영에서 비교했다. 실제 IN은 nano5·small6·medium6이었다. 크기 증가를 일반 정확도 향상이라고 단정하지 않는다. small의 자체 동적 ONNX FP32 출력은 전체513프레임에서 대응 검사를 통과했으며 TensorRT 변환은 미검증이다.
- CrowdHuman [원 학습 프로젝트](https://github.com/SibiAkkash/yolov5-crowdhuman), [ONNX 배포 프로젝트](https://github.com/yakhyo/yolov5-crowdhuman-onnx), [배포 가중치](https://github.com/yakhyo/yolov5-crowdhuman-onnx/releases/download/v0.0.1/crowdhuman.onnx). 원본 SHA256 `4f2b3a96231891de06df6838b4437fe68e9ae2df1ad1e1714cf700be9ea1561e`, 자체 출력 형식 변환 SHA256 `9296616e33a75ae1cb500799044e6533f960d6bb1eddc62fefceb6311010b931`. 클래스 person0/head1을 원본 metadata와 학습 YAML로 확인했고 양성 프레임3장의 출력 수치 일치를 확인했다. 타인의 추론 코드를 복사·실행하지 않았다. 가중치 배포/프로젝트 라이선스 확인은 실제 제품 채택 전에 남아 있으며 Orin 성능은 검증하지 않았다.
- CrowdHuman 몸통 후보는 도시 개발 영상의 검토 대상3명과 시각을 맞췄다. 초록 영상에서는 더 나빠졌으며 머리 검출을 별도 사람으로 더하지 않는다. 같은 촬영의 개발 결과를 논문/데이터셋 성능이나 독립 정확도라고 쓰지 않는다.

- [Grounding DINO tiny 공식 모델](https://huggingface.co/IDEA-Research/grounding-dino-tiny): Apache-2.0, 텍스트 기반 zero-shot 검출. Transformers 4.57.1, snapshot `a2bb814dd30d776dcf7e30523b00659f4f141c71`을 내려받아 CPU 문 검출 참조로 실행했다. 모델 카드 성능을 우리 버스 성능으로 인용하지 않는다.
- [Ultralytics 공식 가중치 배포](https://github.com/ultralytics/assets/releases/tag/v8.3.0): `yolo11m.pt`, `yolov8l-worldv2.pt`를 추가해 기존 n/s 모델과 동일 프레임을 비교했다.
  - 2026-09-30 `yolo11s.pt` 공식 COCO 모델 추가 다운로드: SHA256 `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5`; 요청·출처·바이트 수는 `runs/yolo11s-download-20260930.json`. 사람 학습을 처음부터 새로 한 결과가 아니다.

- [Ultralytics YOLO-World](https://docs.ultralytics.com/models/yolo-world/): 텍스트 지정 검출 탐색. 자체 문 학습의 대체 성능 보장 없음.
- [Ultralytics Tracking](https://docs.ultralytics.com/modes/track/): YOLO와 ByteTrack 연동. Ultralytics 코드/모델 이용 조건을 따른다.
- [Ultralytics Object Counting](https://docs.ultralytics.com/guides/object-counting/): 누적 통과 집계 참고. 본 코드는 이동하는 문과 회귀·영역 이탈 처리를 위해 별도 두 구역 상태를 사용한다.
- [Ultralytics Jetson 안내](https://docs.ultralytics.com/guides/nvidia-jetson/), [TensorRT 배포](https://academy.ultralytics.com/courses/train-your-first-yolo/export-for-deployment): Jetson 배포 후보와 대상 장치 engine 생성 원칙. 페이지 벤치마크를 우리 Orin Nano 성능으로 인용하지 않는다.

## 추가 자료 접근 확인 2026-10-01

- [PAMELA-UANDES 원저자 데이터 안내](https://videodatasets.org/PAMELA-UANDES/whole_data.html): 차량 모형의 승차·하차, 위쪽 단일 시점과 동시4시점 실험 자료. 연구 목적으로 교수에게 연락하여 개인 username/password를 받아야 한다고 명시한다. 인증 자료는 미다운로드이며 연락·메일 발송도 수행하지 않았다. 외부 버스 문 위치 검출 정답이 제공된다고 추정하지 않는다.
- [UPC/TMB/CARNET Smart Bus Stops 논문](https://imatge.upc.edu/web/sites/default/files/pub/cMartinez25.pdf): 정류장 사람 수·개별 대기 시간·버스 도착을 함께 모니터링하는 연구. 깊이 카메라 방식이므로 현재 RGB 프로젝트의 사전학습 모델/데이터를 그대로 제공하는 자료로 취급하지 않는다. 장기 대기 규모 목표의 참고이며 승차 우선순위나 하드웨어 결정을 바꾸지 않았다.
- [Pexels 추가 정류장 영상 원페이지](https://www.pexels.com/video/people-waiting-at-bus-stop-in-urban-setting-36467681/): 페이지 설명은 확인했지만 로컬 다운로드 시 HTTP403으로 종료됐다. 원영상 확보/추론/독립 검증을 완료했다고 기록하지 않는다. 인증·접근 제한을 우회하지 않았다.

## 2026-10-01 추가 영상 후보 접근 조건 확인

[Mixkit Lined up to board a bus](https://mixkit.co/free-stock-video/lined-up-to-board-a-bus-24971/)는 Restricted License 개인 용도 표시이며 [Mixkit 약관](https://mixkit.co/terms/)이 Envato AUP를 적용한다. [Envato AUP](https://help.elements.envato.com/hc/en-us/articles/31035788503321-Acceptable-Use-Policy) 4(m)은 허가 없는 AI/ML 개발 사용을 제한하므로 이번 알고리즘 자료에서 제외했다. 다운로드하지 않았다.

Pexels36445878은 기존 `data/bus-arrival-36445878.mp4`로 이미 확보한 촬영이다. 2026-10-01 다른 경로로 페이지 접근을 다시 시도했으나 HTTP403으로 새 파일은 받지 못했다. 새 독립 영상 확보로 보고하지 않는다. PAMELA는 연구 접근 허가가 필요하여 접근 우회/계정 요청을 하지 않았다. 기존 수집 자료와 합성 스트레스 검증을 계속한다.
## 2026-10-01 추가 실제 승차 촬영과 사진

새 별도 촬영 [A man boarding a moving bus.webm](https://commons.wikimedia.org/wiki/File:A_man_boarding_a_moving_bus.webm)은 Yathra Visheshangal, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)이다. 원본182프레임30fps와 Commons SHA1을 대조했고 `data/commons-moving-bus-boarding-resume3.source.json`에 출처/해시를 보존했다. 이 영상은 문 학습에 넣지 않았다. 모델 선택에 영상을 살펴봤으므로 블라인드 정확도 시험은 아니다.

추가 사진의 실제 Commons API 저작자·라이선스·원본/파생 URL·SHA는 `data/commons-door-photo-batch-resume3-r2/provenance.json`에 있다. 주석 이미지는 변형본이고 다운로드 원본 bytes는 보존했다.

- [런던 가운데 문 승차](https://commons.wikimedia.org/wiki/File:Middle-Door-Boarding-P1640542_(49997680861).jpg): citytransportinfo, CC0. 모델 예측 전 전체 문 경계를 고정한1장만 추가train에 사용했다. 기존val/test 녹화와 Commons 승차 영상은 train에 추가하지 않았다.
- [정류장 boarding island](https://commons.wikimedia.org/wiki/File:Bus_boarding_from_boarding_island_(38270975711).jpg): Eric Fischer, CC BY2.0. 문 경계를 정밀하게 정하기 어려워 라벨 학습 제외.
- [Christchurch 승차](https://commons.wikimedia.org/wiki/File:Passengers_boarding_bus_at_Cathedral_Square,_Christchurch.jpg): Archives New Zealand, CC BY2.0. 원본900px SHA1 일치, 문 경계 가림으로 학습 제외.
- [Manhattan 승차](https://commons.wikimedia.org/wiki/File:BOARDING_A_BUS_IN_THE_FINANCE_DISTRICT_OF_LOWER_MANHATTAN_-_NARA_-_549921.jpg): Wil Blanche/NARA, public domain. 문 경계 가림으로 학습 제외.

새1장 보강은 실제 학습을 끝냈지만 기존 양성 검출을 잃어 미채택했다. 사진4장 확보를4장 학습이나 승차 정확도 검증으로 표현하지 않는다.
