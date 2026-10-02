"""Keep tracker identities but recover their current, pre-Kalman detections."""
import importlib.metadata

class MeasuredDetectionBoxes:
    def __init__(self,model):
        if importlib.metadata.version('ultralytics')!='8.3.228':
            raise ValueError('Measured box adapter is verified for Ultralytics8.3.228 only')
        if model.predictor is not None:raise ValueError('Attach before predictor/tracker initialization')
        self.snapshots=[]
        model.add_callback('on_predict_postprocess_end',self.capture)
    def capture(self,predictor):
        if len(predictor.results)!=1:raise ValueError('Measured box adapter requires one frame')
        r=predictor.results[0]
        if r.boxes.is_track:raise ValueError('Capture callback ran after tracking')
        self.snapshots=[dict(box=b,score=s,cls=c) for b,s,c in zip(r.boxes.xyxy.cpu().tolist(),r.boxes.conf.cpu().tolist(),r.boxes.cls.int().cpu().tolist())]
    def recover(self,result,tracker):
        if result.boxes.id is None:return [],[]
        ids=result.boxes.id.int().cpu().tolist()
        tracks={t.track_id:t for t in tracker.tracked_stracks if t.is_activated and t.frame_id==tracker.frame_id}
        boxes=[];proof=[];used=set()
        high=[i for i,r in enumerate(self.snapshots) if r['score']>=tracker.args.track_high_thresh]
        low=[i for i,r in enumerate(self.snapshots) if tracker.args.track_low_thresh<r['score']<tracker.args.track_high_thresh]
        for tid,cls,score in zip(ids,result.boxes.cls.int().cpu().tolist(),result.boxes.conf.cpu().tolist()):
            if tid not in tracks:raise ValueError('No current tracker observation for ID')
            local=int(tracks[tid].idx)
            # Installed8.3.228 initializes idx after splitting high/low detections.
            # It is a subset index, not the original pre-tracker detection index.
            subset=high if tracks[tid].score>=tracker.args.track_high_thresh else low
            if not 0<=local<len(subset):raise ValueError('Invalid tracker subset index')
            index=subset[local]
            if index in used or not 0<=index<len(self.snapshots):raise ValueError('Invalid/reused current detection index')
            used.add(index);row=self.snapshots[index]
            if row['cls']!=cls or abs(row['score']-score)>1e-5:raise ValueError('Current detection class/confidence differs')
            boxes.append(row['box']);proof.append(dict(track_id=tid,detection_index=index,tracker_subset_index=local,association_band='high' if subset is high else 'low'))
        return boxes,proof
