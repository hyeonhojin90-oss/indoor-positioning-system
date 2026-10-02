"""Record verified follow-up evidence and live pending jobs without success guesses."""
import csv,json
from pathlib import Path
from record_resume2_status import prepend

def main():
    title='2026-10-01 후속 개선: 하차 증거·표시 병목·사진 보강'
    results=list(csv.DictReader(Path('runs/door-photo-enriched-retention-20261001-r2/training/door/results.csv').open()))
    best=max(results,key=lambda r:float(r['metrics/mAP50-95(B)']))
    old=json.loads(Path('runs/door-photo-enriched-old-baseline-20261001-r2/metrics.json').read_text())['metrics']
    new=json.loads(Path('runs/door-photo-enriched-retention-20261001-r2/test-metrics.json').read_text())
    body=f'''작업 진행 중, 최신 own-chat 5시간 잔여가 엄격히5% 미만일 때만 중단한다. 기본 후보는 기존 그대로이며 Orin/TensorRT·독립 실제 승차 정확도는 미검증이다.

완료: 사람seg+발 증거 하차 보정의 원본/오른쪽/왼쪽 전체513프레임6/0,5/0,5/0, 고정 부분6/6,4/6,4/6. 반전 하차 전체513프레임1/3이며 이전 실행과 모든 입력추적·이벤트가 정확히 같았다(`guard-only-regression.json`). 정지60프레임0/0, 기존 기본 재실행513프레임6/0이며 전체 검출·관측시점·집계시점 일치와 인물6/6을 확인했다. 이들 완료 감사는 런타임 수정 전에 기록했다. 현재 audit를 다시 하면 이후 표시/task hint 변경의 run.py drift가 나올 수 있으며 과거 완료 증거를 덮어쓰지 않는다.

병목 원인 정정: 기존 설정은 이미 CPU threads2였으며 완료 요약에서도 actual2였다. 처음 unbounded-thread 원인 설명은 잘못됐고 interrupted.json을 정정했다. 동일 밀집1080x1920프레임27/26/26명 결과에서 마스크 표시3.1..3.6s, 박스 표시0.006..0.043s. 여러 작업 동시 실행이므로 실기기 FPS 벤치마크는 아니다. 집계에 사용하지 않는 mask 표시를 run.py에서 끄고 박스·측정 발점은 유지했다. 초기 느린 음성 실행과 이후 재시도4건은 명시적으로 interrupted이며 전체 검증으로 쓰지 않는다. 새 box-render 전체실행에서 검출·이벤트 일치를 확인 중이다.

공식 사람seg를 dynamic ONNX로 변환했다. 416입력 고정8프레임 양성49박스·class·confidence IoU>=.99/pixel<=1/score<=.001 일치. 마스크 자체는 비교하지 않았다. 실제 사람입력640의 전체 추적·집계 비교는 아래 새 실행으로 검증 중이다. ONNX는 person_task=segment를 명시하도록 허용하여 detect로 잘못 해석하지 않게 했다. exporter로 파일을 만들었다고 Orin 성능/집계 성공으로 처리하지 않는다.

사진 보강훈련: 이전 bootstrap12/2/3 split과 이미지/라벨을 그대로 복사하고 Boston/Nigeria 독립2사진을 train, Vancouver를 val, Kenya를 test에 추가하여14/3/4로 준비했다. 문 전체·다른 열린/닫힌 문도 기존 고정 좌표로 라벨링했다. 가려진3사진은 음성으로 넣지 않았다. 모든 사진은 앞서 진단했으므로 blind holdout은 아니며 사람 검토가 없다. AdamW lr0=.0001, freeze10, 416, 40최대/patience10로 {len(results)}epochs 완료, validation fitness 최고 epoch{best['epoch']}를 선택했다. 고정 같은 test4장/3문에서 이전 mAP50={old['metrics/mAP50(B)']:.4f}, 새={new['metrics/mAP50(B)']:.4f}; 새 recall={new['metrics/recall(B)']:.3f}. 작은 진단 집합의 개선이며 승차 정확도와 별개다.

고정 conf.35 사진 진단: 학습된 Boston/Nigeria 선택IoU .734/.765. 학습하지 않은 Vancouver는 실제문 raw가 있어도 창문을 선택했고 Kenya 실제문 raw IoU .705이나 승객 지지가 부족하여 선택하지 않았다. 사진 모델이 놓침/창문 선택/증거 부족을 분리한다. Grounding Nigeria는 실제앞문을 못찾았고 Kenya는 창문 선택. confidence*승객 지지의 저장 후보 진단은 Vancouver를 IoU .865로 바꿨지만 다른 실패는 그대로다. `confidence_door_selection.py`는 optional 후보 구현과3테스트만 완료했고 런타임에 아직 연결하지 않았다. 기존 locked door 유지와 최소 승객지지는 완화하지 않는다.

전체 단위 테스트120통과, git diff --check 통과(기존 CRLF 경고). 새 학습모델 기본 미채택. 다음은 아래 전체실행 완료 감사/ONNX 박스·발점·이벤트 대조 후, confidence 선택을 실험 설정에만 연결하고 새 문 모델의 원본·이동·음성 회귀를 확인한다.
'''
    for name in ['people-negative-person-seg-exit-guard','green-person-seg-exit-guard-onnx','green-right80-person-seg-exit-guard-onnx','green-left80-person-seg-exit-guard-onnx']:
        root=Path('runs')/(name+'-box-render-20261001-r2-full')
        if (root/'summary.json').exists():
            r=json.loads((root/'summary.json').read_text());state=f"프로세스 요약 있음 {r['frames']}프레임 {r['counts']}; 완료 감사 여부={(root/'completion-audit.json').exists()}"
        else:state='진행 중, 전체 성공 판정 없음'
        body+=f'\n- `{root}`: {state}\n'
    for filename in ['CHECKPOINT.md','STATUS.md','RESULTS.md']:prepend(Path(filename),title,body)
    brief='사람seg+측정 발 하차 보정은 원본6/0·좌우5/0(고정6/6·4/6·4/6), 반전 기존1/3 유지. 기본 전체6/0·6/6 유지. 마스크 표시 병목3초/프레임을 확인해 박스만 표시하도록 수정하고 전체 ONNX·음성 재검사 중. 새 사진2장 보강훈련은 학습 사진 검출 개선이나 다른 사진 문 선택 실패가 남아 미채택. 테스트120통과. 중단 기준은 최신5시간 잔여5% 미만. 상세 현재 실행·정정·한계는 tools/passenger-counter/CHECKPOINT.md.'
    for filename in ['CURRENT_STATUS.md','WORKLOG.md']:prepend(Path('../../docs')/filename,title,brief)
    p=Path('SOURCES.md');text=p.read_text(encoding='utf-8')
    text=text.replace('박스 표시·진단 이미지는 변형본이다. 학습 미사용.',
        '박스 표시·진단 이미지는 변형본이다. 이후 Boston/Nigeria는 보강훈련 train, Vancouver val, Kenya test에 사용했다. 다른 가려진 사진은 학습하지 않았다. 사진 split은 recording별이며 blind 검증이 아니다.')
    p.write_text(text,encoding='utf-8')
    failures={
        'extra-door-photos-20261001-r2-schema-probe':'Missing status key; no complete diagnostic.',
        'extra-door-photos-20261001-r2-validated-probe':'Mistyped nonexistent model path; no complete diagnostic.'}
    for name,reason in failures.items():
        p=Path('runs')/name/'failure.json'
        if not p.exists():p.write_text(json.dumps(dict(completed=False,reason=reason),indent=2))

if __name__=='__main__':main()
