"""Fail-closed Mac resource guards for an explicitly authorized private pilot."""
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import threading
import time


HEALTH=threading.local()


def mac_health():
    pressure=int(subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True).strip())
    vm=subprocess.check_output(['vm_stat'],text=True)
    # Operator explicitly permits restoration from existing swap. Any NEW
    # swap-out still stops the run. General page-outs are not swap-out events.
    swapping=int(re.search(r'^Swapouts:\s+(\d+)',vm,re.M).group(1))
    thermal=subprocess.check_output(['pmset','-g','therm'],text=True)
    # CPU_Available_CPUs is a count, not a percentage.
    speed=[int(v) for v in re.findall(r'(?:CPU_Speed_Limit|CPU_Scheduler_Limit)\s*=\s*(\d+)',thermal)]
    thermal_warning=('Thermal_Level = ' in thermal and 'Thermal_Level = 0' not in thermal)
    HEALTH.snapshot={'memory_pressure_level':pressure,'swapouts':swapping,
                     'cpu_speed_scheduler_limits':speed,'thermal_warning':thermal_warning,
                     'thermal_raw':thermal}
    if pressure!=1:raise RuntimeError(f'Memory pressure level={pressure}')
    if any(v<100 for v in speed) or thermal_warning:
        raise RuntimeError('Thermal/performance limit: '+json.dumps(HEALTH.snapshot,sort_keys=True))
    return swapping


class Guard:
    def __init__(self,limits,directory,metal=None):
        self.limits=limits;self.directory=Path(directory);self.metal=metal
        self.started=time.monotonic();self.error=None;self.stop_event=threading.Event()
        self.swaps=mac_health();self.max_rss=0;self.max_metal=0
        self.check()
    def check(self):
        if self.error:raise RuntimeError(self.error)
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        self.max_rss=max(self.max_rss,rss)
        metal=0 if self.metal is None else self.metal.get_active_memory()+self.metal.get_cache_memory()
        self.max_metal=max(self.max_metal,metal)
        if rss>self.limits['rss_bytes'] or metal>self.limits['metal_bytes']:
            raise RuntimeError('Hard memory limit reached')
        if shutil.disk_usage(self.directory).free<self.limits['min_free_disk_bytes']:
            raise RuntimeError('Insufficient free disk')
        if time.monotonic()-self.started>self.limits['inference_seconds']:
            raise RuntimeError('Wall-clock limit reached')
        if mac_health()>self.swaps:raise RuntimeError('New swap-out detected')
    def start(self):
        def monitor():
            while not self.stop_event.wait(.5):
                try:self.check()
                except Exception as exc:
                    self.error=str(exc)
                    # Immediate termination preserves the pre-call intent. It is
                    # indeterminate, counted against the cap and never retried.
                    try:
                        with (self.directory/'RESOURCE_STOP.json').open('x') as f:
                            json.dump({'reason':self.error,'max_rss':self.max_rss,'max_metal':self.max_metal,
                                       'health':getattr(HEALTH,'snapshot',None),'baseline_swapouts':self.swaps,
                                       'elapsed_seconds':time.monotonic()-self.started,
                                       'guard_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},f)
                            f.flush();os.fsync(f.fileno())
                    finally:os._exit(75)
        self.thread=threading.Thread(target=monitor,daemon=True);self.thread.start()
    def close(self):
        self.stop_event.set()
        if hasattr(self,'thread'):self.thread.join(timeout=2)
