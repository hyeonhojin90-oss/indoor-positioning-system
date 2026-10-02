import unittest
from rtdetr_duplicate_filter import kept_indices
class FilterTests(unittest.TestCase):
 def test_highest_score_kept_and_different_class_preserved(self):
  b=[[0,0,10,20]]*3
  self.assertEqual(kept_indices(b,[.7,.9,.8],[0,0,5],.7),[1,2])
 def test_neighboring_people_and_nested_head_are_preserved(self):
  b=[[0,0,10,20],[5,0,15,20],[2,0,8,5]]
  self.assertEqual(kept_indices(b,[.9,.8,.7],[0]*3,.7),[0,1,2])
 def test_invalid_parameters_and_unobserved_boxes_rejected(self):
  for threshold in [True,0,1,float('nan')]:
   with self.assertRaises(ValueError):kept_indices([],[],[],threshold)
  with self.assertRaises(ValueError):kept_indices([[0,0,0,1]],[.9],[0],.7)
 def test_score_tie_is_deterministic(self):
  self.assertEqual(kept_indices([[0,0,10,20]]*2,[.9,.9],[0,0],.7),[0])
 def test_actual_results_filter_precedes_measurement_and_rejects_tracked_boxes(self):
  import os
  from pathlib import Path
  os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))
  import numpy as np
  import torch
  from types import SimpleNamespace
  from ultralytics.engine.results import Results
  from measured_detection_boxes import MeasuredDetectionBoxes
  from rtdetr_duplicate_filter import RTDETRDuplicateFilter
  class Model:
   predictor=None
   def __init__(self):self.callbacks=[]
   def add_callback(self,event,callback):self.callbacks.append(callback)
  model=Model();adapter=RTDETRDuplicateFilter(model,.7);measurement=MeasuredDetectionBoxes(model)
  r=Results(np.zeros((20,20,3),dtype=np.uint8),path='synthetic callback fixture',names={0:'person'},boxes=torch.tensor([[0,0,10,20,.6,0],[0,0,10,20,.9,0]]))
  predictor=SimpleNamespace(results=[r])
  for callback in model.callbacks:callback(predictor)
  self.assertEqual(len(r.boxes),1);self.assertEqual(adapter.removed,1);self.assertAlmostEqual(measurement.snapshots[0]['score'],.9,places=6)
  r.update(boxes=torch.tensor([[0,0,10,20,77,.9,0]]))
  with self.assertRaises(ValueError):adapter.filter(predictor)

if __name__=='__main__':unittest.main()
