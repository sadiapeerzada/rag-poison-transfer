"""Read-only exposure metadata reconciliation. No sampling, loaders or inference.

Explicit projections discard question/answer/prompt/document text. Historical
membership is observed, not proof of complete exposure or reviewer identity.
"""
import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

ID = re.compile(r'[0-9a-f]{32}')
SINGLE = {'query_id','_id','source_query_id','destination_query_id','destination_id','source_id'}
LISTS = {'query_ids','selected_query_ids','attacked_query_ids','known_historical_ids','study_query_ids','development_query_ids'}
FORBIDDEN = {'question','gold_answer','gold_aliases','answer','text','prompt','backend_prompt','raw_response',
             'generated_text'}


def sha(data):return hashlib.sha256(data).hexdigest()


def project(value):
    ids=set();revisions=set()
    def walk(node):
        if isinstance(node,dict):
            for key,item in node.items():
                if key in FORBIDDEN:continue
                if key in SINGLE and isinstance(item,str) and ID.fullmatch(item):ids.add(item)
                elif key in LISTS and isinstance(item,list):
                    ids.update(x for x in item if isinstance(x,str) and ID.fullmatch(x))
                elif key in ('dataset_revision','revision') and isinstance(item,str) and re.fullmatch(r'[0-9a-f]{40}',item):revisions.add(item)
                if isinstance(item,(dict,list)):walk(item)
        elif isinstance(node,list):
            for item in node:
                if isinstance(item,(dict,list)):walk(item)
    walk(value)
    return sorted(ids),sorted(revisions)


def inspect_bytes(raw, suffix):
    if not raw:return {'query_ids':[],'dataset_revisions':[],'status':'empty_not_evidence_of_nonexposure'}
    ids=set();revisions=set()
    try:
        if suffix=='.jsonl':values=[json.loads(line) for line in raw.decode().splitlines() if line.strip()]
        elif suffix=='.csv':values=list(csv.DictReader(io.StringIO(raw.decode())))
        else:values=[json.loads(raw)]
        for value in values:
            q,r=project(value);ids.update(q);revisions.update(r)
        return {'query_ids':sorted(ids),'dataset_revisions':sorted(revisions),
                'status':'typed_metadata_projected' if ids else 'no_recognized_ids_not_nonexposure'}
    except (ValueError,UnicodeDecodeError,TypeError) as exc:
        return {'query_ids':[],'dataset_revisions':[],'status':'unparsed_not_nonexposure','error_type':type(exc).__name__}


def inspect_file(path):
    path=Path(path);raw=path.read_bytes()
    return {'path':str(path),'sha256':sha(raw),'bytes':len(raw),**inspect_bytes(raw,path.suffix)}


def inspect_zip(path):
    """Declared historical review bundles only; never execute or extract members."""
    path=Path(path);out=[]
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if not info.filename.endswith(('.json','.jsonl','.csv')) or '__MACOSX' in info.filename:continue
            raw=archive.read(info)
            out.append({'path':str(path)+'!/'+info.filename,'archive_sha256':sha(path.read_bytes()),
                        'sha256':sha(raw),'bytes':len(raw),**inspect_bytes(raw,Path(info.filename).suffix)})
    return out


def reconcile(parent, observations, *, parent_sha256):
    """Preserve every parent source and exclusion. Never issue a certificate."""
    result=copy.deepcopy(parent);old=set(parent['excluded_query_ids'])
    observed={q for record in observations for q in record['query_ids']}
    result['excluded_query_ids']=sorted(old|observed)
    result['parent_registry_sha256']=parent_sha256
    result['reconciliation_observations']=copy.deepcopy(observations)
    result['new_query_ids']=sorted(observed-old)
    result['certification']=None;result['status']='incomplete_not_certified'
    result['reconciliation_limit']='Typed membership is conservative exclusion evidence; the historical 25-ID run binding and full custody remain unresolved.'
    return result


def assess_pool(pool_ids, excluded_ids, *, provenance, history_complete=False):
    """Counts only: deliberately never rank/sample/return potentially eligible IDs."""
    if any(not isinstance(x,str) or not ID.fullmatch(x) for x in pool_ids):raise ValueError('Only actual 2Wiki ID metadata accepted')
    if len(pool_ids)!=len(set(pool_ids)):raise ValueError('Duplicate metadata IDs')
    pool=set(pool_ids);blocked=set(excluded_ids)
    count=len(pool-blocked)
    return {'provenance':provenance,'pool_count':len(pool),'excluded_count':len(pool&blocked),
            'potentially_id_eligible_count':count,'at_least_25_by_id':count>=25,
            'historical_exposure_complete':history_complete,
            'prospective_go':False,'cohort_selected':False,
            'reason':'available_pool_exhausted' if count<25 else 'cardinality_only_custody_and_all_protocol_gates_still_required'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--parent',required=True)
    parser.add_argument('--parent-sha256',required=True);parser.add_argument('--source-list',required=True)
    parser.add_argument('--output-directory',required=True);args=parser.parse_args()
    path=Path(args.parent);raw=path.read_bytes()
    if sha(raw)!=args.parent_sha256:raise ValueError('Parent registry pin mismatch')
    source_paths=json.loads(Path(args.source_list).read_text())
    observations=[inspect_file(p) for p in source_paths]
    output=Path(args.output_directory);output.mkdir(parents=True,exist_ok=False)
    result=reconcile(json.loads(raw),observations,parent_sha256=args.parent_sha256)
    (output/'registry.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'observations':len(observations),'new_ids':len(result['new_query_ids']),
                      'excluded_ids':len(result['excluded_query_ids']),'certification':None,'cohort_selected':False}))


if __name__=='__main__':main()
