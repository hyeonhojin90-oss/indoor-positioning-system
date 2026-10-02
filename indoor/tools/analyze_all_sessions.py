"""Offline inventory + sensor timeline audit. Does not modify raw files or engines.
Uses NumPy only; SVG plots are standalone, with no remote resources.
"""
import csv, hashlib, html, json, math
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'indoor/data'
OUT=DATA/'analysis/detailed-20260908'
INBOX=Path(r'C:\Users\20222967\Documents\카카오톡 받은 파일')

def stats(x):
    a=np.asarray(x,dtype=float);a=a[np.isfinite(a)]
    if not len(a): return None
    return dict(n=len(a),mean=float(a.mean()),sd=float(a.std()),median=float(np.median(a)),
                p05=float(np.quantile(a,.05)),p95=float(np.quantile(a,.95)),min=float(a.min()),max=float(a.max()))

def series(rows,sensor,start):
    values=[]
    for r in rows:
        if r.get('sensor')!=sensor:continue
        v=r.get('values');t=r.get('wall_time_ms')
        if not isinstance(v,list) or t is None:continue
        if not v or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in v):continue
        values.append(((t-start)/1000,v))
    if not values:return np.array([]),np.empty((0,1))
    values.sort(key=lambda p:p[0]);width=min(len(v) for _,v in values)
    return np.array([t for t,_ in values]),np.array([v[:width] for _,v in values])

def regular(t,v,hz=20):
    if len(t)<2:return np.array([]),np.array([])
    # Multiple callbacks at the same wall time are averaged, not counted as extra motion.
    u,idx,count=np.unique(t,return_inverse=True,return_counts=True)
    means=np.bincount(idx,weights=v)/count
    grid=np.arange(u[0],u[-1]+1e-8,1/hz)
    y=np.interp(grid,u,means)
    for a,b in zip(u[:-1],u[1:]):
        if b-a>.5:y[(grid>a)&(grid<b)]=np.nan
    return grid,y

def smooth(a,n):
    if not len(a):return a
    n=min(n,len(a));good=np.isfinite(a)
    num=np.convolve(np.where(good,a,0),np.ones(n),'same')
    den=np.convolve(good.astype(float),np.ones(n),'same')
    result=np.divide(num,den,out=np.full(len(a),np.nan),where=den>0)
    result[~good]=np.nan
    return result

def peaks(t,a,threshold):
    indices=[]
    for i in range(1,len(a)-1):
        if np.isfinite(a[i-1:i+2]).all() and a[i]>=threshold and a[i]>a[i-1] and a[i]>=a[i+1]:
            if not indices or t[i]-t[indices[-1]]>=.28:indices.append(i)
            elif a[i]>a[indices[-1]]:indices[-1]=i
    return t[indices]

