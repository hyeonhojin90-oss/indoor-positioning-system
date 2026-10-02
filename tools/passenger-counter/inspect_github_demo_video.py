import hashlib,json
from pathlib import Path
import cv2,numpy as np

def main():
    source=Path('data/public-github-bus-demo-20261001-r2.mp4')
    out=Path('runs/github-demo-source-inspection-r2');out.mkdir(exist_ok=False)
    cap=cv2.VideoCapture(str(source));n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
    assert n>0 and fps>0
    tiles=[];frames=sorted(set([0]+[round((n-1)*f) for f in [.15,.3,.45,.6,.75,.9,1]]))
    try:
        for fid in frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES,fid);ok,im=cap.read();assert ok
            scale=min(480/im.shape[1],480/im.shape[0]);small=cv2.resize(im,(round(im.shape[1]*scale),round(im.shape[0]*scale)))
            tile=np.zeros((510,480,3),np.uint8);tile[30:30+small.shape[0],:small.shape[1]]=small
            cv2.putText(tile,f'frame {fid}, {fid/fps:.2f}s',(8,22),0,.6,(255,255,255),1);tiles.append(tile)
        while len(tiles)%2:tiles.append(np.zeros_like(tiles[0]))
        canvas=np.vstack([np.hstack(tiles[i:i+2]) for i in range(0,len(tiles),2)])
        cv2.imencode('.jpg',canvas)[1].tofile(out/'source-contact.jpg')
        report=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),frames=n,fps=fps,
            width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            inspected_frames=frames,model_inference_performed=False,annotations_not_yet_written=True)
        (out/'inspection.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
    finally:cap.release()

if __name__=='__main__':main()
