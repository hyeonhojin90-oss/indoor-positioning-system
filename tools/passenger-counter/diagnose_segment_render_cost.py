"""Measure box-only versus mask rendering on the same crowded frame results."""
import hashlib,json,os,time
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))

def main():
    import cv2,torch
    from ultralytics import YOLO
    from runtime_threads import configure_model_threads
    torch.set_num_threads(2)
    source=Path('data/people-walking.mp4');model=YOLO('models/yolo11s-seg.pt')
    configure_model_threads(model,2);cap=cv2.VideoCapture(str(source));rows=[]
    try:
        for fid in [0,30,60]:
            cap.set(cv2.CAP_PROP_POS_FRAMES,fid);ok,frame=cap.read();assert ok
            start=time.perf_counter();r=model.predict(frame,imgsz=640,classes=[0],conf=.25,device='cpu',verbose=False)[0]
            inference=time.perf_counter()-start
            times={}
            for enabled in [False,True,False,True]:
                start=time.perf_counter();display=r.plot(line_width=2,font_size=12,masks=enabled)
                times.setdefault(str(enabled),[]).append(time.perf_counter()-start)
            rows.append(dict(frame=fid,people=len(r.boxes),predict_s=inference,ultralytics_speed_ms=r.speed,
                             render_seconds=times,threads=torch.get_num_threads(),image_shape=list(frame.shape)))
    finally:cap.release()
    report=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),rows=rows,
                concurrent_jobs_running=True,controlled_speed_benchmark=False,jetson_validated=False,
                note='Same result rendered both ways; masks are not used for counting. First inference includes setup.')
    with Path('runs/segment-mask-render-cost-r2.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))

if __name__=='__main__':main()
