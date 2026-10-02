"""Adapt YOLOv5 objectness output to the installed YOLO detector interface.

No source code from the model distributor is executed. This adds only tensor
layout/score operations; the downloaded network stays unchanged. Raw tensor
parity against NumPy is required before use, including positive predictions.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parent/'runs'/'settings'))

def adapt(source,output):
    import onnx
    from onnx import helper,TensorProto
    model=onnx.load(source)
    metadata={p.key:p.value for p in model.metadata_props}
    if ast.literal_eval(metadata.get('names','{}'))!={0:'person',1:'head'}:
        raise ValueError('Unverified CrowdHuman class order')
    if len(model.graph.output)!=1:raise ValueError('Expected one raw output')
    original=model.graph.output[0].name
    prefix='passenger_adapter_'
    def integer(name,values):
        model.graph.initializer.append(helper.make_tensor(prefix+name,TensorProto.INT64,[len(values)],values))
        return prefix+name
    axes=integer('axis',[2]);steps=integer('step',[1])
    names=[]
    for name,start,end in [('xywh',0,4),('objectness',4,5),('classes',5,7)]:
        node=prefix+name;names.append(node)
        model.graph.node.append(helper.make_node('Slice',[original,integer(name+'_start',[start]),integer(name+'_end',[end]),axes,steps],[node]))
    model.graph.node.extend([
        helper.make_node('Mul',[names[1],names[2]],[prefix+'scores']),
        helper.make_node('Concat',[names[0],prefix+'scores'],[prefix+'rows'],axis=2),
        helper.make_node('Transpose',[prefix+'rows'],[prefix+'predictions'],perm=[0,2,1])])
    del model.graph.output[:]
    model.graph.output.append(helper.make_tensor_value_info(prefix+'predictions',TensorProto.FLOAT,['batch',6,'anchors']))
    helper.set_model_props(model,{**metadata,'task':'detect','batch':'1','imgsz':'[640, 640]',
                                  'description':'CrowdHuman person/head experimental adapter; objectness multiplied into classes'})
    onnx.checker.check_model(model);onnx.save(model,output)

def verify(source,output,video,frames):
    import cv2
    import numpy as np
    import onnxruntime as ort
    from ultralytics.data.augment import LetterBox
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    sessions=[ort.InferenceSession(str(p),options,providers=['CPUExecutionProvider']) for p in (source,output)]
    cap=cv2.VideoCapture(str(video));proof=[]
    try:
        for frame_id in frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES,frame_id);ok,im=cap.read()
            if not ok:raise ValueError('Cannot read verification frame')
            padded=LetterBox(new_shape=(640,640),auto=True,stride=32)(image=im)
            x=np.ascontiguousarray(padded[:,:,::-1].transpose(2,0,1)[None],dtype=np.float32)/255
            raw=sessions[0].run(None,{sessions[0].get_inputs()[0].name:x})[0]
            actual=sessions[1].run(None,{sessions[1].get_inputs()[0].name:x})[0]
            if raw.ndim!=3 or raw.shape[2]!=7:raise ValueError('Expected xywh,objectness,2 classes')
            expected=np.concatenate([raw[:,:,:4],raw[:,:,4:5]*raw[:,:,5:7]],axis=2).transpose(0,2,1)
            error=float(np.max(np.abs(expected-actual)))
            positive=int((actual[:,4:,:].max(axis=1)>.1).sum())
            if not np.allclose(expected,actual,atol=1e-5,rtol=1e-5):raise ValueError('Adapter changed raw predictions')
            proof.append(dict(frame=frame_id,max_abs_error=error,positive_anchors=positive,input_shape=list(x.shape)))
    finally:cap.release()
    if not sum(v['positive_anchors'] for v in proof):raise ValueError('Vacuous comparison')
    return proof

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--frames',type=int,nargs='+',required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);dest=a.output/'model.onnx';adapt(a.model,dest)
    proof=verify(a.model,dest,a.source,a.frames)
    hashes={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in [('original',a.model),('adapted',dest),('source',a.source)]}
    result=dict(passed=True,hashes=hashes,frames=proof,accuracy_validated=False,jetson_validated=False,
                upstream='https://github.com/yakhyo/yolov5-crowdhuman-onnx',
                note='Raw score/layout parity only; not a counting or speed validation. Deployment licensing needs separate confirmation.')
    (a.output/'adapter-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
