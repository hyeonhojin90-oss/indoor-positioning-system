"""File frame time versus observed host read time for live cameras/streams."""
import math
from pathlib import Path
import time


def source_kind(source, requested='auto'):
    if requested not in ('auto','file','live'):
        raise ValueError('Invalid source kind')
    if requested != 'auto':
        if requested == 'file' and isinstance(source,int):
            raise ValueError('A numeric camera is not a file')
        return requested
    if isinstance(source,int):
        return 'live'
    try:
        return 'file' if Path(source).is_file() else 'live'
    except OSError:
        return 'live'


class SourceClock:
    def __init__(self,source,fps,started,requested='auto',clock=time.perf_counter):
        if not math.isfinite(fps) or fps<=0 or not math.isfinite(started):
            raise ValueError('Invalid source clock')
        self.kind=source_kind(source,requested)
        self.fps,self.started,self.clock=fps,started,clock
        self.last_frame=-1;self.last_time=-1.

    def frame_time(self,frame):
        if type(frame) is not int or frame<=self.last_frame:
            raise ValueError('Frame sequence must advance')
        now=frame/self.fps if self.kind=='file' else self.clock()-self.started
        if not math.isfinite(now) or now<0 or now<self.last_time:
            raise ValueError('Invalid or regressed observation time')
        self.last_frame,self.last_time=frame,now
        return now

    def describe(self):
        return dict(source_kind=self.kind,time_base='file_frame_index_over_fps' if self.kind=='file'
                    else 'host_monotonic_after_frame_read',
                    camera_exposure_timestamp_verified=False,
                    camera_buffer_latency_verified=False,
                    annotated_video_constant_fps=self.fps,
                    live_video_playback_preserves_wall_time=False if self.kind=='live' else None)
