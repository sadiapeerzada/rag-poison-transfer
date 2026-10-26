#!/usr/bin/env python3
"""Materialize the already selected training cohort; never read held-out answers."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.experiments.twowiki_replication import SCHEMA,load_cohort,fetch_selected,verify_questions,sha
from scripts.run_week9_protocol_poison_matrix import write


def prepare(manifest_path,pin,output):
    manifest=load_cohort(manifest_path,pin)
    output=Path(output).resolve()
    if output.exists():raise FileExistsError('Use fresh development preprocessing output')
    records=manifest['cohorts']['train']
    data=fetch_selected('train',[r['query_id'] for r in records])
    verify_questions(data,records)
    write(output/'development_data.json',data)
    specification={'schema':SCHEMA,'cohort_manifest':str(Path(manifest_path).resolve()),'cohort_manifest_sha256':pin,
        'development_data':str(output/'development_data.json'),'development_data_sha256':sha(output/'development_data.json'),
        'historical_exposure_risk_acknowledged':True,'complete_historical_nonoverlap_certified':False}
    write(output/'replication_inputs.json',specification)
    return {'queries':len(data['queries']),'replication_spec_sha256':sha(output/'replication_inputs.json'),
            'heldout_answer_records_read':0,'model_calls':0}


def main():
    import json
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cohort-manifest',required=True,type=Path)
    parser.add_argument('--cohort-manifest-sha256',required=True);parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args();print(json.dumps(prepare(args.cohort_manifest,args.cohort_manifest_sha256,args.output_dir),indent=2))


if __name__=='__main__':main()
