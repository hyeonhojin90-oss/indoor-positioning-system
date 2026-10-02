import unittest
from run_experiment import completion_state

class ProcessReceiptTests(unittest.TestCase):
    def test_failure_never_verified_even_if_summary_exists(self):
        audit={'complete_source':True,'replay_parity':True,'implementation_drift_since_start':[]}
        self.assertFalse(completion_state(1,True,audit)['full_run_verified'])
    def test_summary_without_full_trace_or_current_hash_is_insufficient(self):
        for audit in [None,{'complete_source':False,'replay_parity':True},
                      {'complete_source':True,'replay_parity':False},
                      {'complete_source':True,'replay_parity':True,'implementation_drift_since_start':['run.py']}]:
            self.assertFalse(completion_state(0,True,audit)['full_run_verified'])
    def test_full_process_is_not_project_or_hardware_completion(self):
        r=completion_state(0,True,{'complete_source':True,'replay_parity':True,'implementation_drift_since_start':[]})
        self.assertTrue(r['full_run_verified']);self.assertFalse(r['project_goal_completed']);self.assertFalse(r['hardware_validated'])

if __name__=='__main__':unittest.main()
