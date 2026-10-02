"""Recorded-source review with immutable provenance and exclusive saved snapshots."""
import hashlib
import json
import math
from pathlib import Path
import threading


def read_source_frame(source,index):
    """Check the decoder's logical position; fall back to counted sequential reads."""
    import cv2
    cap=cv2.VideoCapture(str(source))
    try:
        if not cap.isOpened():raise ValueError('Cannot open recorded source frame')
        if cap.set(cv2.CAP_PROP_POS_FRAMES,index):
            ok,image=cap.read();position=cap.get(cv2.CAP_PROP_POS_FRAMES)
            if ok and math.isfinite(position) and abs(position-(index+1))<1e-6:
                return image,'position_checked_seek'
    finally:cap.release()
    cap=cv2.VideoCapture(str(source))
    try:
        if not cap.isOpened():raise ValueError('Cannot reopen source for sequential frame read')
        for _ in range(index+1):
            ok,image=cap.read()
            if not ok:raise ValueError('Cannot sequentially decode requested frame')
        return image,'counted_sequential_decode'
    finally:cap.release()


class ReviewSession:
    def __init__(self,source,output):
        import cv2
        self.source=Path(source).resolve();self.output=Path(output)
        if not self.source.is_file():raise ValueError('Recorded local source required')
        digest=hashlib.sha256(self.source.read_bytes()).hexdigest()
        cap=cv2.VideoCapture(str(self.source));frames=0
        try:
            if not cap.isOpened():raise ValueError('Cannot open recorded source')
            fps=cap.get(cv2.CAP_PROP_FPS)
            if not math.isfinite(fps) or fps<=0:raise ValueError('Source FPS unavailable')
            width,height=int(cap.get(3)),int(cap.get(4))
            while True:
                ok,frame=cap.read()
                if not ok:break
                if frame.shape[:2]!=(height,width):raise ValueError('Frame dimensions changed')
                frames+=1
        finally:cap.release()
        if not frames or hashlib.sha256(self.source.read_bytes()).hexdigest()!=digest:
            raise ValueError('Empty or changed source')
        self.manifest=dict(source=str(self.source),source_sha256=digest,frames=frames,
            fps=fps,width=width,height=height,all_source_frames_decoded=True,
            detector_overlays_used=False,independent_accuracy_validated=False)
        self.output.mkdir(parents=True,exist_ok=False)
        (self.output/'source-manifest.json').write_text(json.dumps(self.manifest,indent=2),encoding='utf-8')
        stat=self.source.stat();self.source_stat=(stat.st_size,stat.st_mtime_ns)
        self.lock=threading.Lock();self.seen=set();self.served={};self.snapshots=0

    def frame(self,index):
        import cv2
        if type(index) is not int or not 0<=index<self.manifest['frames']:
            raise ValueError('Frame outside source')
        with self.lock:
            stat=self.source.stat()
            if (stat.st_size,stat.st_mtime_ns)!=self.source_stat:raise ValueError('Source changed since review began')
            image,mode=read_source_frame(self.source,index)
            if image.shape[:2]!=(self.manifest['height'],self.manifest['width']):raise ValueError('Reviewed frame dimensions changed')
            ok,jpeg=cv2.imencode('.jpg',image)
            if not ok:raise ValueError('Cannot encode source frame')
            data=jpeg.tobytes();self.seen.add(index)
            self.served[index]=dict(decoder_mode=mode,jpeg_sha256=hashlib.sha256(data).hexdigest())
            return data

    def save(self,payload):
        if not isinstance(payload,dict) or payload.get('source_sha256')!=self.manifest['source_sha256']:
            raise ValueError('Review/source mismatch')
        reviewer=payload.get('reviewer');actor=payload.get('reviewer_kind')
        if not isinstance(reviewer,str) or not reviewer.strip() or actor not in ('human','assistant'):
            raise ValueError('Reviewer identity and kind required')
        events=payload.get('events')
        if not isinstance(events,list):raise ValueError('Event list required')
        clean=[];keys=set()
        for event in events:
            if not isinstance(event,dict):raise ValueError('Invalid event')
            person,direction=event.get('person'),event.get('direction')
            start,end=event.get('start_frame'),event.get('end_frame')
            if not isinstance(person,str) or not person.strip() or direction not in ('in','out'):
                raise ValueError('Person and direction required')
            if type(start) is not int or type(end) is not int or not 0<=start<=end<self.manifest['frames']:
                raise ValueError('Invalid source frame interval')
            key=(person.strip(),direction,start,end)
            if key in keys:raise ValueError('Duplicate passage interval')
            keys.add(key)
            clean.append(dict(passage_id=f'passage-{len(clean)+1:03d}',person=person.strip(),direction=direction,
                start_frame=start,end_frame=end,start_s=start/self.manifest['fps'],end_s=end/self.manifest['fps']))
        with self.lock:
            if hashlib.sha256(self.source.read_bytes()).hexdigest()!=self.manifest['source_sha256']:
                raise ValueError('Source changed since review began')
            self.snapshots+=1;name=f'windows-{self.snapshots:03d}.jsonl';path=self.output/name
            with path.open('x',encoding='utf-8') as stream:
                for event in clean:stream.write(json.dumps(event,ensure_ascii=False)+'\n')
            metadata=dict(**self.manifest,reviewer=reviewer.strip(),reviewer_kind=actor,
                human_reviewed=actor=='human',whole_ground_truth_complete=False,
                partial_review=True,actual_requested_frames=sorted(self.seen),
                served_frame_proof={str(k):v for k,v in sorted(self.served.items())},
                watched_all_frames_verified=False,events=len(clean),windows_file=name,
                windows_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                precision=None,annotation_before_model_inference_not_verified=True)
            (self.output/f'review-{self.snapshots:03d}.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False),encoding='utf-8')
            return dict(windows_file=name,events=len(clean),partial_review=True)
