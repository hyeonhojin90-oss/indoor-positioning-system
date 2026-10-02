"""Use measured, confident foot keypoints; missing feet are unknown, never guessed."""
import math

def validate_anchor_config(cfg):
    kind=cfg.get('person_anchor_kind','box')
    if kind not in ('box','pose_ankle','pose_dual'):raise ValueError('Unknown person anchor kind')
    opts=cfg.get('pose_anchor',{})
    if kind in ('pose_ankle','pose_dual'):
        if opts.get('foot_choice','leading') not in ('leading','trailing'):
            raise ValueError('Invalid measured foot selection')
        if not 0<opts.get('ankle_conf',.5)<=1 or opts.get('min_visible',2) not in (1,2):
            raise ValueError('Invalid ankle confidence/visibility requirement')
    return kind

def ankle_point(box,keypoints,conf=.5,min_visible=2,foot_choice='leading'):
    if foot_choice not in ('leading','trailing'):raise ValueError('Invalid measured foot selection')
    if keypoints is None or len(keypoints)!=17:return None
    x1,y1,x2,y2=box;h=y2-y1
    valid=[]
    for k in (15,16):
        values=keypoints[k]
        if len(values)!=3 or not all(math.isfinite(z) for z in values):continue
        x,y,score=values
        if score>=conf and x1<=x<=x2 and y1+.55*h<=y<=y2:
            valid.append((x,y))
    if len(valid)<min_visible:return None
    return (min if foot_choice=='leading' else max)(valid,key=lambda p:p[1])

def measured_points(pairs,raw_pairs,keypoints,cfg):
    kind=validate_anchor_config(cfg)
    if kind=='box':
        anchor=cfg.get('person_anchor_y',1.)
        return [((b[0]+b[2])/2,b[1]+anchor*(b[3]-b[1])) for _,b in pairs]
    opts=cfg.get('pose_anchor',{})
    points=[]
    for tid,b in pairs:
        origins=[raw for raw,box in raw_pairs if box==b]
        poses=keypoints.get(origins[0]) if len(origins)==1 else None
        points.append(ankle_point(b,poses,opts.get('ankle_conf',.5),opts.get('min_visible',2),opts.get('foot_choice','leading')))
    return points

def row_points(row,cfg):
    kind=validate_anchor_config(cfg)
    if kind=='box':
        # Geometry/box-anchor replay may deliberately change anchor_y. Do not
        # let an old diagnostic point silently override the requested profile.
        return measured_points(list(zip(row['ids'],row['boxes'])),[],{},cfg)
    if 'points' not in row:
        raise ValueError('Pose experiment requires measured points in saved trace')
    if len(row['points'])!=len(row['ids']):raise ValueError('Point/ID lengths differ')
    for point in row['points']:
        if point is not None and (len(point)!=2 or not all(math.isfinite(z) for z in point)):
            raise ValueError('Invalid measured point')
    return row['points']
