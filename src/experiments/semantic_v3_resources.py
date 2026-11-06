"""Fail-closed operational admission; no scientific approvals or model imports."""
from datetime import datetime, timezone
import math
from pathlib import Path
import platform
import shutil
import subprocess

from src.experiments.semantic_v3_checkpoint import read_record


class ResourceAdmissionDenied(RuntimeError):
    """Safe pause: no new call intent has been reserved, or response is durable."""


def utc_now():
    return datetime.now(timezone.utc)


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.utcoffset() is None:
            raise ValueError('Timezone required')
        return result
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError('Timezone-aware resource deadline required') from exc


def validate_policy(policy):
    fields = {'min_free_disk_bytes', 'max_output_bytes', 'min_available_memory_bytes',
              'max_process_rss_bytes', 'max_memory_pressure', 'max_elapsed_seconds',
              'max_backend_calls', 'deadline'}
    if not isinstance(policy, dict) or set(policy) != fields:
        raise ValueError('Complete resource policy required')
    for key in fields - {'deadline', 'max_memory_pressure', 'max_elapsed_seconds'}:
        if type(policy[key]) is not int or policy[key] <= 0:
            raise ValueError('Positive integer resource limit required: ' + key)
    if policy['max_backend_calls'] > 200 or policy['max_memory_pressure'] not in ('normal', 'warning'):
        raise ValueError('Invalid resource pressure/call budget')
    seconds = policy['max_elapsed_seconds']
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Finite positive execution time required')
    timestamp(policy['deadline'])
    return policy


def system_sample(root):
    """OS availability is observed, never inferred from a model configuration.

    psutil is a required, version-pinned dependency for authorized runtimes.
    On macOS the kernel's pressure level is authoritative; probe failure denies.
    Linux fallback uses explicitly defined available-memory ratios for stub tests.
    """
    import psutil
    root = Path(root)
    existing = root
    while not existing.exists():
        existing = existing.parent
    memory = psutil.virtual_memory()
    if platform.system() == 'Darwin':
        level = int(subprocess.check_output(
            ['/usr/sbin/sysctl', '-n', 'kern.memorystatus_vm_pressure_level'],
            text=True, timeout=5).strip())
        pressure = {1: 'normal', 2: 'warning', 4: 'critical'}[level]
    else:
        ratio = memory.available / memory.total
        pressure = 'critical' if ratio < .05 else 'warning' if ratio < .10 else 'normal'
    used = 0
    if root.exists():
        for path in root.rglob('*'):
            if path.is_symlink():
                raise ResourceAdmissionDenied('Output symlink forbidden')
            if path.is_file():
                used += path.stat().st_size
    return {'free_disk_bytes': shutil.disk_usage(existing).free,
            'output_bytes': used, 'available_memory_bytes': memory.available,
            'process_rss_bytes': psutil.Process().memory_info().rss,
            'memory_pressure': pressure}


class ResourceMonitor:
    def __init__(self, policy, root, *, started_at=None):
        self.policy = validate_policy(policy)
        self.root = Path(root)
        clock = self.root / 'resource.clock.json'
        self.started_at = timestamp(read_record(clock)['started_at']) if clock.exists() else (started_at or utc_now())

    def observe(self, reserved_calls=0, *, new_call=False):
        try:
            sample = system_sample(self.root)
        except Exception as exc:
            raise ResourceAdmissionDenied('Resource telemetry unavailable') from exc
        expected = {'free_disk_bytes', 'output_bytes', 'available_memory_bytes',
                    'process_rss_bytes', 'memory_pressure'}
        if not isinstance(sample, dict) or set(sample) != expected:
            raise ResourceAdmissionDenied('Resource telemetry incomplete')
        for key in expected - {'memory_pressure'}:
            if type(sample[key]) is not int or sample[key] < 0:
                raise ResourceAdmissionDenied('Invalid resource telemetry')
        if sample['memory_pressure'] not in ('normal', 'warning', 'critical'):
            raise ResourceAdmissionDenied('Unknown memory pressure')
        now = utc_now()  # Include probe latency in deadline/elapsed checks.
        elapsed = (now - self.started_at).total_seconds()
        p = self.policy
        violations = []
        checks = [('disk reserve', sample['free_disk_bytes'] < p['min_free_disk_bytes']),
                  ('output budget', sample['output_bytes'] >= p['max_output_bytes']),
                  ('available memory', sample['available_memory_bytes'] < p['min_available_memory_bytes']),
                  ('process RSS', sample['process_rss_bytes'] > p['max_process_rss_bytes']),
                  ('memory pressure', sample['memory_pressure'] == 'critical' or
                   (p['max_memory_pressure'] == 'normal' and sample['memory_pressure'] != 'normal')),
                  ('execution time', elapsed < 0 or elapsed >= p['max_elapsed_seconds']),
                  ('execution deadline', now >= timestamp(p['deadline'])),
                  ('call budget', reserved_calls > p['max_backend_calls'] or
                   (new_call and reserved_calls >= p['max_backend_calls']))]
        violations.extend(name for name, failed in checks if failed)
        return {'observed_at': now.isoformat(), 'started_at': self.started_at.isoformat(),
                'elapsed_seconds_including_downtime': elapsed, 'reserved_calls': reserved_calls,
                'sample': sample, 'violations': violations}

    def check(self, reserved_calls=0, *, new_call=False):
        observation = self.observe(reserved_calls, new_call=new_call)
        if observation['violations']:
            raise ResourceAdmissionDenied('Resource admission denied: ' + ', '.join(observation['violations']))
        return observation
