"""Read-only device/runtime inventory; does not install packages or change power mode."""
import argparse,importlib.metadata,json,platform,shutil,subprocess
from pathlib import Path

def collect():
    report=dict(platform=platform.system(),machine=platform.machine(),python=platform.python_version(),
                jetson_detected=False,cuda_available=False,packages={},commands={},environment_ready=False)
    for path,key in [('/proc/device-tree/model','device_model'),('/etc/nv_tegra_release','tegra_release')]:
        p=Path(path)
        if p.is_file():report[key]=p.read_text(errors='replace').strip('\0\n')
    report['jetson_detected']='jetson' in report.get('device_model','').lower() or 'tegra_release' in report
    for name in ['torch','torchvision','ultralytics','onnx','onnxruntime','onnxruntime-gpu','tensorrt','opencv-python','numpy']:
        try:report['packages'][name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:pass
    try:
        import torch
        report['torch_cuda_version']=torch.version.cuda;report['cuda_available']=torch.cuda.is_available()
        if report['cuda_available']:
            p=torch.cuda.get_device_properties(0)
            report['gpu']=dict(name=p.name,total_memory_bytes=p.total_memory,compute_capability=[p.major,p.minor])
    except Exception as e:report['torch_error']=f'{type(e).__name__}: {e}'
    try:
        import tensorrt
        report['tensorrt_import_version']=tensorrt.__version__
    except Exception as e:report['tensorrt_error']=f'{type(e).__name__}: {e}'
    try:
        import onnxruntime as ort
        report['onnxruntime_available_providers']=ort.get_available_providers()
    except Exception as e:report['onnxruntime_error']=f'{type(e).__name__}: {e}'
    if platform.system()=='Linux':
        for name,args in [('nvcc',['nvcc','--version']),('jetpack',['dpkg-query','-W','nvidia-jetpack']),('power_mode',['nvpmodel','-q'])]:
            if shutil.which(args[0]):
                try:
                    r=subprocess.run(args,capture_output=True,text=True,timeout=10)
                    report['commands'][name]=dict(returncode=r.returncode,stdout=r.stdout[:4000],stderr=r.stderr[:1000])
                except Exception as e:report['commands'][name]={'error':str(e)}
    report['environment_ready']=report['jetson_detected'] and report['cuda_available'] and bool(report.get('tensorrt_import_version'))
    report['onnx_cuda_provider_available']='CUDAExecutionProvider' in report.get('onnxruntime_available_providers',[])
    report['environment_ready_scope']='Jetson plus CUDA torch and TensorRT imports; ONNX GPU readiness is separate'
    report['counter_validated']=False;report['tensorrt_engine_validated']=False
    report['note']='Environment inventory only; readiness is not inference/accuracy/latency proof. No privileged command, package download, install, power-mode mutation or device flash.'
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=collect()
    with a.output.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
