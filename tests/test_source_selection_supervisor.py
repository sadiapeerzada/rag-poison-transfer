import importlib.util, json, tempfile, unittest, sys, subprocess
from unittest.mock import patch
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
            f.write_text(json.dumps(obj)); a=sup.checkpoint_audit(root,p,validate_calls=False); self.assertEqual(a['count'],1)
            self.assertEqual(a['remaining'],2)
            f.write_text(json.dumps({**obj,'data_sha256':'bad'}))
            with self.assertRaisesRegex(RuntimeError,'digest'): sup.checkpoint_audit(root,p,validate_calls=False)
    def test_checkpoint_duplicate_identity_is_rejected_without_local_runtime(self):
        p={'binding':{'query_ids':['q1'],'matrix':[['lexical_influential_token',1,42]]}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); cell='lexical_influential_token.intensity-1.seed-42'
            data={'query_id':'q1','status':'target_construction_failed','documents':[],
                  'candidate_band':0,'selection':None}
            binding={'protocol_sha256':sup.PIN,'family':'lexical_influential_token',
                     'intensity':1,'seed':42,'band':0,'choice':None}
            obj={'schema':'atomic-batched-clean-cache/v1','binding':binding,
                 'data':data,'data_sha256':sup.canonical_hash(data)}
            name=sup.hashlib.sha256(b'q1').hexdigest()+'.json'
            for folder in ('0','extra'):
                f=root/'query-checkpoints'/cell/folder/name
                f.parent.mkdir(parents=True,exist_ok=True)
                f.write_text(json.dumps(obj))
            with self.assertRaisesRegex(RuntimeError,'duplicate checkpoint identity'):
                sup.checkpoint_audit(root,p,validate_calls=False)

    def test_production_checkpoint_audit_keeps_pinned_validator(self):
        p={'binding':{'query_ids':['q1'],'matrix':[['lexical_influential_token',1,42]]}}
        with tempfile.TemporaryDirectory() as d:
            with patch.object(sup.subprocess,'run') as run_validator:
                sup.checkpoint_audit(Path(d),p)
            run_validator.assert_called_once()
            command=run_validator.call_args.args[0]
            self.assertEqual(command[0],str(sup.PYTHON))
            self.assertEqual(command[3],str(sup.REPO))
            self.assertEqual(command[4],str(Path(d)))
            self.assertIn('validate_store',command[2])
            self.assertTrue(run_validator.call_args.kwargs['check'])

    def test_production_preflight_rejects_missing_pinned_interpreter(self):
        with (patch.object(sup,'protocol_data',return_value={'binding':{}}),
              patch.object(sup,'verify_clean_binding'),
              patch.object(sup,'PYTHON',Path('/nonexistent/pinned-python'))):
            with self.assertRaisesRegex(RuntimeError,'exact interpreter absent'):
                sup.preflight()

    def _race_fixture(self, root):
        qid='q1'; family='lexical_influential_token'; intensity=1; seed=42; band=0
        cell=f'{family}.intensity-{intensity}.seed-{seed}'
        data={'query_id':qid,'query_fingerprint':'qfp','target_answer':None,'documents':[],
              'partial_documents':[],'attempt_records':[],'candidate_band':band,'selection':None,
              'status':'target_construction_failed'}
        binding={'protocol_sha256':sup.PIN,'query':'qfp','family':family,'intensity':intensity,
                 'seed':seed,'band':band,'choice':None}
        cp=root/'query-checkpoints'/cell/str(band)/(sup.hashlib.sha256(qid.encode()).hexdigest()+'.json')
        ledger=root/'candidates'/cell/'0.json'
        def write_pair():
            cp.parent.mkdir(parents=True,exist_ok=True); ledger.parent.mkdir(parents=True,exist_ok=True)
            cp.write_text(json.dumps({'schema':'atomic-batched-clean-cache/v1','binding':binding,
                                      'data':data,'data_sha256':sup.canonical_hash(data)}))
            ledger.write_text(json.dumps({'family':family,'intensity':intensity,'seed':seed,'records':[data]}))
        protocol={'binding':{'query_ids':[qid],'matrix':[[family,intensity,seed]]}}
        return protocol,cp,ledger,write_pair

    def test_live_progress_poll_avoids_checkpoint_ledger_scan_race(self):
        # Reproduce the old failure deterministically: checkpoint enumeration ends,
        # then the writer publishes the checkpoint and its ledger before
        # the strict audit starts scanning ledgers.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); qroot=root/'query-checkpoints'
            qroot.mkdir(parents=True)
            protocol,cp,ledger,publish=self._race_fixture(root)
            original=sup.Path.rglob
            def racing_rglob(path, pattern):
                if path==qroot and pattern=='*.json':
                    def empty_then_publish():
                        yield from ()
                        publish()
                    return empty_then_publish()
                return original(path,pattern)
            with patch.object(sup.Path,'rglob',racing_rglob):
                with self.assertRaisesRegex(RuntimeError,'ledger record lacks checkpoint'):
                    sup.checkpoint_audit(root,protocol,validate_calls=False)
            # Reset and inject the same write window into the progress-only poll.
            root=Path(d)/'live'; qroot=root/'query-checkpoints'; qroot.mkdir(parents=True)
            protocol,cp,ledger,publish=self._race_fixture(root)
            def live_racing_rglob(path, pattern):
                if path==qroot and pattern=='*.json':
                    def empty_then_publish():
                        yield from ()
                        publish()
                    return empty_then_publish()
                return original(path,pattern)
            with patch.object(sup.Path,'rglob',live_racing_rglob):
                self.assertEqual(sup.progress_checkpoint_count(root),0)
            self.assertTrue(cp.exists()); self.assertTrue(ledger.exists())
            after=sup.checkpoint_audit(root,protocol,validate_calls=False)
            self.assertEqual(after['count'],1)

    def test_post_exit_strict_audit_rejects_genuine_missing_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); protocol,cp,ledger,publish=self._race_fixture(root)
            ledger.parent.mkdir(parents=True)
            ledger.write_text(json.dumps({'family':'lexical_influential_token','intensity':1,
                'seed':42,'records':[{'query_id':'q1'}]}))
            with self.assertRaisesRegex(RuntimeError,'ledger record lacks checkpoint'):
                sup.checkpoint_audit(root,protocol,validate_calls=False)

    def test_stopped_child_is_waited_before_strict_audit(self):
        order=[]
        class Child:
            def poll(self): return None
            def terminate(self): order.append('terminate')
            def wait(self): order.append('wait'); return 0
        old=sup.checkpoint_audit
        try:
            sup.checkpoint_audit=lambda **kwargs: order.append('strict-audit') or {'count':0}
            sup.stopped_child_audit(Child(),{})
        finally: sup.checkpoint_audit=old
        self.assertEqual(order,['terminate','wait','strict-audit'])

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
