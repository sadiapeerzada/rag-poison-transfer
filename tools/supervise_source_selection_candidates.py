#!/usr/bin/env python3
"""Fail-closed, one-batch-at-a-time supervisor for frozen transfer candidates.

The helper is tracked outside the protocol-fingerprinted src/ and scripts/ trees.
Runtime state stays in ignored logs/, and it never advances beyond candidates.
"""
from __future__ import annotations
import argparse, fcntl, hashlib, json, os, subprocess, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

SUPERVISOR_ROOT = Path(__file__).resolve().parents[1]
# Keep protocol execution on the verified frozen checkout; this helper branch
# intentionally has a different Git commit and must not supply experiment code.
REPO = Path.home()/"Documents/rag-research-results/hotpotqa-reliable-execution"
PROTOCOL = Path.home()/"Documents/rag-research-results/hotpotqa-transfer-20261028/transfer/protocol.json"
PIN = "94e4b6d8fb49a7e662074fb766c92498ad0667abf9cf38233e0f49aa401183aa"
PYTHON = Path.home()/"Downloads/rag-poison-transfer/.venv/bin/python"
SCRIPT = REPO/"scripts/run_source_selection_transfer.py"
MODEL_SNAPSHOT = Path.home()/".cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed"
OUTPUT = Path.home()/"Documents/rag-research-results/hotpotqa-transfer-20261028/transfer/execution/candidates"
LOCAL_STATE_DIR = SUPERVISOR_ROOT/"logs/transfer-supervisor"
LOG = LOCAL_STATE_DIR/"candidates.supervisor.progress.jsonl"
SUPERVISOR_LOCK = LOCAL_STATE_DIR/"candidates.supervisor.lock"
STAGE_LOCK = OUTPUT.parent/"candidates.writer.lock"
MODEL_LOCK = Path(tempfile.gettempdir())/"rag-poison-transfer-local-model.writer.lock"
BATCH_SIZE = 25
DIAGNOSTIC_DIR = LOCAL_STATE_DIR/"diagnostics"
STDOUT_LOG = DIAGNOSTIC_DIR/"candidate-child.stdout.log"
STDERR_LOG = DIAGNOSTIC_DIR/"candidate-child.stderr.log"

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def canonical_hash(obj) -> str:
    raw=json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()

def protocol_data(path=PROTOCOL):
    if sha(path)!=PIN: raise RuntimeError('frozen protocol SHA-256 mismatch')
    return json.loads(path.read_text())

def expected_ids(p):
    b=p['binding']; return b['query_ids'], b['matrix']

