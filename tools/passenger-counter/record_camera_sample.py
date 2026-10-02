"""Bounded unannotated camera recording with host-read timestamps; no detector."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
from source_timing import source_kind


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(source,output,duration=0,max_frames=0,recording_fps=30.,allow_file_drill=False,
           backend='auto',clock=time.perf_counter):
    import cv2
    if type(max_frames) is not int or max_frames<0 or not math.isfinite(duration) or duration<0 or not (duration>0 or max_frames>0):
        raise ValueError('A positive duration or frame limit is required')
    if not math.isfinite(recording_fps) or recording_fps<=0:raise ValueError('Invalid recording FPS')
    if backend not in ('auto','gstreamer'):raise ValueError('Unknown capture backend')
    kind=source_kind(source)
    if kind=='file' and not allow_file_drill:raise ValueError('Local file requires explicit file-drill mode')
    if kind!='file' and allow_file_drill:raise ValueError('File drill requires an existing local file')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    manifest=dict(source=str(source),source_kind=kind,file_drill=kind=='file',
                  camera_connection_validated=False,host_read_time_base='perf_counter_after_read',
                  camera_exposure_timestamp_verified=False,camera_buffer_latency_verified=False,
                  image_transform='none',detector_overlays_used=False,audio_recorded=False,
                  whole_camera_session_complete=False,jetson_validated=False,phase='starting',frames=0)
    path=output/'capture.json'
    def save():path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    save();cap=None;writer=None;stopped='unknown';count=0
    try:
        if kind=='file':manifest['drill_source_sha256_before']=sha(source)
        cap=cv2.VideoCapture(source,cv2.CAP_GSTREAMER) if backend=='gstreamer' else cv2.VideoCapture(source)
        if not cap.isOpened():raise ValueError('Cannot open capture source')
        manifest.update(phase='recording',capture_backend=cap.getBackendName(),
                        reported_source_fps=cap.get(cv2.CAP_PROP_FPS),recording_fps=recording_fps)
        save();started=clock();last=-1.;video=output/'sample.mp4';ledger=output/'read-times.jsonl'
        with ledger.open('x',encoding='utf-8') as stream:
            while True:
                if max_frames and count>=max_frames:stopped='requested_frame_limit';break
                if duration and clock()-started>=duration:stopped='requested_duration';break
                ok,image=cap.read();observed=clock()-started
                if not ok:
                    if kind=='file':stopped='file_drill_end_of_file';break
                    raise ValueError('Live capture read failed; complete sample is not established')
                if not math.isfinite(observed) or observed<0 or observed<last:raise ValueError('Capture clock regressed')
                height,width=image.shape[:2]
                if writer is None:
                    manifest.update(width=width,height=height)
                    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),recording_fps,(width,height))
                    if not writer.isOpened():raise ValueError('Cannot open recording writer')
                elif (width,height)!=(manifest['width'],manifest['height']):raise ValueError('Capture dimensions changed')
                writer.write(image)
                stream.write(json.dumps(dict(frame=count,host_read_time_s=observed))+'\n');stream.flush()
                count+=1;last=observed
        if count==0:raise ValueError('No frames recorded')
        manifest.update(phase='recorded',stop_reason=stopped,frames=count,
                        camera_connection_validated=kind=='live')
    except BaseException as error:
        manifest.update(phase='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',
                        frames=count,error=f'{type(error).__name__}: {error}',camera_connection_validated=False)
        raise
    finally:
        if cap is not None:cap.release()
        if writer is not None:writer.release()
        for name in ('sample.mp4','read-times.jsonl'):
            artifact=output/name
            if artifact.is_file():manifest[name.replace('.','_')+'_sha256']=sha(artifact)
        if kind=='file' and 'drill_source_sha256_before' in manifest:
            manifest['drill_source_unchanged']=sha(source)==manifest['drill_source_sha256_before']
            if not manifest['drill_source_unchanged']:
                manifest.update(phase='failed',error='File drill source changed')
        save()
    if manifest['phase']!='recorded':raise ValueError(manifest.get('error','Recording failed'))
    return manifest


def verify(output):
    import cv2
    output=Path(output);manifest=json.loads((output/'capture.json').read_text(encoding='utf-8'))
    if manifest['phase']!='recorded':raise ValueError('Recording did not complete its requested sample')
    for name in ('sample.mp4','read-times.jsonl'):
        if sha(output/name)!=manifest[name.replace('.','_')+'_sha256']:raise ValueError('Capture artifact hash mismatch')
    if manifest['file_drill'] and not manifest.get('drill_source_unchanged'):raise ValueError('File drill source changed')
    times=[json.loads(line) for line in (output/'read-times.jsonl').read_text(encoding='utf-8').splitlines()]
    if len(times)!=manifest['frames'] or any(row['frame']!=i for i,row in enumerate(times)):raise ValueError('Incomplete read-time ledger')
    values=[row['host_read_time_s'] for row in times]
    if any(isinstance(t,bool) or not isinstance(t,(int,float)) or not math.isfinite(t) or t<0 for t in values) or any(b<a for a,b in zip(values,values[1:])):
        raise ValueError('Invalid host read clock')
    cap=cv2.VideoCapture(str(output/'sample.mp4'));decoded=0
    try:
        if not cap.isOpened():raise ValueError('Cannot decode recorded sample')
        while True:
            ok,image=cap.read()
            if not ok:break
            if image.shape[:2]!=(manifest['height'],manifest['width']):raise ValueError('Recorded dimensions differ')
            decoded+=1
    finally:cap.release()
    if decoded!=len(times):raise ValueError('Recorded frames and host timestamps differ')
    return dict(sample_integrity_verified=True,frames=decoded,file_drill=manifest['file_drill'],
                camera_connection_validated=manifest['camera_connection_validated'],
                camera_exposure_timestamp_verified=False,camera_buffer_latency_verified=False,
                full_camera_session_verified=False,boarding_accuracy_validated=False,jetson_validated=False,
                constant_fps_playback_preserves_live_wall_time=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--duration',type=float,default=0)
    parser.add_argument('--max-frames',type=int,default=0);parser.add_argument('--recording-fps',type=float,default=30.)
    parser.add_argument('--allow-file-drill',action='store_true');parser.add_argument('--backend',choices=['auto','gstreamer'],default='auto')
    args=parser.parse_args();source=int(args.source) if args.source.isdecimal() else args.source
    record(source,args.output,args.duration,args.max_frames,args.recording_fps,args.allow_file_drill,args.backend)
    report=verify(args.output)
    with (args.output/'capture-audit.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(report))
