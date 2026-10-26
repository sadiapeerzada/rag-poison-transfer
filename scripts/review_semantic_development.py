#!/usr/bin/env python3
"""Export blinded human review, validate supplied reviews, or summarize sealed construction."""
import sys
sys.dont_write_bytecode=True
import argparse
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import run_week9_protocol_poison_matrix as base
from src.experiments import semantic_development_study as study
from src.experiments import semantic_review as review
from src.experiments import execution_reliability as reliable


def sealed(path,pin,root,seal_pin):
    value,dense,rcd,clean,cells=base.load_sealed(path,pin,root,seal_pin)
    if value.get('development_study')!=study.descriptor() or value['binding']['scope']!='development':raise ValueError('Only the frozen 25-query development study is supported')
    return value,clean,cells


def package_context(value,cells,pin,seal_pin):
    return {"protocol_sha256":pin,"construction_seal_sha256":seal_pin,
        "source":value["source"],"dataset":value["binding"]["dataset"],
        "query_set_fingerprint":value["binding"]["study_query_set_fingerprint"],
        "construction_failures":[{"query_id":r["query_id"],"intensity":c["intensity"],"status":r["status"],"target_answer":r["target_answer"]}
            for c in cells.values() for r in c["records"] if r["status"]!="valid_construction"]}


def safe_output(output,value,construction):
    path=base.legacy._ensure_output_outside_repository(Path(output))
    protected=[Path(construction).resolve(),Path(value["planned_outputs"]["evaluation"]).resolve()]
    if any(path==root or root in path.parents for root in protected):
        raise ValueError("Review output cannot modify sealed construction/evaluation namespaces")
    return path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['export','import','summary'])
    for name in ('protocol','construction-dir','package','reviews','output'):p.add_argument('--'+name,type=Path)
    p.add_argument('--protocol-sha256');p.add_argument('--construction-seal-sha256');a=p.parse_args()
    if a.stage=='import':
        if not all((a.package,a.reviews,a.output,a.protocol,a.protocol_sha256,a.construction_dir,a.construction_seal_sha256)):
            p.error('import requires package, reviews, pinned protocol/construction seal and a fresh output')
        value,clean,cells=sealed(a.protocol,a.protocol_sha256,a.construction_dir,a.construction_seal_sha256)
        a.output=safe_output(a.output,value,a.construction_dir)
        manifest,records=review.load_package(a.package)
        if (records!=review.items(clean,cells,a.protocol_sha256) or
            manifest['context']!=package_context(value,cells,a.protocol_sha256,a.construction_seal_sha256)):
            raise ValueError('Review package differs from the trusted frozen construction')
        result={**review.validate_reviews(records,review.read_reviews(a.reviews)),'package_context':manifest['context'],
            'human_review_file_sha256':base.sha(a.reviews)}
        reliable.atomic(a.output,result)
    else:
        if not all((a.protocol,a.protocol_sha256,a.construction_dir,a.construction_seal_sha256,a.output)):p.error('Require pinned protocol, construction root, seal and fresh output')
        value,clean,cells=sealed(a.protocol,a.protocol_sha256,a.construction_dir,a.construction_seal_sha256)
        a.output=safe_output(a.output,value,a.construction_dir)
        if a.stage=='summary':
            result={'schema':'rag-poison-transfer.semantic-quality-construction-summary/v1','diagnostic_only':True,
                'protocol_sha256':a.protocol_sha256,'construction_seal_sha256':a.construction_seal_sha256,
                'intensities':study.construction_summary(cells,a.construction_dir),'independent_review':'PENDING'}
            reliable.atomic(a.output,result)
        else:
            context=package_context(value,cells,a.protocol_sha256,a.construction_seal_sha256)
            result=review.write_package(a.output,review.items(clean,cells,a.protocol_sha256),context,reliable.atomic)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
