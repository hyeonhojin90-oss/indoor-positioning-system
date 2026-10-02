import json
from pathlib import Path
import cv2
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection


def main():
    path='IDEA-Research/grounding-dino-tiny'
    cache='models/hf'
    processor=AutoProcessor.from_pretrained(path,cache_dir=cache)
    model=AutoModelForZeroShotObjectDetection.from_pretrained(path,cache_dir=cache).eval()
    out=Path('runs/grounding-probe');out.mkdir(exist_ok=True)
    c=cv2.VideoCapture('data/bus-3132290.mp4'); results=[]
    for n in [0,10,30,40,60,90]:
        c.set(1,n);ok,frame=c.read()
        image=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
        inputs=processor(images=image,text='a bus door. a person.',return_tensors='pt')
        with torch.no_grad():outputs=model(**inputs)
        r=processor.post_process_grounded_object_detection(outputs,inputs.input_ids,threshold=.2,
                                                            text_threshold=.2,target_sizes=[image.size[::-1]])[0]
        labels=r.get('text_labels',r.get('labels'))
        detections=[{'box':b,'confidence':s,'label':l} for b,s,l in zip(r['boxes'].tolist(),r['scores'].tolist(),labels)]
        results.append({'frame':n,'detections':detections})
        for d in detections:
            b=list(map(int,d['box'])); cv2.rectangle(frame,b[:2],b[2:],(0,255,0),2)
            cv2.putText(frame,f"{d['label']} {d['confidence']:.2f}",b[:2],0,.7,(0,0,255),2)
        cv2.imwrite(str(out/f'frame-{n}.jpg'),frame)
        (out/'detections.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(n,detections,flush=True)
    c.release()


if __name__=='__main__':main()
