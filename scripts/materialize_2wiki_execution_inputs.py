#!/usr/bin/env python3
"""Pin local inputs after cohort freeze. Data I/O only; no nomination or inference."""
import argparse
import copy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import run_week9_protocol_poison_matrix as base
from src.experiments import twowiki_replication as two
from src.experiments import execution_reliability as reliable
from src.experiments.protocol import corpus_fingerprint,query_set_fingerprint


def materialize(spec_path,spec_pin,parent_path,parent_pin,scope,output,embedder,reranker):
    spec=base.read_pinned(spec_path,spec_pin);parent=base.read_pinned(parent_path,parent_pin)
    manifest=two.load_cohort(spec['cohort_manifest'],spec['cohort_manifest_sha256'])
    if (parent.get('schema')!=base.REPLICATION_PROTOCOL_SCHEMA or
        parent.get('rules')!={**base.protocol.rules(),'dataset_replication':'risk-disclosed-2wiki/v1'} or
        parent.get('binding',{}).get('dataset',{}).get('revision')!=two.REVISION or
        parent.get('replication')!=spec or parent['binding']['cohort_manifest_sha256']!=spec['cohort_manifest_sha256'] or
        parent['binding']['scope']!='heldout' or parent['binding']['query_ids']!=[r['query_id'] for r in manifest['cohorts']['dev']]):
        raise ValueError('Parent frozen 2Wiki protocol/cohort mismatch')
    output=base.legacy._ensure_output_outside_repository(Path(output))
    if output.exists():raise FileExistsError('Fresh materialization destination required')
    # Never change the already frozen ID order or use answers for selection.
    data=(two.fetch_selected('dev',parent['binding']['query_ids']) if scope=='heldout' else
          base.read_pinned(spec['development_data'],spec['development_data_sha256']))
    two.verify_questions(data,manifest['cohorts']['dev' if scope=='heldout' else 'train'])
    snapshots={}
    for name,path,identity in [('embedder',embedder,'BAAI/bge-small-en-v1.5'),('reranker',reranker,'cross-encoder/ms-marco-MiniLM-L-6-v2')]:
        snapshots[name]={'path':str(Path(path).resolve()),'binding':base.model_binding(path,identity)}
    local={**copy.deepcopy(spec),'schema':two.LOCAL_SCHEMA,'scope':scope,'parent_protocol_sha256':parent_pin,
        'local_data':str(output/'dataset.json'),'local_query_fingerprint':query_set_fingerprint(data['queries']),
        'local_corpus_fingerprint':corpus_fingerprint(data['corpus']),'retrieval_snapshots':snapshots}
    reliable.atomic(output/'dataset.json',data);local['local_data_sha256']=base.sha(output/'dataset.json')
    reliable.atomic(output/'replication_inputs.json',local)
    return {'status':'local_inputs_materialized_no_nomination_or_inference','scope':scope,'queries':len(data['queries']),
        'replication_spec_sha256':base.sha(output/'replication_inputs.json'),'model_calls':0}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('replication-spec','parent-protocol','output','embedder-snapshot','reranker-snapshot'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('replication-spec-sha256','parent-protocol-sha256'):p.add_argument('--'+name,required=True)
    p.add_argument('--scope',choices=('development','heldout'),required=True);a=p.parse_args()
    print(json.dumps(materialize(a.replication_spec,a.replication_spec_sha256,a.parent_protocol,a.parent_protocol_sha256,a.scope,a.output,a.embedder_snapshot,a.reranker_snapshot),indent=2))

if __name__=='__main__':main()
