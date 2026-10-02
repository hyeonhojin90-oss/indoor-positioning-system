"""Experimental full-body observation recovery from uniquely matched same-frame pose."""
from counter import iou
from track_bridge import nested_head_match

def recover_observations(pairs,pose_boxes,keypoints,min_iou=.55,margin=.1):
    if len(pose_boxes)!=len(keypoints):raise ValueError('Pose observation lengths differ')
    candidates=[]
    for tid,box in pairs:
        scores=[]
        for j,p in enumerate(pose_boxes):
            overlap=iou(box,p);partial=nested_head_match(p,box)
            if overlap>=min_iou or partial:scores.append((max(overlap,.9 if partial else 0),j,partial))
        scores.sort(reverse=True)
        if not scores:continue
        if len(scores)>1 and scores[0][0]-scores[1][0]<margin:continue
        score,j,partial=scores[0];candidates.append((tid,j,partial,score))
    matches={};proof=[]
    for tid,j,partial,score in candidates:
        if sum(k==j for _,k,_,_ in candidates)!=1:continue
        matches[tid]=(pose_boxes[j],keypoints[j],partial)
        proof.append(dict(raw_track_id=tid,pose_index=j,partial_recovery=partial,association_score=score))
    output=[];poses={}
    for tid,box in pairs:
        if tid in matches:
            p,k,partial=matches[tid];poses[tid]=k;box=p if partial else box
        output.append((tid,box))
    return output,poses,proof
