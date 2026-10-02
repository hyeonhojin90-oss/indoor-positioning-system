import tempfile
from pathlib import Path
import unittest
from source_timing import SourceClock,source_kind


class SourceTimingTests(unittest.TestCase):
    def test_file_time_does_not_follow_cpu_processing_delay(self):
        with tempfile.TemporaryDirectory() as tmp:
            video=Path(tmp)/'video.mp4';video.write_bytes(b'local')
            clock=SourceClock(str(video),25,100,clock=lambda:999)
            self.assertEqual(clock.frame_time(0),0)
            self.assertEqual(clock.frame_time(25),1)
            self.assertEqual(clock.describe()['source_kind'],'file')

    def test_rtsp_and_csi_pipeline_use_actual_observation_intervals(self):
        for source in ['rtsp://camera.local/live','nvarguscamerasrc ! appsink',0]:
            samples=iter([100.2,101.7])
            clock=SourceClock(source,30,100,clock=lambda:next(samples))
            self.assertAlmostEqual(clock.frame_time(0),.2)
            self.assertAlmostEqual(clock.frame_time(1),1.7)
            self.assertFalse(clock.describe()['camera_exposure_timestamp_verified'])

    def test_stream_time_regression_and_invalid_clock_are_rejected(self):
        samples=iter([101,100.5]);clock=SourceClock(0,30,100,clock=lambda:next(samples))
        clock.frame_time(0)
        with self.assertRaises(ValueError):clock.frame_time(1)
        for fps in [0,-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):SourceClock(0,fps,100)

    def test_explicit_source_kind_and_repeated_frame(self):
        self.assertEqual(source_kind('https://host/recording.mp4','file'),'file')
        self.assertEqual(source_kind('recorded.mp4','live'),'live')
        with self.assertRaises(ValueError):source_kind(0,'file')
        clock=SourceClock('recorded.mp4',30,100,requested='file')
        clock.frame_time(1)
        with self.assertRaises(ValueError):clock.frame_time(1)


if __name__=='__main__':unittest.main()
