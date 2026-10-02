"""Record interrupted-run recovery and verified post-resume evidence."""
import json
from pathlib import Path
from record_resume2_status import prepend
from latest_usage import latest

title='2026-10-01 재중단 복구: 새 승차 영상·보조 문 모델 조건부 취득'
usage=latest(Path('C:/Users/20222967/.codex/sessions/2026/09/18/rollout-2026-09-18T20-25-08-01a0b417-a35f-7f33-a8e7-d28bc7398f3d_01a0b443-5bc9-7c11-80e2-c2c99e610aac.jsonl'))
body='''사용자 재개 지시에 따라 실제 작업 계속 중. 중단 기준은 최신5시간 잔여5% 도달이다. Orin Nano 미연결. 메모리의 과거 결과는 실제 파일/전체source 재검증 후 사용했다.

복구: 중단 전 원본/오른쪽 low-score 실행은 summary513·전체source/replay·구현 무변경 감사를 확인했다. 이전 프로세스 exit코드는 도구 세션 소실로 재확인하지 못했다. 왼쪽 최초 실행은 tracks513이 있어도 summary가 없어 완료로 처리하지 않고 보존했다. 새 retry는 실제 exit0·summary513·전체감사 완료.

낮은점수 .05 후보: 원본6/0·고정6/6, 오른쪽5/0·3/6(청록 관측249가 고정255..315보다 조기), 왼쪽retry6/1·5/6(동일 olive ID27이 IN67/OUT69/IN73 흔들림). 사람이6명인 것이 아니라 같은사람을 중복 집계했다. confidence/low만 낮추는 후보 미채택, 창 조정 없음. 큰 보조pose-M 현재검출좌표 후보 왼쪽 전체5/0·5/6이며 작은pose와 비교해 누락 회복 없음·미채택.

새 소스 `data/commons-moving-bus-boarding-resume3.webm`: Yathra Visheshangal의 A man boarding a moving bus.webm, Commons CC BY4.0. 원본 SHA1 c2b6997afdbdcd99c13af0bbd62790a8e43441aa 대조, SHA25688e0f1be67eb7080e1ff0b8b42ede76d0a53dd12a5a311980a40548dcabe8f0d.182프레임30fps. 원본 유지, 학습 미사용, source.json에 저작자/라이선스/URL 보존. 움직이는 버스/움직이는 카메라/넓은측면1명 장면이며 사용자 정류장 실험이나 완전한 독립 블라인드 정답셋 아님. 기존셔틀 촬영의 합성 변형과는 다른 소스다.

새 소스 전체 비교: 기존 문416/640 모두 자동문0·IN0/OUT0. 사진보강 문640은 자동문47·IN1/OUT0(frame142 ID22). 원본110/120/130/142/155/170에서 실제 탑승자의 일치를 확인했다. 사후보조 검토이며 정확도100%라고 표현하지 않는다. 모델만 바꾼 것의 부작용도 확인: 기존 초록 전체 원본5/0·고정4/6, 왼쪽5/0·3/6, 오른쪽6/0·5/6. 오른쪽 ID19/31은 olive 동일인을 반복집계한다. 새 소스1건 성공으로 기존 기본 승격 금지.

문 모델640 실제6프레임 PT/ONNX 비교는 양성5개·박스/점수 일치, `compare_model_frames.py`로 재현. 이는 표본 model parity이며 전체추적/Orin 성능 증거와 구분한다.

새 선택 후보 `door_acquisition_fallback`: 기존 custom 모델/입력416을 유지하다가 현재잠금 없음+주 모델승객지원후보 없음+strong 버스 검출일 때만 별도 사진보강640으로 취득한다. 후보가 선택되면 같은모델/입력으로 안정성확인과 잠금재검출을 계속한다. 현재유효문은 보조모델로 교체하지 않는다. 기본 미설정이며 집계 문턱/GT 미변경. 실제 전체 비교 진행 중이다.

Orin 전달 r4는50파일+6ONNX/기존모델·연결된PT,13개 config/source/model/event baseline, AGPL LICENSE 원문·환경읽기·장치엔진빌드·실제프레임parity·target regression 검사 포함. ZIP293680045bytes·CRC/해시 검증 통과. 이 snapshot은 보조문취득 구현 전이며 현재 최신코드와 자동 동기화된 것이 아니다. `verify_target_run.py`는 같은총계라도 다른 ID/관측/확정/문generation/모델/설정/source면 실패하며 ONNX CUDA provider를 요구한다. 실제Windows full baseline에서 이벤트일치여도 Jetson/CUDA/CPU provider 이유로 올바르게 실패했다. 기기/카메라 실시간/온도/전력/메모리/지연은 미검증. TensorRT model변경은 새parity 없이 SHA차이를 승인하지 않는다.

진단 정정: 왼쪽 frame250 ID4는 오른쪽 가장자리 행인으로 teal이 아니다. 이전 partial-pose probe의 회복0은 해당표본 일반 진단이며 teal 직접회복 근거가 아니다. 원본전체모음으로 teal 최초ID1→103/107→148의 가림/박스분할을 별도로 확인 중. 현재검출좌표 trace에 head-flow만 재생하면 원본5/0·왼쪽4/0·오른쪽5/0으로 악화/개선없음. 런타임 미도입. 모델 크기나 flow만으로 해결됐다고 하지 않는다.
'''
names=['commons-boarding-acquisition-fallback-resume3-full','green-acquisition-fallback-resume3-full','green-default-after-acquisition-resume3-full']
for name in names:
    root=Path('runs')/name
    if (root/'summary.json').exists():
        s=json.loads((root/'summary.json').read_text());state=f"summary {s['frames']}프레임 {s['counts']}, audit={(root/'completion-audit.json').exists()}"
    else:state='실행 중; 전체 성공 판정 없음'
    body+=f'\n- `{name}`: {state}\n'
body+=f"\n사용량 {usage['timestamp']}: 잔여{usage['primary_remaining_percent']}%, fresh={usage['fresh']}, stop={usage['stop_reached']}.\n"
for name in ['CHECKPOINT.md','STATUS.md','RESULTS.md']:prepend(Path(name),title,body)
brief='재중단 실행 복구. low-score는 중복/조기집계로 미채택, 큰pose 누락 유지. 새 Commons CC BY4.0 원본182프레임에서 기존문0명→보강문640 승차1명·인물소스 확인, 기존원본4/6로 악화하여 공통미채택. 기존문을 보존하며 strong버스+문취득실패에서만 별도 보조문모델을 쓰는 선택후보 실제 비교 중. Orin r4 50파일/13baseline/장치회귀검사·ZIP무결성 확인, 실기기미검증. 잔여5%까지 계속; 상세 tools/passenger-counter/CHECKPOINT.md.'
for name in ['CURRENT_STATUS.md','WORKLOG.md']:prepend(Path('../../docs')/name,title,brief)
print('Recovery, completed evidence and pending comparisons saved.')