def svg_chart(path,title,tracks,labels):
    w,h=1100,170*len(tracks)+55
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
         '<rect width="100%" height="100%" fill="white"/>',f'<text x="70" y="25" font-family="sans-serif" font-size="17">{html.escape(title)}</text>']
    xmax=max([float(t[-1]) for _,t,v in tracks if len(t)]+[1])
    for j,(name,t,v) in enumerate(tracks):
        top=55+j*170;out.append(f'<text x="12" y="{top+15}" font-family="sans-serif" font-size="12">{html.escape(name)}</text>')
        out.append(f'<path d="M85 {top+20} V{top+140} H1070" fill="none" stroke="#aab"/>')
        finite=np.isfinite(v)
        if len(v) and finite.any():
            lo,hi=float(np.nanmin(v)),float(np.nanmax(v));hi=max(hi,lo+1e-3)
            stride=max(1,len(v)//1800);parts=[];active=False
            for k in range(0,len(v),stride):
                if not np.isfinite(v[k]):active=False;continue
                x=85+t[k]/xmax*985;y=top+140-(v[k]-lo)/(hi-lo)*115
                parts.append(f'{"L" if active else "M"}{x:.2f},{y:.2f}');active=True
            out.append(f'<path d="{" ".join(parts)}" stroke="#1466ad" stroke-width="1.2" fill="none"/>')
            out.append(f'<text x="30" y="{top+40}" font-size="11">{hi:.2f}</text><text x="30" y="{top+140}" font-size="11">{lo:.2f}</text>')
        else:out.append(f'<text x="100" y="{top+80}" font-size="14">No recorded sensor</text>')
        for i,lab in enumerate(labels):
            x=85+lab['time']/xmax*985
            out.append(f'<path d="M{x:.2f} {top+20} V{top+140}" stroke="#b86" stroke-dasharray="3 4"/>')
            if j==0:out.append(f'<text x="{x:.2f}" y="{top+12}" font-size="10">L{i}</text>')
        out.append(f'<text x="85" y="{top+157}" font-size="11">0 s</text><text x="1010" y="{top+157}" font-size="11">{xmax:.1f} s</text>')
    path.write_text(''.join(out)+'</svg>',encoding='utf8')

def analyze(path,meta):
    raw=path.read_bytes();rows=[];errors=[]
    for i,line in enumerate(raw.decode('utf-8-sig').splitlines()):
        try:rows.append(json.loads(line))
        except Exception:errors.append(i+1)
    start=rows[0].get('wall_time_ms',0);end=rows[-1].get('wall_time_ms',start)
    first=rows[0];route=meta.get('route_id') or first.get('label',{}).get('route_id','unknown')
    labels=[dict(time=(r.get('wall_time_ms',start)-start)/1000,location=r['label'].get('location',''),
                 lap=r['label'].get('lap_index'),kind=r.get('kind')) for r in rows if r.get('label')]
    # Free runs often have no truth laps: append an end boundary, explicitly not truth.
    bounds=labels[:]
    if not bounds:bounds=[dict(time=0,location='start',lap=0)]
    if bounds[-1]['time']<(end-start)/1000-.001:bounds.append(dict(time=(end-start)/1000,location='session_end (not position truth)',lap=None))
    sensor_names=sorted({r['sensor'] for r in rows if 'sensor' in r});ss={n:series(rows,n,start) for n in sensor_names}
    health={}
    for n,(t,v) in ss.items():
        dif=np.diff(t);positive=dif[dif>0]
        health[n]=dict(count=len(t),unique_wall_times=len(np.unique(t)),duplicate_wall_times=int((dif==0).sum()),
            median_dt_ms=float(np.median(positive)*1000) if len(positive) else None,
            max_gap_s=float(positive.max()) if len(positive) else None,gaps_over_500ms=int((positive>.5).sum()),
            invalid_records=sum(r.get('sensor')==n for r in rows)-len(t))
    empty=(np.array([]),np.empty((0,1)))
    at,av=ss.get('accelerometer_mps2',empty);at,an=regular(at,np.linalg.norm(av[:,:3],axis=1))
    dyn=an-smooth(an,17);pk=peaks(at,dyn,1.0)
    gt,gv=ss.get('gyroscope_rads',empty);gn=np.linalg.norm(gv[:,:3],axis=1)
    mt,mv=ss.get('magnetic_field_ut',empty);mn=np.linalg.norm(mv[:,:3],axis=1)
    pt,pv=ss.get('pressure_hpa',empty);pn=pv[:,0]
    ht,hv=ss.get('heading_degrees',empty);heading_source='absolute_heading_degrees'
    if len(ht):yaw=hv[:,0]
    else:
        ht,hv=ss.get('rotation_vector',empty);heading_source='quaternion_device_yaw_not_walking_heading'
        if len(ht):
            x,y,z=hv[:,0],hv[:,1],hv[:,2];qw=hv[:,3] if hv.shape[1]>3 else np.sqrt(np.maximum(0,1-x*x-y*y-z*z))
            yaw=np.degrees(np.arctan2(2*(qw*z+x*y),1-2*(y*y+z*z)))
        else:
            ht,hv=ss.get('device_motion_rotation_rads',empty);heading_source='ios_alpha_device_orientation_not_walking_heading';yaw=np.degrees(hv[:,0])
    if len(yaw):yaw=np.degrees(np.unwrap(np.radians(yaw)))
    yt,ys=regular(ht,yaw);ys=smooth(ys,11)
    # Two-second orientation changes, merged when overlapping, diagnostic only.
    turns=[];i=20
    while i<len(ys)-20:
        delta=ys[i+20]-ys[i-20]
        if np.isfinite(delta) and abs(delta)>=30:
            t=float(yt[i]);g=gn[(gt>=t-1)&(gt<=t+1)]
            turns.append(dict(time=t,device_yaw_change_2s=float(delta),gyro_rms=float(np.sqrt(np.mean(g*g))) if len(g) else None,
                peak_candidates=int(((pk>=t-1)&(pk<=t+1)).sum())))
            i+=40
        else:i+=1
    st,sv=ss.get('step_counter',empty);counter_base=0 if first.get('platform')=='ios' else first.get('start_step_counter',sv[0,0] if len(st) else 0)
    def step_at(t):
        found=sv[st<=t,0];return float(found[-1]) if len(found) else float(counter_base)
    # iOS pedometer is usually a separate event, not a sample sensor.
    ped=[((r['wall_time_ms']-start)/1000,r['steps_since_start']) for r in rows if 'steps_since_start' in r and 'wall_time_ms' in r]
    if not len(st) and ped:
        st=np.array([t for t,v in ped]);sv=np.array([[v] for t,v in ped]);counter_base=0
    segments=[]
    for a,b in zip(bounds[:-1],bounds[1:]):
        lo,hi=a['time'],b['time'];d=dyn[(at>=lo)&(at<hi)];m=mn[(mt>=lo)&(mt<hi)];p=pn[(pt>=lo)&(pt<hi)];y=ys[(yt>=lo)&(yt<hi)];g=gn[(gt>=lo)&(gt<hi)]
        y=y[np.isfinite(y)]
        valid=d[np.isfinite(d)];npk=int(((pk>=lo)&(pk<hi)).sum());steps=step_at(hi)-step_at(lo) if len(st) else None
        segments.append(dict(start_s=lo,end_s=hi,from_label=a['location'],to_label=b['location'],duration_s=hi-lo,
            counter_delta=steps,accel_peak_candidates=npk,dynamic_rms=float(np.sqrt(np.mean(valid**2))) if len(valid) else None,
            active_fraction=float(np.mean(np.abs(valid)>.8)) if len(valid) else None,
            zero_counter_with_motion=steps==0 and npk>=2,magnetic=stats(m),
            pressure_median_delta=float(np.median(p[-max(1,len(p)//5):])-np.median(p[:max(1,len(p)//5)])) if len(p) else None,
            device_yaw_delta=float(y[-1]-y[0]) if len(y)>1 else None,gyro_rms=float(np.sqrt(np.mean(g*g))) if len(g) else None,
            turns=[q for q in turns if lo<=q['time']<hi]))
    digest=hashlib.sha256(raw).hexdigest()
    issues=[]
    if meta.get('include_in_analysis') is False:issues.append('Excluded by existing manifest; quality audit only, not training or truth.')
    if route in ['2F_STUDY','2F_EXTENSION']:issues.append('Legacy 2107 labels: may include return via corridor; do not assume labels are wrong or a direct wall crossing. Actual detour timing unresolved.')
    if len(labels)<=1:issues.append('No intermediate truth labels; final displayed position is an engine estimate, not arrival evidence.')
    if heading_source!='absolute_heading_degrees':issues.append('Device orientation is not calibrated walking direction; no absolute map-path accuracy claim.')
    if any(s['zero_counter_with_motion'] for s in segments):issues.append('Zero counter increments coexist with acceleration peaks; counter-only segment distance is unreliable.')
    if not meta:issues.append('External/unregistered source; analyzed as diagnostic, not automatically accepted for training.')
    r=dict(file=path.name,path=str(path),sha256=digest,bytes=len(raw),route=route,device=first.get('device_model',first.get('device')),
        existing_status=meta.get('status','unregistered_diagnostic'),previous_analysis=meta.get('previous_analysis','none found'),
        checksum_matches=not meta.get('sha256') or meta['sha256']==digest,parse_errors=errors,
        duration_s=(end-start)/1000,ended=rows[-1].get('kind')=='session_end',labels=labels,sensors=health,
        wall_time_reversals=sum(b.get('wall_time_ms',start)<a.get('wall_time_ms',start) for a,b in zip(rows,rows[1:])),
        counter_total=step_at((end-start)/1000)-counter_base if len(st) else None,
        acceleration_peaks={str(th):len(peaks(at,dyn,th)) for th in [.7,1.,1.3]},magnetic=stats(mn),pressure=stats(pn),
        pressure_endpoint_delta=float(np.median(pn[-min(len(pn),10):])-np.median(pn[:10])) if len(pn) else None,
        heading_source=heading_source,turn_candidates=turns,segments=segments,issues=issues,
        recorded_final_position=rows[-1].get('final_position'),recorded_final_fusion=rows[-1].get('final_fusion'))
    stem=path.stem
    svg_chart(OUT/f'{stem}.svg',stem,[('Dynamic accel (m/s2)',at,dyn),('Magnetic norm (uT)',mt,mn),
        ('Pressure (hPa)',pt,pn),('Device orientation (deg)',yt,ys),('Gyroscope norm (rad/s)',gt,gn)],labels)
    # Downsample only for review artifact, not metrics.
    with (OUT/f'{stem}-timeline.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f);writer.writerow(['sensor','time_s','value'])
        for name,t,v in [('dynamic_accel',at,dyn),('magnetic_norm',mt,mn),('pressure',pt,pn),('device_yaw',yt,ys),('gyro_norm',gt,gn)]:
            for k in range(0,len(t),max(1,len(t)//2500)):
                if np.isfinite(v[k]):writer.writerow([name,round(float(t[k]),4),float(v[k])])
    write_session(r)
    return r

def fmt(v):return '—' if v is None else f'{v:.3f}' if isinstance(v,(float,int)) else str(v)
def write_session(r):
    stem=Path(r['file']).stem
    text=[f"# {r['route']} / {r['file']}",f"\n원본: `{r['path']}`",f"\nSHA-256: `{r['sha256']}`",
      f"\n기존 분석: {r['previous_analysis']} / 기존 상태: {r['existing_status']}",
      f"\n시간 {r['duration_s']:.3f}초 · 카운터 {fmt(r['counter_total'])} · 가속도 피크 후보(.7/1/1.3): {r['acceleration_peaks']}",
      f"\n방향 출처: `{r['heading_source']}`. 휴대폰 회전 후보를 보행 회전으로 확정하지 않는다.",
      f"\n![Sensor timelines]({stem}.svg)","\nL0,L1…은 원본 라벨 시점이다. 표시 위치 정답이나 지도 경로가 아니다.",
      '\n## 품질·한계','\n'+'\n'.join('- '+s for s in r['issues']),
      '\n## 센서 기록', '\n|센서|샘플|동일 wall time|중앙 간격 ms|최대 공백 s|', '|---|---:|---:|---:|---:|']
    for n,s in r['sensors'].items():text.append(f"|{n}|{s['count']}|{s['duplicate_wall_times']}|{fmt(s['median_dt_ms'])}|{fmt(s['max_gap_s'])}|")
    text += ['\n## 랩 구간 분석','\n|구간|초|카운터|피크 후보|동적 RMS|B 평균±SD µT|기압차 hPa|기기방향 변화°|','|---|---:|---:|---:|---:|---|---:|---:|']
    for s in r['segments']:
        m=s['magnetic'];text.append(f"|{s['from_label']} → {s['to_label']}|{fmt(s['duration_s'])}|{fmt(s['counter_delta'])}|{s['accel_peak_candidates']}|{fmt(s['dynamic_rms'])}|{fmt(m['mean'])+' ± '+fmt(m['sd']) if m else '—'}|{fmt(s['pressure_median_delta'])}|{fmt(s['device_yaw_delta'])}|")
    text+=['\n## 2초 창의 휴대폰 방향 변화 후보','\n|시점 s|방향 변화°|자이로 RMS|동시 피크 후보|','|---:|---:|---:|---:|']
    for t in r['turn_candidates']:text.append(f"|{fmt(t['time'])}|{fmt(t['device_yaw_change_2s'])}|{fmt(t['gyro_rms'])}|{t['peak_candidates']}|")
    text+=['\n각도 변화30°/2초는 진단용 기준이다. 자세 변화·자기장 교란·축 정의 영향을 포함한다. 가속도 피크도 실제 걸음 정답이 아니다. 샘플 수는 물리 센서의 독립 관측 수와 같지 않다.']
    (OUT/f'{stem}.md').write_text('\n'.join(text)+'\n',encoding='utf8')

def barometer(path):
    raw=path.read_bytes();lines=raw.decode('utf-8-sig').splitlines();rows=list(csv.DictReader(x for x in lines if not x.startswith('#')))
    t=np.array([float(r['time']) for r in rows]);p=np.array([float(r['P']) for r in rows]);t=t-t[0]
    phases=[]
    for i in range(0,max(1,len(t)-2),3):
        tt=t[i:i+4];pp=p[i:i+4]
        if len(tt)<2:continue
        slope=float(np.polyfit(tt,pp,1)[0]);phases.append(dict(start=float(tt[0]),end=float(tt[-1]),slope=slope,
            state='pressure_change' if abs(slope)>.025 else 'near_stable'))
    r=dict(file=path.name,path=str(path),sha256=hashlib.sha256(raw).hexdigest(),samples=len(t),duration_s=float(t[-1]),pressure=stats(p),
        endpoint_delta=float(p[-1]-p[0]),equivalent_floor_intervals=abs(float(p[-1]-p[0]))/.44,phases=phases,
        limitation='One sample: no continuous movement analysis' if len(t)<2 else 'Pressure signal only; floor endpoints not inferred from filename. .44 hPa is provisional interval, not absolute floor.')
    svg_chart(OUT/f'{path.stem}.svg',path.stem,[('Pressure hPa',t,p)],[])
    return r

def main():
    OUT.mkdir(parents=True,exist_ok=True);metadata={}
    checks=json.loads((DATA/'analysis/source_checksums.json').read_text(encoding='utf8'))
    for name in ['manifest.json','ios_manifest.json']:
        manifest=json.loads((DATA/name).read_text(encoding='utf8'))
        for s in manifest['sessions']:
            metadata[s['file']]={**s,'sha256':s.get('sha256',checks.get(s['file'],{}).get('sha256')),
                'previous_analysis':'4F repeated multi-sensor analysis' if name.startswith('ios') else 'baseline summary/segments; excluded logs quality only' if s.get('include_in_analysis') is False else 'baseline summary/segments; special routes no path accuracy'}
    paths=sorted((DATA/'raw').rglob('*.jsonl'))+sorted(INBOX.glob('indoor_positioning*.jsonl'))
    seen={};duplicates=[];results=[]
    for path in paths:
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:duplicates.append(dict(path=str(path),same_as=seen[digest],sha256=digest));continue
        seen[digest]=str(path)
        result=analyze(path,metadata.get(path.name,{}));results.append(result)
        print(path.name,len(result['segments']),'segments',flush=True)
    pressure=[barometer(p) for p in sorted(INBOX.glob('barometer_*.csv'))]
    # Compare distributions across branch sessions; never treat same-run windows as test accuracy.
    branch=[r for r in results if r['route'] in ['2F_2107_OPEN','2F_STUDY','2F_EXTENSION','3F_EXTENSION','3F_IT_HALL']]
    pairs=[]
    for i,a in enumerate(branch):
        for b in branch[i+1:]:
            if a['route'][0]!=b['route'][0]:continue
            x,y=a['magnetic'],b['magnetic'];pooled=math.sqrt((x['sd']**2+y['sd']**2)/2)
            pairs.append(dict(a=a['route'],b=b['route'],standardized_mean_gap=abs(x['mean']-y['mean'])/pooled,
                central90_ranges_overlap=max(x['p05'],y['p05'])<=min(x['p95'],y['p95'])))
    report=dict(scope='Repository raw + known Kakao sensor inbox; device-only/unlocated logs excluded from completeness claim',
      sessions=results,duplicates=duplicates,barometers=pressure,branch_distribution_comparisons=pairs)
    (OUT/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    lines=['# 전체 실내 센서 자료 상세분석 — 2026-09-08',f'\n중복 제외 JSONL {len(results)}개, 기압 CSV {len(pressure)}개. 동일해시 사본 {len(duplicates)}개는 중복 계산하지 않았다.',
      '\n## 분석 범위와 방법','\n저장소 raw와 알려진 카카오톡 센서 폴더를 전수 점검했다. 휴대폰에만 남은 데이터, 현재 원본 경로가 없는 과거 기록까지 분석했다고 주장하지 않는다. 제외 manifest는 유지하며 외부 자료는 자동 학습 편입하지 않는다.',
      '\n시간축: wall_time_ms; 동일시각 평균 후 가속도20Hz 재표본화, 0.5초 초과 공백은 보간하지 않음. 0.85초 이동평균 제거, 최소 피크 간격0.28초와 높이0.7/1.0/1.3 m/s² 민감도 비교. 회전은2초 기기방향차30° 이상 후보이며 실제 회전·위치 정답이 아님. 기압 구간차는 앞/뒤20% 중앙값. 원시 통계와 파생 궤적을 혼동하지 않는다.',
      '\n## 로그별 결과','\n|파일|경로|초|카운터|피크1.0|회전후보|상태|','|---|---|---:|---:|---:|---:|---|']
    for r in results:lines.append(f"|[{r['file']}]({Path(r['file']).stem}.md)|{r['route']}|{fmt(r['duration_s'])}|{fmt(r['counter_total'])}|{r['acceleration_peaks']['1.0']}|{len(r['turn_candidates'])}|{r['existing_status']}|")
    lines+=['\n## 분기 자기장 분포 비교','\n동일 플랫폼·동일 층의 세션 전체 분포 비교다. 이동구간 구성이 달라 구역 분류 정확도가 아니며 반복 세션 검증을 대체하지 않는다.','\n|경로쌍|평균차/합동SD|중앙90% 범위 겹침|','|---|---:|---|']
    for p in pairs:lines.append(f"|{p['a']} / {p['b']}|{p['standardized_mean_gap']:.3f}|{p['central90_ranges_overlap']}|")
    lines+=['\n## 기압 CSV','\n|파일|샘플|초|끝-시작 hPa|0.44hPa 간격 수|','|---|---:|---:|---:|---:|']
    for r in pressure:lines.append(f"|[{r['file']}]({Path(r['file']).stem}.svg)|{r['samples']}|{r['duration_s']:.3f}|{r['endpoint_delta']:.4f}|{r['equivalent_floor_intervals']:.2f}|")
    lines+=['\n0.44hPa 간격 수는 압력 변화를 환산한 참고값이며 실제 층이나 층 이동 정답이 아니다. 20-35-51 CSV의 실제 이동 경로는 별도 확인 필요.',
       '\n## 원본·검증','\n`analysis.json`에 모든 원본 경로/해시, 기존 분석 범위, 센서 공백, 랩별 수치, 휴대폰 회전 후보와 기록된 엔진 종료값을 보존했다. 각 세션 MD/SVG/CSV로 시간축을 검토할 수 있다. 엔진 코드·지도·원시 데이터·manifest는 변경하지 않았다.']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    cards=''.join(f'<li><a href="{Path(r["file"]).stem}.svg">{html.escape(r["route"])} / {r["file"]}</a></li>' for r in results)
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Sensor audit</title><h1>Sensor timelines</h1><p>Device orientation is not walking-direction truth. L markers are recorded labels.</p><ul>'+cards+'</ul>',encoding='utf8')
    assert all(r['checksum_matches'] for r in results),'Historical checksum mismatch'
    assert all(hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()==r['sha256'] for r in results+pressure),'Raw changed during run'
    print(json.dumps(dict(jsonl=len(results),csv=len(pressure),duplicates=len(duplicates),branch_pairs=pairs),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
