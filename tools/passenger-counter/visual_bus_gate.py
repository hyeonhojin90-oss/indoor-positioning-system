"""Bounded visual continuity of a previously strongly detected vehicle."""
import cv2
import numpy as np


class BusVisualFallback:
    def __init__(self,max_gap=2,min_points=24,min_inlier_ratio=.7,min_span=.3):
        if max_gap<=0 or min_points<8 or not 0<min_inlier_ratio<=1 or not 0<min_span<=1:
            raise ValueError('Invalid visual fallback settings')
        self.max_gap,self.min_points,self.min_inlier_ratio,self.min_span=max_gap,min_points,min_inlier_ratio,min_span
        self.reset()

    def reset(self):
        self.gray=self.points=self.box=None;self.last_strong=float('-inf')

    def update(self,frame,strong_boxes,now,people=()):
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY);height,width=gray.shape
        if strong_boxes:
            box=max(strong_boxes,key=lambda b:(b[2]-b[0])*(b[3]-b[1]))
            mask=np.zeros_like(gray)
            x1,y1,x2,y2=[round(v) for v in box]
            mask[max(0,y1):min(height,y2),max(0,x1):min(width,x2)]=255
            for p in people:
                a,b,c,d=[round(v) for v in p]
                mask[max(0,b):min(height,d),max(0,a):min(width,c)]=0
            points=cv2.goodFeaturesToTrack(gray,160,.01,7,mask=mask)
            self.gray,self.points,self.box=gray,points,list(box);self.last_strong=now
            return None  # detector is already sufficient in this frame
        if self.points is None or self.box is None or not 0<=now-self.last_strong<=self.max_gap:
            self.reset();return None
        target,status,error=cv2.calcOpticalFlowPyrLK(self.gray,gray,self.points,None,
            winSize=(21,21),maxLevel=3)
        if target is None or status is None:
            self.reset();return None
        good=(status.reshape(-1)==1)&(error.reshape(-1)<20)
        old=self.points.reshape(-1,2)[good];new=target.reshape(-1,2)[good]
        if len(new)<self.min_points:
            self.reset();return None
        transform,inliers=cv2.estimateAffinePartial2D(old,new,method=cv2.RANSAC,ransacReprojThreshold=2)
        if transform is None or inliers is None or float(inliers.mean())<self.min_inlier_ratio:
            self.reset();return None
        keep=inliers.reshape(-1).astype(bool);new=new[keep]
        bw,bh=self.box[2]-self.box[0],self.box[3]-self.box[1]
        if len(new)<self.min_points or np.ptp(new[:,0])<bw*self.min_span or np.ptp(new[:,1])<bh*self.min_span:
            self.reset();return None
        scale=float(np.hypot(transform[0,0],transform[1,0]))
        if not .8<=scale<=1.2:
            self.reset();return None
        x1,y1,x2,y2=self.box
        corners=np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]],np.float32)
        warped=cv2.transform(corners[None],transform)[0]
        box=[max(0,float(warped[:,0].min())),max(0,float(warped[:,1].min())),
             min(width,float(warped[:,0].max())),min(height,float(warped[:,1].max()))]
        self.gray,self.points,self.box=gray,new.reshape(-1,1,2),box
        return box if box[2]>box[0] and box[3]>box[1] else None
