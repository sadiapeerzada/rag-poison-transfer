#!/usr/bin/env python3
"""One operator-authorized initialization, followed by already bounded E1 dispatch.

Purely diagnostic preflight; no model/config/guard threshold changes. The marker
prevents a second initialization through this entrypoint without new authorization.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import resource
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.hotpotqa_native_reuse import read
from scripts.audit_e1_e2_reuse import sha
from scripts.bounded_pilot_resources import Guard,mac_health,HEALTH
from src.experiments.execution_reliability import atomic,acquire_model_lease


def run(root,snapshot):
    root,snapshot=Path(root),Path(snapshot)
    marker=root/'operator-authorized-single-initialization.json'
    if marker.exists():raise RuntimeError('One authorized initialization already reserved; no automatic retry')
    freeze=read(root/'pilot.freeze.json');limits=freeze['limits']
    acquire_model_lease()
    import psutil
    import mlx.core as mx
    available=psutil.virtual_memory().available
    weights=sum(p.stat().st_size for p in snapshot.glob('*.safetensors'))
    metal=mx.get_active_memory()+mx.get_cache_memory()
    preflight={'utc':datetime.now(timezone.utc).isoformat(),'available_ram_bytes':available,
        'total_ram_bytes':psutil.virtual_memory().total,'weight_file_bytes':weights,
        'rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'metal_bytes':metal,
        'metal_policy_headroom_bytes':limits['metal_bytes']-metal,
        'disk_free_bytes':shutil.disk_usage(root).free,'limits':limits,'observer_sha256':sha(__file__)}
    baseline=mac_health();samples=[dict(HEALTH.snapshot)]
    for _ in range(2):
        time.sleep(5)
        if mac_health()!=baseline:raise RuntimeError('New swap-out in preflight; no initialization')
        samples.append(dict(HEALTH.snapshot))
    available=psutil.virtual_memory().available
    preflight['available_ram_bytes_after_idle']=available
    preflight['disk_free_bytes']=shutil.disk_usage(root).free
    if available<weights+512*2**20 or limits['metal_bytes']-metal<weights+512*2**20:
        raise RuntimeError('Insufficient available RAM/Metal headroom for weight bytes plus 512 MiB; no initialization')
    if preflight['rss_bytes']>=limits['rss_bytes'] or preflight['disk_free_bytes']<limits['min_free_disk_bytes']:
        raise RuntimeError('Preflight RSS/disk requirement failed; no initialization')
    preflight['health_samples']=samples
    atomic(root/'operator-initialization-preflight.json',preflight)
    atomic(marker,{'authorized_initializations':1,'pilot_sha256':sha(root/'pilot.freeze.json'),
        'preflight_sha256':sha(root/'operator-initialization-preflight.json'),
        'model_configuration_changed':False,'guard_thresholds_changed':False})
    charged=0.
    for p in (root.parent/'e1-e2-20261112-authorized-session/sessions').glob('*.complete.json'):
        charged+=read(p)['elapsed_seconds']
    outer_dir=root/'operator-initialization-resource-monitor';outer_dir.mkdir(exist_ok=False)
    guard=Guard({**limits,'inference_seconds':limits['inference_seconds']-charged},outer_dir,metal=mx)
    guard.start()
    print('PREFLIGHT_PASSED_ONE_AUTHORIZED_INITIALIZATION',flush=True)
    try:
        from scripts.run_bounded_e1_e2_qwen import execute
        execute(root,snapshot,'E1')
    finally:guard.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--snapshot',required=True);a=p.parse_args();run(a.root,a.snapshot)
