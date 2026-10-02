"""Offline RoNIN ResNet inference on Android JSONL. No endpoint fitting or retraining.
Run with tools/passenger-counter/.venv/Scripts/python.exe.
Outputs raw horizontal velocity and start-relative ENU trajectory, not a deployed map fix.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import torch
from scipy.spatial.transform import Rotation, Slerp

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
from model_resnet1d import ResNet1D, BasicBlock1D, FCOutputModule

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load_model(checkpoint):
    net = ResNet1D(6, 2, BasicBlock1D, [2, 2, 2, 2], base_plane=64,
                   output_block=FCOutputModule, kernel_size=3, fc_dim=512,
                   in_dim=7, dropout=.5, trans_planes=128)
    saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
    net.load_state_dict(saved['model_state_dict'], strict=True)
    return net.eval()

def prepare(file):
    rows = [json.loads(s) for s in file.read_text(encoding='utf-8').splitlines() if s.strip()]
    start = rows[0]['wall_time_ms'] / 1000
    end = [r for r in rows if r['kind'] == 'label'][-1]['wall_time_ms'] / 1000
    offsets = [r['wall_time_ms']/1000-r['sensor_timestamp_ns']/1e9 for r in rows if 'sensor_timestamp_ns' in r]
    offset = float(np.median(offsets))
    streams = {}
    for name in ['accelerometer_mps2', 'gyroscope_radps', 'rotation_vector']:
        samples = []
        for r in rows:
            if r.get('sensor') != name: continue
            t = r.get('sensor_wall_time_ms', r['sensor_timestamp_ns']/1e6 + offset*1000)/1000
            if not start <= t <= end: continue
            v = r['values'][:4 if name == 'rotation_vector' else 3]
            if name == 'rotation_vector' and len(v) == 3:
                v = v + [np.sqrt(max(0, 1-np.dot(v,v)))]
            if np.isfinite(v).all(): samples.append((t, v))
        by_time = dict(samples)
        t = np.array(sorted(by_time), dtype=np.float64)
        if len(t) < 200: raise ValueError('insufficient '+name)
        values = np.array([by_time[x] for x in t], dtype=np.float64)
        streams[name] = (t, values)
    lo = max(s[0][0] for s in streams.values())
    hi = min(s[0][-1] for s in streams.values())
    ts = lo + np.arange(int((hi-lo)*200)+1)/200
    qtime, quats = streams['rotation_vector']
    norms = np.linalg.norm(quats, axis=1)
    if np.any(norms < .5): raise ValueError('invalid rotation vector')
    orientation = Slerp(qtime, Rotation.from_quat(quats/norms[:,None]))(ts)
    vectors = []
    diagnostics = {}
    for name in ['gyroscope_radps','accelerometer_mps2']:
        t,v = streams[name]
        sampled = np.column_stack([np.interp(ts,t,v[:,i]) for i in range(3)])
        vectors.append(orientation.apply(sampled))
    for name,(t,v) in streams.items():
        dt=np.diff(t)
        diagnostics[name]={'samples':len(t),'medianHz':float(1/np.median(dt)),
                           'maxGapMs':float(dt.max()*1000),'gapsOver250ms':int((dt>.25).sum())}
    # Match the authors' global-frame order: gyro xyz then acceleration xyz including gravity.
    features = np.concatenate(vectors,axis=1).astype(np.float32)
    gravity = vectors[1]
    return ts,features,{'streams':diagnostics,'startCoverageDelayS':float(lo-start),
        'endCoverageGapS':float(end-hi),'medianGlobalAcceleration':np.median(gravity,axis=0).tolist(),
        'sensorClockOffsetS':offset,'hasLongGap':any(x['gapsOver250ms'] for x in diagnostics.values())}

def infer(net, ts, features):
    # One-second trailing window; first output at t=1s, then 20Hz, held until next output.
    indices=np.arange(200,len(features),10)
    if not len(indices): raise ValueError('less than one model window')
    predictions=[]
    with torch.inference_mode():
        for i in range(0,len(indices),128):
            batch=np.stack([features[j-200:j].T for j in indices[i:i+128]])
            predictions.append(net(torch.from_numpy(batch)).numpy())
    velocity=np.concatenate(predictions)
    if not np.isfinite(velocity).all(): raise ValueError('nonfinite model output')
    times=ts[indices]
    dt=np.diff(np.r_[times,ts[-1]])
    increments=velocity*dt[:,None]
    position=np.cumsum(increments,axis=0)
    return times,velocity,position,float(np.sum(np.linalg.norm(increments,axis=1)))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--output',default='indoor/data/analysis/ronin-android-20260923');args=parser.parse_args()
    torch.set_num_threads(4)
    checkpoint=ROOT/'indoor/data/models/ronin/ronin_resnet/checkpoint_gsn_latest.pt'
    net=load_model(checkpoint)
    data=json.loads((ROOT/'indoor/data/analysis/weinberg-combined-20260923/results.json').read_text())
    out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True)
    results=[]
    for fold in data['folds'][:args.limit or None]:
        file=ROOT/fold['file'];began=time.time()
        item={'file':fold['file'],'sha256':sha(file),'route':fold['route'],'distanceM':fold['distanceM']}
        try:
            ts,feat,diagnostic=prepare(file)
            times,velocity,position,path_length=infer(net,ts,feat)
            displacement=float(np.linalg.norm(position[-1]))
            item.update(status='inferred',diagnostics=diagnostic,windows=len(times),
                displacementM=displacement,integratedPathM=path_length,
                displacementMagnitudeErrorM=abs(displacement-fold['distanceM']),
                pathLengthErrorM=abs(path_length-fold['distanceM']),
                maxSpeedMps=float(np.linalg.norm(velocity,axis=1).max()),
                warmupUnestimatedS=float(times[0]-ts[0]),elapsedS=time.time()-began)
            np.savez_compressed(out/(file.stem+'.npz'),timeFromFirstSample=times-ts[0],velocityEnu=velocity,positionEnu=position)
        except Exception as error:
            item.update(status='failed',error=str(error))
        results.append(item)
        print(json.dumps(item,ensure_ascii=False),flush=True)
    ok=[r for r in results if r['status']=='inferred']
    report={'model':'official RoNIN ResNet18 checkpoint_gsn_latest.pt','checkpointSha256':sha(checkpoint),
        'inferenceExecuted':bool(ok),'runtimeDefault':False,'trainingOnLocalLogs':False,
        'method':'Android rotation-vector device-to-ENU; sensor clocks; offline linear IMU interpolation + quaternion SLERP to 200Hz; gyro then acceleration including gravity; trailing200 samples; 20Hz velocity; forward hold integration after1s warmup',
        'limitations':['No start Tango calibration; ENU yaw is not fitted using endpoint','Android calibrated IMU used without dataset-specific bias/scale calibration',
            '200Hz interpolation cannot restore missing information; native rates and gaps reported',
            'Offline interpolation uses next sensor sample; not a strictly causal phone pipeline',
            'One-second warmup unestimated, no retrospective extrapolation',
            'Displacement magnitude error is NOT 2D endpoint position error; opposite/wrong heading can have same magnitude',
            'Straight full routes only; no map/particle/BLE/AP integration and no mobile deployment',
            'No local training; small same-user/device set is development evaluation'],
        'summary':{'succeeded':len(ok),'failed':len(results)-len(ok),
            'displacementMagnitudeMAE':float(np.mean([r['displacementMagnitudeErrorM'] for r in ok])) if ok else None,
            'pathLengthMAE':float(np.mean([r['pathLengthErrorM'] for r in ok])) if ok else None},'sessions':results}
    (out/'evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
