"""Unique simultaneous box association across detectors, never by unrelated track IDs."""
from counter import iou
from person_anchor import ankle_point

def associated_keypoints(raw_pairs,pose_boxes,pose_keypoints,min_iou=.55,margin=.1):
    if not 0<min_iou<=1 or not 0<=margin<=1:raise ValueError('Invalid pose association thresholds')
    if len(pose_boxes)!=len(pose_keypoints):raise ValueError('Pose box/keypoint lengths differ')
    votes=[]
    for tid,box in raw_pairs:
        scores=sorted([(iou(box,p),i) for i,p in enumerate(pose_boxes)],reverse=True)
        if not scores or scores[0][0]<min_iou:continue
        if len(scores)>1 and scores[0][0]-scores[1][0]<margin:continue
        score,index=scores[0];votes.append((tid,index,score))
    matches={};proof=[]
    for tid,index,score in votes:
        if sum(other==index for _,other,_ in votes)!=1:continue
        matches[tid]=pose_keypoints[index]
        proof.append(dict(raw_track_id=tid,pose_index=index,iou=score))
    return matches,proof
