"""Frame cadence for recordings, with an elapsed-time deadline for live cameras."""
import math


def inference_due(frame,last_frame,interval,now,last_time,live,max_age):
    if type(interval) is not int or interval<1 or not math.isfinite(max_age) or max_age<=0:
        raise ValueError('Invalid inference cadence/deadline')
    return frame-last_frame>=interval or (live and now-last_time>=max_age)