def checkpoint_audit(root=OUTPUT, protocol=None, validate_calls=True):
    p=protocol or protocol_data(); ids,matrix=expected_ids(p); expected=set(ids)
    root=Path(root); found=[]; seen=set(); total=len(matrix)*3*len(ids)
    qroot=root/'query-checkpoints'
    if qroot.exists():
        for f in sorted(qroot.rglob('*.json')):
            if f.is_symlink(): raise RuntimeError(f'symlink checkpoint: {f}')
            row=json.loads(f.read_text()); data=row.get('data'); bind=row.get('binding')
            if row.get('schema')!='atomic-batched-clean-cache/v1' or not isinstance(data,dict) or not isinstance(bind,dict): raise RuntimeError(f'invalid checkpoint envelope: {f}')
            if row.get('data_sha256') != canonical_hash(data): raise RuntimeError(f'checkpoint digest mismatch: {f}')
            if bind.get('protocol_sha256') != PIN: raise RuntimeError(f'protocol binding mismatch: {f}')
            qid=data.get('query_id'); family=bind.get('family'); intensity=bind.get('intensity'); seed=bind.get('seed'); band=bind.get('band')
            ident=(family,intensity,seed,band,qid)
            if ident in seen: raise RuntimeError(f'duplicate checkpoint identity: {ident}')
            seen.add(ident)
            if [family,intensity,seed] not in matrix or band not in (0,1,2) or qid not in expected: raise RuntimeError(f'unexpected checkpoint identity: {ident}')
            if f.name != hashlib.sha256(qid.encode()).hexdigest()+'.json': raise RuntimeError(f'checkpoint filename/query mismatch: {f}')
            if data.get('candidate_band')!=band or data.get('selection')!=bind.get('choice'): raise RuntimeError(f'checkpoint choice/band mismatch: {f}')
            status=data.get('status'); docs=data.get('documents')
            if status not in ('valid_construction','target_construction_failed','semantic_construction_failed') or not isinstance(docs,list): raise RuntimeError(f'invalid checkpoint status/data: {f}')
            if status!='valid_construction' and docs: raise RuntimeError(f'failed construction has documents: {f}')
            found.append((family,intensity,seed,band,qid))
    # Existing per-band ledgers must exactly mirror complete ordered checkpoint sets.
    for ledger in sorted((root/'candidates').glob('*/*.json')) if (root/'candidates').exists() else []:
        cell=ledger.parent.name; band=int(ledger.stem); obj=json.loads(ledger.read_text())
        family,intensity,seed=next((x for x in matrix if f'intensity-{x[1]}.seed-{x[2]}' in cell and x[0] in cell), (None,None,None))
        if family is None or (obj.get('family'),obj.get('intensity'),obj.get('seed'))!=(family,intensity,seed): raise RuntimeError(f'ledger identity mismatch: {ledger}')
        rows=obj.get('records'); expected_order=[x for x in ids]
        if not isinstance(rows,list) or [r.get('query_id') for r in rows]!=expected_order: raise RuntimeError(f'incomplete/duplicate ledger records: {ledger}')
        for row in rows:
            match=(family,intensity,seed,band,row['query_id'])
            if match not in seen: raise RuntimeError(f'ledger record lacks checkpoint: {match}')
            cp=root/'query-checkpoints'/cell/str(band)/(hashlib.sha256(row['query_id'].encode()).hexdigest()+'.json')
            if json.loads(cp.read_text())['data']!=row: raise RuntimeError(f'ledger/checkpoint mismatch: {cp}')
    marker=root/'candidates.complete.json'
    if marker.exists():
        m=json.loads(marker.read_text())
        actual={f.relative_to(root).as_posix():sha(f) for f in root.rglob('*') if f.is_file() and f.name not in ('candidates.complete.json','construction.seal.json')}
        if m.get('protocol_sha256')!=PIN or m.get('files_sha256')!=actual or len(found)!=total: raise RuntimeError('candidate completion marker/inventory mismatch')
    if root.exists() and validate_calls:
        code="import sys; sys.path.insert(0,sys.argv[1]); from src.experiments.execution_reliability import validate_store; validate_store(sys.argv[2])"
        subprocess.run([str(PYTHON),'-c',code,str(REPO),str(root)],check=True)
    if len(found)>total: raise RuntimeError('more checkpoints than frozen matrix permits')
    return {'count':len(found),'expected':total,'remaining':total-len(found),'batches_remaining':(total-len(found)+BATCH_SIZE-1)//BATCH_SIZE,'identities':seen}

def verify_clean_binding(p):
    # Reuse the experiment's own pinned source/environment checks without stage execution.
    code="import json,sys; sys.path.insert(0,sys.argv[1]); from scripts import run_week9_protocol_poison_matrix as b; print(json.dumps({'source':b.code_binding(),'environment':b.environment()}))"
    got=json.loads(subprocess.check_output([str(PYTHON),'-c',code,str(REPO)],text=True))
    if got['source'] != p.get('source'): raise RuntimeError('source code fingerprint mismatch')
    if got['environment'] != p.get('environment'): raise RuntimeError('frozen environment mismatch')

def probe_lock(path):
    if not path.exists(): return False
    try:
        with path.open('r') as f:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); fcntl.flock(f,fcntl.LOCK_UN)
        return False
    except BlockingIOError: return True

def preflight():
    p=protocol_data(); verify_clean_binding(p)
    if not PYTHON.is_file(): raise RuntimeError(f'exact interpreter absent: {PYTHON}')
    if probe_lock(STAGE_LOCK): raise RuntimeError('candidate stage lock actively held')
    if probe_lock(MODEL_LOCK): raise RuntimeError('model writer lock actively held')
    return p

def assert_local_runtime_path(path):
    path=Path(path).absolute(); root=SUPERVISOR_ROOT.resolve()
    resolved=path.resolve()
    if resolved!=root and root not in resolved.parents:
        raise RuntimeError(f'runtime path escaped the supervisor checkout: {path}')
    if path.is_symlink(): raise RuntimeError(f'runtime path may not be a symlink: {path}')
    for parent in path.parents:
        if parent==root: break
        if parent.exists() and parent.is_symlink(): raise RuntimeError(f'runtime directory may not contain symlinks: {parent}')

