#!/usr/bin/env python3
"""Validate private E4 annotation provenance and export aggregate-only findings.

This validates records, not factual truth. Reviews are assistant source-assisted;
neither external citations nor valid JSON establish independent adjudication.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
from scripts.prepare_e4_case_review import digest, encode, read

VERDICTS = {'source_contradicts_target', 'source_supports_target', 'ambiguous', 'unadjudicated'}
TIERS = {'native_source_assisted', 'external_primary_source_assisted', 'unadjudicated'}


def summarize(cases, reviews, packet_sha256, ledger_sha256):
    by_id = {c['case_id']: c for c in cases}
    if len(by_id) != len(cases) or len({c['query_id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate selected case or question')
    reviewed = set()
    for r in reviews:
        cid = r['case_id']
        if cid not in by_id or cid in reviewed:
            raise ValueError('Unknown/duplicate review case')
        reviewed.add(cid)
        c = by_id[cid]
        if r['packet_sha256'] != packet_sha256:
            raise ValueError('Review packet binding mismatch')
        if r.get('independent_adjudication') is not False or r.get('review_method') != 'assistant_source_assisted':
            raise ValueError('This ledger cannot establish independent adjudication')
        if r['tier'] not in TIERS or r['verdict'] not in VERDICTS or not r.get('rationale'):
            raise ValueError('Missing/invalid review classification')
        native = {d['doc_id']: d['text'] for d in c['gold_context']}
        for citation in r['native_evidence']:
            if not citation['excerpt'] or citation['excerpt'] not in native.get(citation['doc_id'], ''):
                raise ValueError('Native excerpt not present in bound case')
        external = r['external_evidence']
        for e in external:
            if (not e['url'].startswith('https://') or not e.get('accessed_date')
                    or not e.get('excerpt') or len(e['excerpt'].split()) > 25
                    or not e.get('supports') or not e.get('coverage_limit')):
                raise ValueError('Incomplete external evidence record')
        if r['tier'] == 'external_primary_source_assisted' and not external:
            raise ValueError('External tier without external evidence')
        if r['tier'] == 'native_source_assisted' and not r['native_evidence']:
            raise ValueError('Native tier without native evidence')
        if r['tier'] == 'unadjudicated' and r['verdict'] != 'unadjudicated':
            raise ValueError('Unadjudicated tier cannot claim a verdict')
    return dict(schema='e4-source-assisted-review-summary/v1', selected=len(cases),
                reviewed=len(reviews), unreviewed=len(cases)-len(reviews),
                tiers=dict(Counter(r['tier'] for r in reviews)),
                verdicts=dict(Counter(r['verdict'] for r in reviews)),
                gold_assessments=dict(Counter(r['gold_assessment'] for r in reviews)),
                flags=dict(Counter(flag for r in reviews for flag in r['flags'])),
                independently_adjudicated=0, new_model_calls=0,
                packet_sha256=packet_sha256, review_ledger_sha256=ledger_sha256,
                limitations=['Qualitative outcome-stratified sample; no prevalence estimate.',
                             'Benchmark context is source-assisted evidence, not independent ground truth.',
                             'External primary citations corroborate only the stated proposition, not every hop or poison detail.',
                             'No independent human review; no reliability statistic or corrected attack-success estimate.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', required=True, type=Path)
    parser.add_argument('--ledger', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite a prior summary')
    args.output.write_bytes(encode(summarize(read(args.packet), read(args.ledger),
                                           digest(args.packet.read_bytes()), digest(args.ledger.read_bytes()))))


if __name__ == '__main__':
    main()
