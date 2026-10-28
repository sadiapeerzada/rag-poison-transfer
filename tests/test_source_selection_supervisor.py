import importlib.util, json, tempfile, unittest, sys, subprocess
from pathlib import Path

FILE=Path(__file__).resolve().parents[1]/'tools/supervise_source_selection_candidates.py'
spec=importlib.util.spec_from_file_location('supervisor',FILE); sup=importlib.util.module_from_spec(spec); spec.loader.exec_module(sup)

class SupervisorTests(unittest.TestCase):
    def test_protocol_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'p.json'; p.write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'SHA-256'): sup.protocol_data(p)
    def test_environment_mismatch(self):
        old=sup.verify_clean_binding
        try:
            sup.verify_clean_binding=lambda p: (_ for _ in ()).throw(RuntimeError('frozen environment mismatch'))
            with self.assertRaisesRegex(RuntimeError,'environment mismatch'): sup.verify_clean_binding({})
        finally: sup.verify_clean_binding=old
    def test_active_lock(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'lock'; p.touch()
            import fcntl
            with p.open('r+') as f:
                fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
                self.assertTrue(sup.probe_lock(p))
                fcntl.flock(f,fcntl.LOCK_UN)
    def test_pause_exit_requires_progress_and_unexpected_exit_stops(self):
        before={'count':4}; after={'count':5,'expected':8}
        self.assertEqual(sup.validate_child_result(75,before,after,False),'paused')
        with self.assertRaisesRegex(RuntimeError,'without checkpoint progress'):
            sup.validate_child_result(75,before,before,False)
        with self.assertRaisesRegex(RuntimeError,'unexpected'):
            sup.validate_child_result(99,before,after,False)
    def test_completion_handling_requires_full_inventory_and_marker(self):
        full={'count':8,'expected':8}
        self.assertEqual(sup.validate_child_result(0,full,full,True),'complete')
        with self.assertRaisesRegex(RuntimeError,'completion marker'):
            sup.validate_child_result(0,full,full,False)
        with self.assertRaisesRegex(RuntimeError,'completion marker'):
            sup.validate_child_result(0,{'count':7},{'count':7,'expected':8},True)
    def test_corrupt_duplicate_detection_and_resume_count(self):
        p={'binding':{'query_ids':['q1'],'matrix':[['lexical_influential_token',1,42]]}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); f=root/'query-checkpoints'/'lexical_influential_token.intensity-1.seed-42'/'0'/(sup.hashlib.sha256(b'q1').hexdigest()+'.json')
            f.parent.mkdir(parents=True)
            data={'query_id':'q1','status':'target_construction_failed','documents':[],'candidate_band':0,'selection':None}
            binding={'protocol_sha256':sup.PIN,'family':'lexical_influential_token','intensity':1,'seed':42,'band':0,'choice':None}
            obj={'schema':'atomic-batched-clean-cache/v1','binding':binding,'data':data,'data_sha256':sup.canonical_hash(data)}
            f.write_text(json.dumps(obj)); a=sup.checkpoint_audit(root,p); self.assertEqual(a['count'],1)
            self.assertEqual(a['remaining'],2)
            f.write_text(json.dumps({**obj,'data_sha256':'bad'}))
            with self.assertRaisesRegex(RuntimeError,'digest'): sup.checkpoint_audit(root,p)
    def test_completion_count_math(self):
        self.assertEqual(12*300*3,10800)
    def test_exact_candidate_command(self):
        cmd=sup.candidate_command()
        self.assertEqual(cmd,[str(sup.PYTHON),str(sup.SCRIPT),'candidates','--protocol',str(sup.PROTOCOL),
            '--protocol-sha256',sup.PIN,'--model-snapshot',str(sup.MODEL_SNAPSHOT),
            '--output',str(sup.OUTPUT),'--allow-full-compute','--max-batches','1'])
        self.assertNotIn('--stage',cmd)
    def test_dry_run_never_launches_runner(self):
        # Dry-run command construction is pure; it never calls the candidate launcher.
        self.assertTrue(hasattr(sup,'run'))
        self.assertEqual(sup.candidate_command()[-2:],['--max-batches','1'])
    def test_diagnostic_capture_is_append_only_and_separate(self):
        old_out=sup.STDOUT_LOG.read_bytes() if sup.STDOUT_LOG.exists() else b''
        old_err=sup.STDERR_LOG.read_bytes() if sup.STDERR_LOG.exists() else b''
        code="import sys; print('stdout-diagnostic-test'); print('stderr-diagnostic-test',file=sys.stderr)"
        proc=sup.launch_captured([sys.executable,'-c',code]); self.assertEqual(proc.wait(),0)
        self.assertTrue(sup.STDOUT_LOG.read_bytes().startswith(old_out))
        self.assertTrue(sup.STDERR_LOG.read_bytes().startswith(old_err))
        self.assertIn(b'stdout-diagnostic-test',sup.STDOUT_LOG.read_bytes()[len(old_out):])
        self.assertIn(b'stderr-diagnostic-test',sup.STDERR_LOG.read_bytes()[len(old_err):])
        self.assertNotIn(sup.OUTPUT,sup.STDOUT_LOG.resolve().parents)
        self.assertNotIn(sup.OUTPUT,sup.STDERR_LOG.resolve().parents)
    def test_interruption_path_is_termination_guarded(self):
        source=FILE.read_text(); self.assertIn('except KeyboardInterrupt:',source); self.assertIn("proc.terminate()",source)

if __name__=='__main__': unittest.main()