def append_event(event):
    assert_local_runtime_path(LOG)
    LOG.parent.mkdir(parents=True,exist_ok=True)
    line=json.dumps({'time_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':PIN,**event},sort_keys=True)+'\n'
    fd=os.open(LOG,os.O_WRONLY|os.O_CREAT|os.O_APPEND|getattr(os,'O_NOFOLLOW',0),0o600)
    try: os.write(fd,line.encode()); os.fsync(fd)
    finally: os.close(fd)

def validate_child_result(code, before, after, complete):
    if code==75:
        if after['count']<=before['count']: raise RuntimeError('pause exit without checkpoint progress')
        return 'paused'
    if code==0:
        if after['count']!=after['expected'] or not complete: raise RuntimeError('exit 0 without verified completion marker/count')
        return 'complete'
    raise RuntimeError(f'unexpected candidate runner exit code {code}')

def candidate_command():
    return [str(PYTHON),str(SCRIPT),'candidates','--protocol',str(PROTOCOL),
            '--protocol-sha256',PIN,'--model-snapshot',str(MODEL_SNAPSHOT),
            '--output',str(OUTPUT),'--allow-full-compute','--max-batches','1']

def launch_captured(cmd):
    """Append child streams to local supervisor diagnostics, never experiment output."""
    for path in (STDOUT_LOG,STDERR_LOG): assert_local_runtime_path(path)
    DIAGNOSTIC_DIR.mkdir(parents=True,exist_ok=True)
    with STDOUT_LOG.open('ab') as out, STDERR_LOG.open('ab') as err:
        return subprocess.Popen(cmd,stdout=out,stderr=err)

def run(args):
    p=preflight(); state=checkpoint_audit(protocol=p)
    cmd=candidate_command()
    if args.dry_run:
        print(json.dumps({'mode':'dry-run','command':cmd,'progress':{k:v for k,v in state.items() if k!='identities'},'worker_started':False,'diagnostic_logs':{'stdout':str(STDOUT_LOG),'stderr':str(STDERR_LOG)}},indent=2)); return 0
    if not args.approve_full_compute: raise RuntimeError('execution requires --approve-full-compute')
    if args.max_batches is None or args.max_batches<1: raise RuntimeError('execution requires positive --max-batches')
    if args.stall_seconds<1: raise RuntimeError('execution requires positive --stall-seconds')
    LOG.parent.mkdir(parents=True,exist_ok=True)
    assert_local_runtime_path(SUPERVISOR_LOCK)
    with SUPERVISOR_LOCK.open('a+') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('another supervisor holds its lock')
        append_event({'event':'started','checkpoint_count':state['count'],'max_batches':args.max_batches})
        for batch in range(args.max_batches):
            preflight(); before=checkpoint_audit(protocol=p)
            proc=launch_captured(cmd)
            last=before['count']; changed=time.monotonic()
            try:
                while proc.poll() is None:
                    time.sleep(1)
                    now=checkpoint_audit(protocol=p,validate_calls=False)
                    if now['count']>last: last=now['count']; changed=time.monotonic()
                    if time.monotonic()-changed>args.stall_seconds:
                        proc.terminate(); proc.wait(); append_event({'event':'stalled','batch':batch+1,'count':last}); raise RuntimeError('checkpoint progress stalled; child terminated')
            except KeyboardInterrupt:
                if proc.poll() is None: proc.terminate(); proc.wait()
                append_event({'event':'interrupted','batch':batch+1,'count':last}); raise
            except Exception as error:
                if proc.poll() is None: proc.terminate(); proc.wait()
                append_event({'event':'audit_error','batch':batch+1,'count':last,'error':str(error)}); raise
            after=checkpoint_audit(protocol=p); code=proc.returncode
            append_event({'event':'batch_exit','batch':batch+1,'exit_code':code,'before':before['count'],'after':after['count']})
            result=validate_child_result(code,before,after,(OUTPUT/'candidates.complete.json').is_file())
            if result=='paused': continue
            if result=='complete':
                print('Candidate library complete; no later stage invoked.'); return 0
        print('Limited run stopped at configured batch limit; safe to resume with same command.'); return 0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--max-batches',type=int); ap.add_argument('--stall-seconds',type=int,default=3600); ap.add_argument('--approve-full-compute',action='store_true')
    args=ap.parse_args()
    try:return run(args)
    except Exception as e: print(f'STOP: {e}',file=sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())
