"""Input/shape/integration tests; do not claim physical accuracy from these."""
import json
import tempfile
from pathlib import Path
import numpy as np
import torch
from scipy.spatial.transform import Rotation
from run_android import prepare, infer, load_model, ROOT

def synthetic(rotation):
    rows=[{'kind':'session_start','wall_time_ms':1000000}]
    for i in range(301):
        t=1000000+i*10
        for sensor,values in [('accelerometer_mps2',rotation.inv().apply([0,0,9.81]).tolist()),
                              ('gyroscope_radps',[0,0,0]),('rotation_vector',rotation.as_quat().tolist())]:
            rows.append({'kind':'sample','sensor':sensor,'wall_time_ms':t,'sensor_wall_time_ms':t,'sensor_timestamp_ns':i*10000000,'values':values})
    rows.append({'kind':'label','wall_time_ms':1003000})
    return rows

with tempfile.TemporaryDirectory() as directory:
    features=[]
    for i,rot in enumerate([Rotation.identity(),Rotation.from_euler('xyz',[.6,-.3,1.5])]):
        file=Path(directory)/f'{i}.jsonl'
        file.write_text('\n'.join(json.dumps(r) for r in synthetic(rot)))
        ts,x,diagnostic=prepare(file)
        assert x.shape[1]==6 and not diagnostic['hasLongGap']
        np.testing.assert_allclose(np.median(x,axis=0),[0,0,0,0,0,9.81],atol=1e-5)
        features.append(x)
    np.testing.assert_allclose(features[0],features[1],atol=1e-5)
    class Constant(torch.nn.Module):
        def forward(self,x):
            return torch.tensor([1.,0.]).repeat(len(x),1)
    times,v,p,length=infer(Constant(),ts,features[0])
    assert abs(times[0]-ts[0]-1)<1e-6
    assert abs(length-2)<1e-6 and abs(p[-1,0]-2)<1e-6
    torch.set_num_threads(2)
    model=load_model(ROOT/'indoor/data/models/ronin/ronin_resnet/checkpoint_gsn_latest.pt')
    times,v,p,length=infer(model,ts,features[0])
    assert np.isfinite(v).all() and v.shape[1]==2
print('PASS quaternion/global features, units/order, warmup/velocity integration, strict real-checkpoint inference')
