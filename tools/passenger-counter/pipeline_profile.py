"""Optional serial pipeline wall timings; separate startup and steady sample distributions."""
import json,math,time
from statistics import median

STAGES=('read','person','bus_door','pose','tracking_count','render_video','diagnostic_output')

def distribution(values):
    if not values:return None
    ordered=sorted(values)
    return dict(samples=len(values),median_ms=median(ordered),p95_ms=ordered[min(len(ordered)-1,math.ceil(.95*len(ordered))-1)],max_ms=ordered[-1])

class PipelineProfile:
    def __init__(self,path,synchronize=None,clock=time.perf_counter,warmup_frames=5):
        self.file=path.open('x',encoding='utf-8');self.synchronize=synchronize;self.clock=clock
        self.warmup_frames=warmup_frames;self.samples=[];self.current=None
    def begin(self,frame):
        if self.current is not None or frame!=len(self.samples):raise ValueError('Sequential completed profiling frames required')
        if self.synchronize:self.synchronize()
        self.start=self.last=self.clock();self.current=dict(frame=frame,stages_ms={})
    def mark(self,stage):
        if self.current is None or stage!=STAGES[len(self.current['stages_ms'])]:raise ValueError('Unexpected profiling stage')
        if self.synchronize:self.synchronize()
        now=self.clock();duration=(now-self.last)*1000
        if duration<0 or not math.isfinite(duration):raise ValueError('Invalid monotonic timing')
        self.current['stages_ms'][stage]=duration;self.last=now
    def finish(self):
        if self.current is None or tuple(self.current['stages_ms'])!=STAGES:raise ValueError('Incomplete profiling frame')
        self.current['total_ms']=(self.last-self.start)*1000
        self.file.write(json.dumps(self.current)+'\n');self.file.flush();self.samples.append(self.current);self.current=None
    def close(self):
        # A begin followed by EOF is not a completed source frame.
        self.current=None;self.file.close()
    def summary(self):
        steady=self.samples[self.warmup_frames:]
        return dict(frames=len(self.samples),warmup_frames_excluded=min(self.warmup_frames,len(self.samples)),
            startup_total=distribution([r['total_ms'] for r in self.samples[:self.warmup_frames]]),
            steady_total=distribution([r['total_ms'] for r in steady]),
            steady_stages={stage:distribution([r['stages_ms'][stage] for r in steady]) for stage in STAGES},
            cuda_synchronization_between_stages=self.synchronize is not None,
            camera_capture_to_display_latency_validated=False,gpu_operation_profile_verified=False,
            sustained_thermal_performance_validated=False,
            note='Serial wall timings include file/camera read, inference, tracking/counting, rendering and output. Stage synchronization changes scheduling. File replay is not sensor capture latency; CPU contention/thermal conditions must be recorded separately.')
