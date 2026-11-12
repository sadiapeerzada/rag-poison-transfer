#!/usr/bin/env python3
"""Read-only E1/E2 inventory and exact-response reuse checker; never imports models.

inventory ROOT MANIFEST --sha256 PIN verifies a historical stage, emitting counts
only. compare PLAN HISTORY --history-sha256 PIN accepts private JSON arrays:
PLAN contains required observations; HISTORY contains historical observations.
Both use the explicit FIELDS contract below (not a native-run adapter). HISTORY
must be externally pinned to a reviewed export. Never publish either input.
No options create or overwrite files. Diagnostics contain no private values.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random

FIELDS = (
    'query_id', 'query_sha256', 'target_assignment_sha256', 'candidate_sha256',
    'poison_corpus_sha256', 'retrieval_config', 'retrieval_evidence',
    'prompt', 'backend_prompt', 'model_snapshot_sha256', 'tokenizer_sha256',
    'generator_config', 'backend_environment', 'decoding', 'scoring',
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def complete(row):
    # Empty poison lists should be represented by an explicit clean corpus hash.
    return isinstance(row, dict) and all(row.get(k) not in (None, '', {}, []) for k in FIELDS)


def classify(required, historical):
    if historical is None:
        return 'MISSING'
    if not complete(required) or not complete(historical):
        return 'UNVERIFIED'
    if any(required[k] != historical[k] for k in FIELDS):
        return 'INCOMPATIBLE'
    # A cached logical measurement is not an additional physical invocation.
    if (historical.get('provenance') != 'physical_completed'
            or not historical.get('physical_call_id')
            or not isinstance(historical.get('raw_response'), str)):
        return 'UNVERIFIED'
    return 'REUSABLE'


def binding_key(row):
    """Fingerprint the complete contract, keeping observation IDs as provenance only."""
    return digest({k: row[k] for k in FIELDS})


def compare(required, history):
    for rows in (required, history):
        if not isinstance(rows, list) or any(
                not isinstance(r, dict) or not isinstance(r.get('observation_id'), str)
                or not r['observation_id'] for r in rows):
            raise ValueError('Invalid observation schema')
        if len({r['observation_id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate observation keys')

    by_id, by_binding, physical_records = {}, {}, {}
    for row in history:
        by_id[row['observation_id']] = row
        if complete(row):
            by_binding.setdefault(binding_key(row), []).append(row)
        call = row.get('physical_call_id')
        if call is not None:
            if not isinstance(call, str) or not call:
                raise ValueError('Invalid physical call identity')
            # Even incomplete records cannot contradict known input fields or
            # the preserved response for the same physical invocation.
            known = physical_records.setdefault(call, {})
            for field in (*FIELDS, 'raw_response'):
                if field in row and row[field] is not None:
                    if field in known and digest(known[field]) != digest(row[field]):
                        raise ValueError('Conflicting physical call provenance')
                    known[field] = row[field]

    counts = Counter({k: 0 for k in ('REUSABLE', 'MISSING', 'INCOMPATIBLE', 'UNVERIFIED')})
    physical, missing = set(), set()
    for row in required:
        matches = by_binding.get(binding_key(row), []) if complete(row) else []
        verified = [old for old in matches if classify(row, old) == 'REUSABLE']
        if verified:
            # Stable representative when independent historical invocations have
            # identical inputs. Keep every original observation ID unchanged.
            old = min(verified, key=lambda r: (r['physical_call_id'], r['observation_id']))
            status = 'REUSABLE'
            physical.add(old['physical_call_id'])
        elif not complete(row) or matches:
            status = 'UNVERIFIED'
        else:
            old = by_id.get(row['observation_id'])
            status = classify(row, old)
            # An incomplete historical record with compatible known fields may
            # be a match; absence of metadata must not become a new-call budget.
            if status == 'MISSING' and any(
                    not complete(h) and all(
                        h.get(k) is None or digest(h[k]) == digest(row[k])
                        for k in FIELDS) for h in history):
                status = 'UNVERIFIED'
        counts[status] += 1
        if status != 'REUSABLE' and complete(row):
            missing.add(binding_key(row))

    # A pinned export alone cannot validate incomplete/uncertified provenance.
    # Be conservative even when that historical row did not supply a match.
    uncertain = (counts['UNVERIFIED'] > 0
                 or any(classify(h, h) != 'REUSABLE' for h in history))
    return {'classification_counts': dict(counts), 'verified_reusable_physical_calls': len(physical),
            'nonreusable_distinct_complete_inputs': len(missing),
            'new_call_estimate': 'UNKNOWN' if uncertain else len(missing),
            'reused_responses_are_new_independent_inference': False}


def select(library, method, seed, *, budget, feedback=None):
    """Same ordered frozen library for all methods; feedback is source-only booleans.

    Each item has candidate_id and valid. Failed slots still consume budget.
    Fixed-budget screening evaluates every valid candidate, without early stop.
    """
    if type(budget) is not int or budget < 1 or len(library) != budget:
        raise ValueError('Candidate budget parity violation')
    if len({r['candidate_id'] for r in library}) != budget:
        raise ValueError('Duplicate candidate identities')
    valid = [r['candidate_id'] for r in library if r['valid'] is True]
    if method not in ('M1', 'M2', 'M3'):
        raise ValueError('Unknown method')
    if feedback is not None and (set(feedback) != set(valid) or any(type(v) is not bool for v in feedback.values())):
        raise ValueError('Only complete source-only success feedback is accepted')
    if method == 'M3' and feedback is None:
        raise ValueError('Missing source screening')
    if not valid:
        return None
    if method == 'M2':
        return random.Random(seed).choice(valid)
    if method == 'M3':
        return next((c for c in valid if feedback[c]), valid[0])
    return valid[0]


def inventory(root, manifest, pin):
    root, manifest = Path(root), Path(manifest)
    if root.is_symlink() or not root.is_dir() or manifest.is_symlink() or sha(manifest) != pin:
        raise ValueError('Missing or unpinned inventory')
    expected = json.loads(manifest.read_text()).get('files_sha256')
    if not isinstance(expected, dict) or not expected:
        raise ValueError('Missing inventory entries')
    paths = list(root.rglob('*'))
    if any(p.is_symlink() for p in paths):
        raise ValueError('Symlink inventory rejected')
    actual = {p.relative_to(root).as_posix() for p in paths if p.is_file() and p.resolve() != manifest.resolve()}
    if actual != set(expected):
        raise ValueError('Inventory membership mismatch')
    for rel, checksum in expected.items():
        if sha(root / rel) != checksum:
            raise ValueError('Inventory content mismatch')
    return {'status': 'VERIFIED_INVENTORY_ONLY', 'files_verified': len(expected),
            'generator_reuse_eligibility': 'UNVERIFIED'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inv = sub.add_parser('inventory')
    inv.add_argument('root'); inv.add_argument('manifest'); inv.add_argument('--sha256', required=True)
    cmp = sub.add_parser('compare')
    cmp.add_argument('plan'); cmp.add_argument('history'); cmp.add_argument('--history-sha256', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'inventory':
            result = inventory(args.root, args.manifest, args.sha256)
        else:
            if Path(args.history).is_symlink() or sha(args.history) != args.history_sha256:
                raise ValueError('Historical export provenance rejected')
            result = compare(json.loads(Path(args.plan).read_text()), json.loads(Path(args.history).read_text()))
    except (ValueError, OSError, TypeError, KeyError):
        parser.exit(2, 'Audit rejected: invalid, missing, mismatched or unpinned private evidence.\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
