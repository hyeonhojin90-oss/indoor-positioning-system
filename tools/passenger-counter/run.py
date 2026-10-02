"""Offline video / USB camera prototype. No manual fallback in automatic mode."""
import argparse
import hashlib
import json
import os
import math
from pathlib import Path
import time
from counter import DoorLock, PassageCounter, iou, plausible_door
from tracking_profile import resolve_tracker
from runtime_threads import configure_model_threads, backend_runtime_info
from door_selection import select_door, passenger_search_regions,locked_search_region
from geometry_visibility import boundary_visibility
from inference_schedule import inference_due
from person_anchor import validate_anchor_config,measured_points
from multi_anchor_counter import DualAnchorCounter
from associate_pose import associated_keypoints
from pose_activation import pose_due
from lost_reid_guard import install as install_lost_reid_guard
from door_occlusion_guard import contained_shrink
from confidence_door_selection import select_confident_door
from source_timing import SourceClock


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True, help='Local video path, numeric camera, RTSP URL or capture pipeline')
    p.add_argument('--source-kind',choices=['auto','file','live'],default='auto')
    p.add_argument('--config', required=True)
    p.add_argument('--output', required=True, help='New output directory (refuses overwrite)')
    p.add_argument('--device', default='cpu')
    p.add_argument('--max-frames', type=int, default=0)
    args = p.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    if type(cfg.get('profile_pipeline',False)) is not bool:raise ValueError('profile_pipeline must be boolean')
    if type(cfg.get('person_measured_boxes',False)) is not bool:
        raise ValueError('person_measured_boxes must be boolean')
    if cfg.get('person_measured_boxes',False):
        if cfg.get('person_task') not in ('detect','segment'):
            raise ValueError('Measured-box candidate requires explicit detect/segment task')
        if cfg.get('person_anchor_kind') in ('pose_dual','pose_ankle') and not cfg.get('pose_aux_model'):
            raise ValueError('Measured-box pose requires separate current-frame pose inference')
        if cfg.get('bus_gate',{}).get('enabled') and not cfg.get('bus_model'):
            raise ValueError('Measured person boxes require separate bus detector when bus gate is enabled')
    if type(cfg.get('partial_door_guard',False)) is not bool:
        raise ValueError('partial_door_guard must be boolean')
    if type(cfg.get('partial_door_fast_retry',False)) is not bool:
        raise ValueError('partial_door_fast_retry must be boolean')
    if cfg.get('partial_door_fast_retry') and not cfg.get('partial_door_guard'):
        raise ValueError('Partial-door fast retry requires the partial guard')
    confidence_selection=cfg.get('door_selection_confidence',False)
    if type(confidence_selection) is not bool:raise ValueError('door_selection_confidence must be boolean')
    if confidence_selection and (cfg.get('door_mode')!='custom' or not cfg.get('door_selection',{}).get('enabled')):
        raise ValueError('Confidence door selection requires custom detector and enabled passenger selection')
    anchor_kind=validate_anchor_config(cfg)
    from appearance_runtime import validate as validate_appearance
    validate_appearance(cfg.get('appearance_bridge',{}))
    person_task=cfg.get('person_task')
    if person_task is not None and person_task not in ('detect','pose','segment'):
        raise ValueError('person_task must be detect, pose or segment')
    person_class=cfg.get('person_class_id',0)
    if type(person_class) is not int or person_class<0 or person_class==5:
        raise ValueError('Invalid person_class_id or collision with bus class')
    if person_class!=0 and cfg.get('bus_gate',{}).get('enabled') and not cfg.get('bus_model'):
        raise ValueError('Non-COCO person class requires a separate bus model')
    implementation_hashes={name:hashlib.sha256((Path(__file__).resolve().parent/name).read_bytes()).hexdigest()
                           for name in ('run.py','counter.py','cascade_detector.py','grounding_detector.py',
                                        'door_selection.py','track_bridge.py','bus_gate.py','tracking_profile.py',
                                        'runtime_threads.py','visual_bus_gate.py','geometry_visibility.py','inference_schedule.py','person_anchor.py','multi_anchor_counter.py','associate_pose.py','pose_activation.py','lost_reid_guard.py','door_occlusion_guard.py','exit_evidence_guard.py','confidence_door_selection.py','source_timing.py','appearance_runtime.py')}
    tracker = cfg.get('person_tracker', 'bytetrack.yaml')
    if tracker not in ('bytetrack.yaml', 'botsort.yaml'):
        raise ValueError('Unsupported person_tracker')
    person_imgsz = cfg.get('person_imgsz', cfg.get('imgsz',640))
    if not isinstance(person_imgsz,int) or person_imgsz < 32:
        raise ValueError('person_imgsz must be an integer of at least 32')
    for name in ('person_rect','door_rect'):
        if name in cfg and type(cfg[name]) is not bool:
            raise ValueError(f'{name} must be boolean')
    mode = cfg['door_mode']
    if mode not in ('manual', 'world', 'custom', 'grounding', 'cascade'):
        raise ValueError('Unsupported door_mode')
    acquisition_config=cfg.get('door_acquisition_fallback')
    acquisition_size=None
    if acquisition_config is not None:
        from door_acquisition_fallback import validate,fallback_due
        acquisition_size=validate(acquisition_config)
        if mode!='custom' or not cfg.get('bus_gate',{}).get('enabled') or not cfg.get('door_selection',{}).get('enabled'):
            raise ValueError('Acquisition fallback requires custom detector, bus gate and passenger selection')
        if cfg.get('door_fallback_sizes'):
            raise ValueError('Acquisition fallback comparison cannot also vary primary fallback sizes')
        implementation_hashes['door_acquisition_fallback.py']=hashlib.sha256(Path('door_acquisition_fallback.py').read_bytes()).hexdigest()
    import cv2
    if 'cpu_threads' in cfg:
        if type(cfg['cpu_threads']) is not int or not 1<=cfg['cpu_threads']<=32:
            raise ValueError('cpu_threads must be 1..32')
        import torch
        torch.set_num_threads(cfg['cpu_threads'])
    os.environ.setdefault('YOLO_CONFIG_DIR', str(Path(__file__).resolve().parent/'runs'/'settings'))
    from ultralytics import YOLO, YOLOWorld
    import ultralytics
    install_lost_reid_guard(cfg)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    tracker = resolve_tracker(tracker,cfg.get('person_tracker_options'),out)
    if cfg.get('person_family','yolo')!='yolo':
        from person_model_family import load as load_person_family
        people=load_person_family(cfg)
        implementation_hashes['person_model_family.py']=hashlib.sha256(Path('person_model_family.py').read_bytes()).hexdigest()
        if 'person_rtdetr_nms_iou' in cfg:
            implementation_hashes['rtdetr_duplicate_filter.py']=hashlib.sha256(Path('rtdetr_duplicate_filter.py').read_bytes()).hexdigest()
    else:people = YOLO(cfg.get('person_model', 'yolo11n.pt'),task=person_task)
    configure_model_threads(people,cfg.get('cpu_threads'))
    measured_box_adapter=None
    if cfg.get('person_measured_boxes',False):
        from measured_detection_boxes import MeasuredDetectionBoxes
        measured_box_adapter=MeasuredDetectionBoxes(people)
        implementation_hashes['measured_detection_boxes.py']=hashlib.sha256(Path('measured_detection_boxes.py').read_bytes()).hexdigest()
    pose_aux=None;pose_aux_calls=0;partial_door_retry=False
    if cfg.get('pose_aux_model'):
        if anchor_kind!='pose_dual':raise ValueError('Auxiliary pose requires dual-anchor counting')
        pose_aux=YOLO(cfg['pose_aux_model'],task='pose')
        configure_model_threads(pose_aux,cfg.get('cpu_threads'))
        if cfg.get('pose_aux_gate') and (cfg['counting']['axis']!='y' or cfg['counting']['entry']!='negative'):
            raise ValueError('Pose approach activation requires negative-y entry')
        pose_due(None,[],cfg.get('pose_aux_gate'))
    detector = None
    if mode in ('grounding', 'cascade'):
        from grounding_detector import GroundingDoorDetector
        detector=GroundingDoorDetector(cfg.get('door_model','IDEA-Research/grounding-dino-tiny'),
                                      cfg.get('door_prompt','a bus door.'))
        if mode == 'cascade':
            from cascade_detector import CascadeDoorDetector
            detector = CascadeDoorDetector(YOLO(cfg['door_primary_model']), detector,
                                           max_area=cfg.get('max_door_area', .6),
                                           min_aspect=cfg.get('min_door_aspect', 0),
                                           **cfg.get('cascade', {}))
    if mode == 'world':
        detector = YOLOWorld(cfg.get('door_model', 'yolov8s-worldv2.pt'))
        detector.set_classes(cfg.get('door_prompts', ['door']))
    elif mode == 'custom':
        detector = YOLO(cfg['door_model'])
        if 'door_classes' not in cfg:
            raise ValueError('Custom detector requires explicit door_classes IDs')
    if detector is not None and hasattr(detector,'add_callback'):
        configure_model_threads(detector,cfg.get('cpu_threads'))
    elif mode=='cascade':
        configure_model_threads(detector.primary,cfg.get('cpu_threads'))
    acquisition_detector=None;acquisition_active=False;acquisition_calls=0;primary_door_calls=0
    if acquisition_config is not None:
        acquisition_detector=YOLO(acquisition_config['model'],task='detect')
        configure_model_threads(acquisition_detector,cfg.get('cpu_threads'))
    source = int(args.source) if args.source.isdecimal() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError('Cannot open source')
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    if not math.isfinite(fps) or fps <= 0:
        fps = 30
    width, height = int(cap.get(3)), int(cap.get(4))
    writer = cv2.VideoWriter(str(out/'annotated.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width,height))
    if not writer.isOpened():
        raise RuntimeError('Cannot create output video')
    dual=anchor_kind=='pose_dual'
    counter = DualAnchorCounter(cfg.get('counting',{}),cfg.get('person_anchor_y',1),**cfg.get('dual_anchor',{})) if dual else PassageCounter(**cfg.get('counting', {}))
    moving_lock=cfg.get('door_follow_observations',False)
    if type(moving_lock) is not bool:raise ValueError('door_follow_observations must be boolean')
    if moving_lock:
        from moving_door_lock import MovingDoorLock
        if mode!='custom':raise ValueError('Observed door following requires custom detector')
        implementation_hashes['moving_door_lock.py']=hashlib.sha256(Path('moving_door_lock.py').read_bytes()).hexdigest()
        lock=MovingDoorLock(**cfg.get('door_lock',{}))
    else:
        lock = DoorLock(**cfg.get('door_lock', {}))
    bridge=None
    appearance=None
    if cfg.get('appearance_bridge',{}).get('enabled',False):
        from appearance_runtime import create as create_appearance
        appearance=create_appearance(cfg['appearance_bridge'])
        for name in ['appearance_runtime.py','appearance_observation_bridge.py',
                     'osnet_onnx_features.py','osnet_preprocessing.py','temporal_nested_bridge.py','feature_cache_proof.py']:
            implementation_hashes[name]=hashlib.sha256(Path(name).read_bytes()).hexdigest()
    bridge_events=[]
    bridge_generation=None
    if cfg.get('track_bridge',{}).get('enabled',False):
        from track_bridge import NestedTrackBridge
        bridge=NestedTrackBridge(**{k:v for k,v in cfg['track_bridge'].items() if k!='enabled'})
    bus_gate = None
    if cfg.get('bus_gate', {}).get('enabled', False):
        from bus_gate import BusPresenceGate
        bus_gate = BusPresenceGate(**{k:v for k,v in cfg['bus_gate'].items() if k != 'enabled'})
    vehicle=None;vehicle_calls=0
    vehicle_interval=cfg.get('bus_detector',{}).get('interval_frames',5)
    if 'bus_model' in cfg:
        if bus_gate is None or type(vehicle_interval) is not int or vehicle_interval<1:
            raise ValueError('Separate bus model requires gate and positive interval')
        if vehicle_interval/fps>=bus_gate.grace_s:
            raise ValueError('Bus detector interval must be shorter than gate grace')
        vehicle=YOLO(cfg['bus_model'],task='detect')
        configure_model_threads(vehicle,cfg.get('cpu_threads'))
    visual_bus=None;visual_bus_frames=0
    if cfg.get('bus_visual_fallback',{}).get('enabled',False):
        if bus_gate is None:raise ValueError('Visual bus continuity requires bus gate')
        from visual_bus_gate import BusVisualFallback
        visual_bus=BusVisualFallback(**{k:v for k,v in cfg['bus_visual_fallback'].items() if k!='enabled'})
    interval = cfg.get('door_interval_frames', 10)
    if not isinstance(interval, int) or interval < 1:
        raise ValueError('door_interval_frames must be positive integer')
    locked_interval = cfg.get('door_locked_interval_frames', interval)
    if not isinstance(locked_interval, int) or locked_interval < 1 or locked_interval/fps >= lock.ttl:
        raise ValueError('Locked detection interval must be positive and shorter than door TTL')
    last_detection_frame = -max(interval, locked_interval)
    last_detection_time=float('-inf');last_vehicle_frame=-vehicle_interval;last_vehicle_time=float('-inf')
    detector_calls = 0
    bus_visible_frames, bus_gate_skipped_frames = 0, 0
    n, active, generation = 0, 0, 0
    last_search_frame=-100000
    started = time.perf_counter()
    source_clock = SourceClock(source,fps,started,requested=args.source_kind)
    profile=None
    if cfg.get('profile_pipeline',False):
        from pipeline_profile import PipelineProfile
        synchronizer=None
        if str(args.device) in ('0','cuda:0'):
            import torch
            if not torch.cuda.is_available():raise ValueError('GPU profiling requires CUDA')
            synchronizer=lambda:torch.cuda.synchronize(0)
        profile=PipelineProfile(out/'pipeline-times.jsonl',synchronize=synchronizer)
        implementation_hashes['pipeline_profile.py']=hashlib.sha256(Path('pipeline_profile.py').read_bytes()).hexdigest()
    events = []
    invisible_axis_frames=0
    with (out/'events.jsonl').open('w', encoding='utf-8') as ef, (out/'doors.jsonl').open('w', encoding='utf-8') as df, (out/'tracks.jsonl').open('w', encoding='utf-8') as tf:
        try:
            while not args.max_frames or n < args.max_frames:
                if profile:profile.begin(n)
                ok, frame = cap.read()
                if not ok:
                    break
                if profile:profile.mark('read')
                now = source_clock.frame_time(n)
                result = people.track(frame, persist=True, tracker=tracker,
                                      classes=[person_class,5] if bus_gate and vehicle is None else [person_class], conf=cfg.get('person_conf',.1),
                                      rect=cfg.get('person_rect',True),
                                      imgsz=person_imgsz, device=args.device, verbose=False)[0]
                all_boxes = result.boxes.xyxy.cpu().tolist()
                tracker_boxes=all_boxes;detection_box_proof=[]
                if measured_box_adapter is not None:
                    all_boxes,detection_box_proof=measured_box_adapter.recover(result,people.predictor.trackers[0])
                all_classes = result.boxes.cls.int().cpu().tolist()
                all_confidences = result.boxes.conf.cpu().tolist()
                all_ids = result.boxes.id.int().cpu().tolist() if result.boxes.id is not None else []
                person_pairs = [(tid,b) for tid,b,cls in zip(all_ids,all_boxes,all_classes) if cls == person_class]
                if profile:profile.mark('person')
                bus_boxes,bus_classes,bus_scores=all_boxes,all_classes,all_confidences
                if vehicle is not None:
                    bus_boxes,bus_classes,bus_scores=[],[],[]
                    if inference_due(n,last_vehicle_frame,vehicle_interval,now,last_vehicle_time,
                                     isinstance(source,int),max(bus_gate.grace_s*.5,.001)):
                        last_vehicle_frame=n;last_vehicle_time=now
                        vehicle_calls+=1
                        prediction=vehicle.predict(frame,classes=[5],device=args.device,
                            imgsz=cfg.get('bus_detector',{}).get('imgsz',640),
                            conf=cfg.get('bus_detector',{}).get('conf',.05),verbose=False)[0]
                        bus_boxes=prediction.boxes.xyxy.cpu().tolist()
                        bus_classes=prediction.boxes.cls.int().cpu().tolist()
                        bus_scores=prediction.boxes.conf.cpu().tolist()
                visual_box=None
                if visual_bus is not None:
                    strong=[b for b,c,s in zip(bus_boxes,bus_classes,bus_scores) if c==5
                            and s>=bus_gate.min_conf and (b[2]-b[0])*(b[3]-b[1])/(width*height)>=bus_gate.min_area]
                    visual_box=visual_bus.update(frame,strong,now,[b for _,b in person_pairs])
                bus_visible = (bus_gate.observe(bus_boxes,bus_classes,bus_scores,width,height,now,
                                               continuity_valid=visual_box is not None)
                               if bus_gate else True)
                bus_source=bus_gate.observation_kind if bus_gate else 'disabled'
                if visual_bus is not None:
                    if not bus_visible and visual_box is not None:
                        area=(visual_box[2]-visual_box[0])*(visual_box[3]-visual_box[1])/(width*height)
                        if area>=bus_gate.min_area:
                            bus_gate.boxes=[visual_box];bus_visible=True
                            bus_source='visual_continuity';visual_bus_frames+=1
                if bus_gate:
                    bus_visible_frames += int(bus_visible)
                if mode == 'manual':
                    r = cfg['manual_box']
                    if not (0 <= r[0] < r[2] <= 1 and 0 <= r[1] < r[3] <= 1):
                        raise ValueError('manual_box must be normalized valid xyxy')
                    box = (r[0]*width,r[1]*height,r[2]*width,r[3]*height)
                else:
                    if not bus_visible:
                        partial_door_retry=False
                        bus_gate_skipped_frames += 1
                        lock.reset()
                        if hasattr(detector, 'reset'):
                            detector.reset()
                        df.write(json.dumps({'frame':n,'time_s':now,'backend':'bus_gate',
                                             'bus_visible':False,'candidate':None,
                                             'locked':None,'generation':lock.generation})+'\n')
                    current_interval = locked_interval if lock.box is not None and not partial_door_retry else interval
                    if bus_visible and inference_due(n,last_detection_frame,current_interval,now,last_detection_time,
                                                     isinstance(source,int),lock.ttl*.5):
                        last_detection_frame = n
                        last_detection_time=now
                        detector_calls += 1
                        kwargs = {'classes': cfg['door_classes']} if mode == 'custom' else {}
                        if mode in ('custom','world') and 'door_rect' in cfg:
                            kwargs['rect']=cfg['door_rect']
                        if mode == 'cascade':
                            kwargs['locked_box'] = lock.valid_box(now)
                            if bus_gate:
                                kwargs['candidate_filter'] = bus_gate.accept_door
                                search_options=cfg.get('door_search',{})
                                valid=lock.valid_box(now)
                                if search_options.get('enabled',False):
                                    pending=lock.candidate if 0<=now-lock.last_seen<=lock.ttl else None
                                    search_box=valid or pending
                                    if search_box is not None:
                                        kwargs['search_regions']=locked_search_region(search_box,width,height)
                                    elif n-last_search_frame>=search_options.get('interval_frames',15):
                                        kwargs['search_regions']=passenger_search_regions(
                                            [b for _,b in person_pairs],bus_gate.boxes,width,height,
                                            search_options.get('max_regions',2))
                                        last_search_frame=n
                            if cfg.get('door_selection',{}).get('enabled',False):
                                selection_options={k:v for k,v in cfg['door_selection'].items() if k!='enabled'}
                                kwargs['candidate_selector'] = lambda boxes: select_door(
                                    boxes,[b for _,b in person_pairs],lock.valid_box(now),**selection_options)
                        if acquisition_detector is not None:
                            pending=lock.candidate if 0<=now-lock.last_seen<=lock.ttl else None
                            if lock.valid_box(now) is None and pending is None:acquisition_active=False
                        active_detector=acquisition_detector if acquisition_active else detector
                        active_size=acquisition_size if acquisition_active else cfg.get('imgsz',640)
                        if acquisition_active:acquisition_calls+=1
                        else:primary_door_calls+=1
                        pred = active_detector.predict(frame, imgsz=active_size, device=args.device,
                                                conf=cfg.get('door_conf',.25), verbose=False, **kwargs)[0]
                        accepted = cfg.get('door_classes', [0])
                        detections = [{'box':b,'class_id':c,'confidence':score} for b,c,score in zip(
                            pred.boxes.xyxy.cpu().tolist(),pred.boxes.cls.int().cpu().tolist(),pred.boxes.conf.cpu().tolist())]
                        candidates = [d['box'] for d in detections if d['class_id'] in accepted
                                      and plausible_door(d['box'], width, height, cfg.get('max_door_area',.6), cfg.get('min_door_aspect',0))
                                      and (not bus_gate or bus_gate.accept_door(d['box']))]
                        # Retry a larger input only when the primary scale has no
                        # accepted door. All coordinates remain original pixels.
                        used_size=active_size
                        for fallback_size in cfg.get('door_fallback_sizes',[]):
                            if candidates: break
                            pred=detector.predict(frame,imgsz=fallback_size,device=args.device,
                                                  conf=cfg.get('door_conf',.25),verbose=False,**kwargs)[0]
                            detections=[{'box':b,'class_id':c,'confidence':score} for b,c,score in zip(
                                pred.boxes.xyxy.cpu().tolist(),pred.boxes.cls.int().cpu().tolist(),pred.boxes.conf.cpu().tolist())]
                            candidates=[d['box'] for d in detections if d['class_id'] in accepted
                                        and plausible_door(d['box'], width, height, cfg.get('max_door_area',.6), cfg.get('min_door_aspect',0))
                                        and (not bus_gate or bus_gate.accept_door(d['box']))]
                            used_size=fallback_size
                        detection_backend = getattr(detector,'last_backend',mode)
                        if not candidates and hasattr(detector, 'reset'):
                            detector.reset()
                        # Associate with previous door; initially choose highest confidence
                        # (Ultralytics predictions are confidence ordered).
                        reference = lock.box or lock.candidate
                        chosen = max(candidates, key=lambda b:iou(reference,b)) if candidates and reference else (candidates[0] if candidates else None)
                        if mode!='cascade' and cfg.get('door_selection',{}).get('enabled',False):
                            selection_options={k:v for k,v in cfg['door_selection'].items() if k!='enabled'}
                            if confidence_selection:
                                scores=[max(d['confidence'] for d in detections if d['box']==box) for box in candidates]
                                selected=select_confident_door(candidates,[b for _,b in person_pairs],scores,
                                                              lock.valid_box(now),**selection_options)
                            else:
                                selected=select_door(candidates,[b for _,b in person_pairs],
                                                     lock.valid_box(now),**selection_options)
                            chosen=candidates[selected] if selected is not None else None
                        acquisition_attempt=None
                        if acquisition_detector is not None and fallback_due(chosen,lock.valid_box(now),acquisition_active,bus_source):
                            acquisition_attempt={'primary_detections':detections,'primary_input_size':used_size}
                            extra=acquisition_detector.predict(frame,imgsz=acquisition_size,device=args.device,
                                        conf=cfg.get('door_conf',.25),verbose=False,**kwargs)[0]
                            acquisition_calls+=1
                            fallback_detections=[{'box':b,'class_id':int(c),'confidence':float(s)} for b,c,s in zip(
                                extra.boxes.xyxy.cpu().tolist(),extra.boxes.cls.cpu().tolist(),extra.boxes.conf.cpu().tolist())]
                            fallback_candidates=[d['box'] for d in fallback_detections if d['class_id'] in accepted
                                and plausible_door(d['box'],width,height,cfg.get('max_door_area',.6),cfg.get('min_door_aspect',0))
                                and bus_gate.accept_door(d['box'])]
                            if confidence_selection:
                                scores=[max(d['confidence'] for d in fallback_detections if d['box']==b) for b in fallback_candidates]
                                selected=select_confident_door(fallback_candidates,[b for _,b in person_pairs],scores,None,**selection_options)
                            else:selected=select_door(fallback_candidates,[b for _,b in person_pairs],None,**selection_options)
                            acquisition_attempt['fallback_detections']=fallback_detections
                            if selected is not None:
                                chosen=fallback_candidates[selected];candidates=fallback_candidates;detections=fallback_detections
                                acquisition_active=True;used_size=acquisition_size
                        if acquisition_active:detection_backend='custom-acquisition-fallback'
                        partial_rejected = cfg.get('partial_door_guard',False) and contained_shrink(lock.valid_box(now),chosen,lock.min_iou)
                        partial_door_retry = cfg.get('partial_door_fast_retry',False) and (partial_rejected or (partial_door_retry and chosen is None))
                        # A rejected partial observation never refreshes last_seen or TTL.
                        lock.observe(None if partial_rejected else chosen, now)
                        df.write(json.dumps({'frame':n,'time_s':now,'input_size':used_size,
                                             'search_regions':kwargs.get('search_regions',[]),
                                             'backend':detection_backend,
                                             'bus_visible':bus_visible,'detections':detections,
                                             'bus_presence_source':bus_source,
                                             'candidate':chosen,'partial_rejected':partial_rejected,'partial_retry':partial_door_retry,'locked':lock.box,
                                             'generation':lock.generation,
                                             **({'acquisition_attempt':acquisition_attempt,'acquisition_fallback_active':acquisition_active}
                                                if acquisition_detector is not None else {})})+'\n')
                    if now-lock.last_seen > lock.ttl:
                        lock.observe(None, now)
                    if generation != lock.generation:
                        counter.reset_tracks()
                        generation = lock.generation
                    box = lock.box
                raw_pairs=person_pairs
                if profile:profile.mark('bus_door')
                poses={};pose_proof=[];pose_inferred=False
                if anchor_kind in ('pose_ankle','pose_dual'):
                    if pose_aux is not None:
                        if pose_due(box,[b for _,b in raw_pairs],cfg.get('pose_aux_gate')):
                            aux=pose_aux.predict(frame,imgsz=person_imgsz,conf=cfg.get('pose_aux_conf',.1),device=args.device,verbose=False)[0]
                            pose_aux_calls+=1;pose_inferred=True
                            if aux.keypoints is None:raise ValueError('Auxiliary model returned no keypoints')
                            poses,pose_proof=associated_keypoints(raw_pairs,aux.boxes.xyxy.cpu().tolist(),aux.keypoints.data.cpu().tolist())
                    else:
                        if result.keypoints is None:raise ValueError('Pose ankle requires a keypoint model')
                        poses={tid:k for tid,c,k in zip(all_ids,all_classes,result.keypoints.data.cpu().tolist()) if c==person_class}
                if profile:profile.mark('pose')
                if appearance is not None:
                    person_pairs=appearance.update(frame,raw_pairs,now,box,generation,n)
                if bridge is not None:
                    if bridge_generation!=generation or box is None:
                        bridge.reset();bridge_generation=generation
                    before=len(bridge.audit)
                    person_pairs=bridge.update(person_pairs,now,box)
                    bridge_events.extend(dict(e,frame=n,door_generation=generation) for e in bridge.audit[before:])
                points=measured_points(person_pairs,raw_pairs,poses,cfg)
                tf.write(json.dumps({'frame':n,'time_s':now,'door':box,
                                    'door_generation':generation,
                                    'raw_ids':[tid for tid,_ in raw_pairs],
                                    'raw_boxes':[b for _,b in raw_pairs],
                                    **({'tracker_filtered_boxes':tracker_boxes,'current_detection_box_proof':detection_box_proof,
                                        'person_box_coordinate_source':'current_detection'} if measured_box_adapter is not None else {}),
                                    'raw_confidences':[score for tid,cls,score in zip(all_ids,all_classes,all_confidences) if cls==person_class],
                                    'ids':[tid for tid,_ in person_pairs],
                                    'boxes':[b for _,b in person_pairs],'points':points,
                                    **({'pose_association':pose_proof,'pose_aux_inferred':pose_inferred} if pose_aux is not None else {}),
                                    **({'raw_keypoints':poses} if anchor_kind in ('pose_ankle','pose_dual') else {})})+'\n')
                if box is None:
                    counter.reset_tracks()
                else:
                    active += 1
                    if dual:
                        for event in counter.advance(now,[tid for tid,_ in person_pairs]):
                            event.update(frame=n,door_generation=generation,mode=mode)
                            events.append(event);ef.write(json.dumps(event)+'\n')
                    invisible_axis_frames+=int(boundary_visibility(counter.body if dual else counter,box,width,height)['has_invisible_axis_region'])
                    if person_pairs:
                        for (tid,b),point in zip(person_pairs,points):
                            if point is None and not dual:continue
                            event = counter.update(tid,b,point,box,now,frame=n) if dual else counter.update(tid,point,box,now)
                            if event:
                                event.update(frame=n, door_generation=generation, mode=mode)
                                events.append(event)
                                ef.write(json.dumps(event)+'\n')
                if profile:profile.mark('tracking_count')
                # Counting consumes boxes and measured pose points; drawing dense
                # segmentation masks adds seconds per frame without count evidence.
                frame = result.plot(line_width=2, font_size=12, masks=False)
                if box:
                    x1,y1,x2,y2 = map(int,box)
                    cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,255),2)
                    geometry_counter=counter.body if dual else counter
                    for threshold in (geometry_counter.low,geometry_counter.high):
                        if geometry_counter.axis == 'y':
                            y = int(y1+(y2-y1)*threshold)
                            a,b = (x1,y),(x2,y)
                        else:
                            x = int(x1+(x2-x1)*threshold)
                            a,b = (x,y1),(x,y2)
                        cv2.line(frame,a,b,(0,255,255),2)
                    if geometry_counter.transverse_exit is not None:
                        y=int(y1+(y2-y1)*geometry_counter.transverse_exit)
                        cv2.line(frame,(x1,y),(x2,y),(0,180,255),2)
                label = f"{mode} IN {counter.totals['in']} OUT {counter.totals['out']} {'ACTIVE' if box else 'WAIT DOOR'}"
                cv2.putText(frame,label,(15,30),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,255),2)
                writer.write(frame)
                if profile:profile.mark('render_video')
                if n == 0 or n % 30 == 0 or (events and events[-1]['frame'] == n):
                    cv2.imwrite(str(out/f'frame-{n:06d}.jpg'),frame)
                    ef.flush(); df.flush(); tf.flush()
                    print(f"frame={n} active={bool(box)} counts={counter.totals}", flush=True)
                if profile:profile.mark('diagnostic_output');profile.finish()
                n += 1
        finally:
            cap.release()
            writer.release()
            if profile:profile.close()
    elapsed = time.perf_counter()-started
    source_hash = hashlib.sha256(Path(source).read_bytes()).hexdigest() if isinstance(source,str) else None
    summary = {'frames':n,'source_fps':fps,'processed_fps_including_render':n/max(elapsed,.001),
               'elapsed_s':elapsed,'active_door_frames':active,'counts':counter.totals,
               'source':args.source,'source_sha256':source_hash,'device':args.device,
               'ultralytics':ultralytics.__version__,'config':cfg,
               'accuracy_validated':False,'jetson_validated':False}
    if moving_lock:
        summary['moving_door_follow']={'observations':lock.follow_audit,'count':len(lock.follow_audit),'predicted_boxes_used':False}
    summary['geometry_diagnostics']={'invisible_axis_region_frames':invisible_axis_frames,
        'note':'A region outside the image cannot establish that approach; doorway lateral routes may still work. No automatic threshold correction.'}
    if 'cpu_threads' in cfg:
        import torch
        summary['cpu_threads_requested']=cfg['cpu_threads']
        summary['cpu_threads_actual']=torch.get_num_threads()
        summary['cpu_threads_actual_scope']='PyTorch; ONNX session options recorded separately'
    summary['backend_execution']={'people':backend_runtime_info(people),
                                  'pose_aux':backend_runtime_info(pose_aux),
                                  'door':backend_runtime_info(detector),
                                  'bus':backend_runtime_info(vehicle)}
    if acquisition_detector is not None:
        summary['backend_execution']['door_acquisition_fallback']=backend_runtime_info(acquisition_detector)
        summary['door_acquisition_fallback_calls']=acquisition_calls
        summary['primary_door_detector_calls']=primary_door_calls
    summary['model_sha256'] = {key:hashlib.sha256(Path(cfg[key]).read_bytes()).hexdigest()
                               for key in ('person_model','door_model','door_primary_model','bus_model','pose_aux_model') if key in cfg and Path(cfg[key]).is_file()}
    if acquisition_detector is not None:
        summary['model_sha256']['door_acquisition_fallback.model']=hashlib.sha256(Path(acquisition_config['model']).read_bytes()).hexdigest()
    summary['pose_aux_calls']=pose_aux_calls
    summary['person_task_effective']=people.task
    if profile:summary['pipeline_profile']=profile.summary()
    if cfg.get('person_family')=='rtdetr':
        summary['person_preprocessing']='RT-DETR native640 square scale-filled; not YOLO rect letterboxing'
    summary['bus_detector_calls']=vehicle_calls
    summary['door_detector_calls'] = detector_calls
    if hasattr(people,'rtdetr_duplicate_filter'):
        adapter=people.rtdetr_duplicate_filter
        summary['rtdetr_duplicate_filter']=dict(iou=adapter.iou,frames=adapter.frames,removed=adapter.removed)
    summary['implementation_sha256']=implementation_hashes
    summary['source_timing']=source_clock.describe()
    if appearance is not None:
        summary['observed_appearance']=appearance.describe()
        root=Path(cfg['appearance_bridge']['model_root'])
        summary['observed_appearance']['model_sha256']=hashlib.sha256((root/'model.onnx').read_bytes()).hexdigest()
        summary['observed_appearance']['parity_sha256']=hashlib.sha256((root/'parity.json').read_bytes()).hexdigest()
    if bridge is not None:
        summary['track_bridge_events']=bridge_events
    if dual:summary['anchor_evidence']=counter.evidence
    if bus_gate:
        summary['bus_gate_stats'] = {'visible_frames':bus_visible_frames,
                                     'door_detection_skipped_frames':bus_gate_skipped_frames,
                                     'visual_continuity_frames':visual_bus_frames}
    if detector is not None and hasattr(detector, 'stats'):
        summary['cascade_stats'] = detector.stats
        if hasattr(detector,'reference') and hasattr(detector.reference,'stats'):
            summary['reference_inference_stats']=detector.reference.stats
    if detector is not None and hasattr(detector, 'provenance'):
        summary['door_model_provenance'] = detector.provenance
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
