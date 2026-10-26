#!/usr/bin/env python3
"""Read-only generation incident inventory. JSON to stdout; no recovery or inference."""
import sys
sys.dont_write_bytecode=True
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.evaluation.qa_records import validate_qa
from src.experiments.week9_construction import fingerprint


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):
    if Path(path).is_symlink():raise ValueError('Symlink input not inspected')
    return json.loads(Path(path).read_text())


def audit(protocol_path,protocol_pin,construction,local_timezone='Asia/Kolkata'):
    protocol_path=Path(protocol_path);root=Path(construction)
    if root.is_symlink() or not root.is_dir():raise ValueError('Existing nonsymlink construction directory required')
    if protocol_path.is_symlink():raise ValueError('Protocol symlink not inspected')
    if sha(protocol_path)!=protocol_pin:raise ValueError('Protocol SHA-256 mismatch')
    protocol=read(protocol_path);ids=protocol['binding']['query_ids'];matrix=protocol['binding']['matrix']
    identities={hashlib.sha256(q.encode()).hexdigest():q for q in ids}
    inventory={};issues=[];events=[];checkpoints=[]
    files=[]
    for p in sorted(root.rglob('*')):
        if p.is_symlink():issues.append({'path':p.relative_to(root).as_posix(),'issue':'symlink_not_followed'});continue
        if p.is_file():
            files.append(p);inventory[p.relative_to(root).as_posix()]=sha(p)
            if p.name.startswith('.atomic-'):issues.append({'path':p.relative_to(root).as_posix(),'issue':'unpublished_atomic_file'})
    for p in files:
        if not p.name.endswith('.intent.json'):continue
        rel=p.relative_to(root).as_posix();entry={'intent':rel,'intent_sha256':inventory[rel],
            'mtime_utc':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),
            'mtime_local':datetime.fromtimestamp(p.stat().st_mtime,ZoneInfo(local_timezone)).isoformat(),
            'automatic_retry_permitted':False}
        response=p.with_name(p.name.replace('.intent.json','.response.json'))
        try:
            request=read(p);provenance=request.get('provenance',{});context=request.get('context',{})
            directory_query=identities.get(p.parent.name)
            qid=provenance.get('query_id',context.get('query_id',directory_query))
            entry.update(query_id=qid,query_directory_key=p.parent.name,
                request_fingerprint=fingerprint(request),provenance_sha256=fingerprint(provenance),
                prompt_sha256=hashlib.sha256(request['prompt'].encode()).hexdigest(),max_tokens=request.get('max_tokens'),
                model_binding_sha256=fingerprint(provenance.get('model')),model_revision=provenance.get('model',{}).get('revision'),
                protocol_reference_matches=provenance.get('protocol_sha256')==protocol_pin,
                model_reference_matches=provenance.get('model')==protocol.get('model'))
            entry['identity_matches']=qid in ids and (directory_query is None or qid==directory_query)
            if not entry['identity_matches'] or not entry['protocol_reference_matches'] or not entry['model_reference_matches']:
                issues.append({'path':rel,'issue':'query_or_protocol_or_model_provenance_mismatch'})
            if not response.exists():entry.update(status='unresolved_intent',backend_execution='unknown')
            else:
                saved=read(response);entry['response']=response.relative_to(root).as_posix();entry['response_sha256']=sha(response)
                if saved.get('request_fingerprint')!=fingerprint(request):raise ValueError('Response request fingerprint mismatch')
                if 'error' in saved:
                    entry.update(status='error_response',error_type=saved.get('error_type'),error_sha256=fingerprint(saved.get('error')),backend_execution='recorded_error')
                else:
                    record=saved['generation'];validate_qa(record,record['extracted_answer'])
                    if record['prompt']!=request['prompt']:raise ValueError('Response prompt mismatch')
                    if 'generation_sha256' in saved and saved['generation_sha256']!=fingerprint(record):raise ValueError('Response content hash mismatch')
                    entry.update(status='completed_response',generation_sha256=fingerprint(record),
                        stored_generation_hash='present_matches' if 'generation_sha256' in saved else 'legacy_unhashed',backend_execution='recorded_response')
        except (ValueError,KeyError,TypeError,OSError,AttributeError) as error:
            entry.update(status='invalid_journal',diagnostic_error=type(error).__name__+': '+str(error))
        events.append(entry)
    for p in files:
        if p.name.endswith('.response.json') and not p.with_name(p.name.replace('.response.json','.intent.json')).exists():
            events.append({'response':p.relative_to(root).as_posix(),'response_sha256':sha(p),'status':'orphan_response','automatic_retry_permitted':False})
        if len(p.relative_to(root).parts)==3 and p.parent.name=='queries' and p.suffix=='.json':
            item={'path':p.relative_to(root).as_posix(),'sha256':sha(p),'cell':p.parent.parent.name}
            try:
                obj=read(p);record=obj.get('data',obj)
                if 'data_sha256' in obj and obj['data_sha256']!=fingerprint(record):raise ValueError('Checkpoint hash mismatch')
                item.update(query_id=record['query_id'],construction_status=record['status'],query_fingerprint=record.get('query_fingerprint'))
                if identities.get(p.stem)!=record['query_id']:raise ValueError('Checkpoint query key mismatch')
            except (ValueError,KeyError,TypeError,OSError,AttributeError) as error:item['diagnostic_error']=str(error)
            checkpoints.append(item)
    expected_cells=[f'{a}.intensity-{i}.seed-{s}' for a,i,s in matrix]
    present={(x['cell'],x.get('query_id')) for x in checkpoints if 'diagnostic_error' not in x}
    missing=[{'cell':cell,'query_id':qid,'query_key':hashlib.sha256(qid.encode()).hexdigest()} for cell in expected_cells for qid in ids if (cell,qid) not in present]
    counts=dict(Counter(x['status'] for x in events));seal=root/'construction.seal.json'
    plan=root/'construction.plan.json';plan_status='absent'
    if plan.exists():
        try:
            value=read(plan);plan_status='matches' if value.get('protocol_sha256')==protocol_pin and value.get('binding')==protocol['binding'] and value.get('source')==protocol['source'] else 'mismatch'
        except (ValueError,KeyError,TypeError):plan_status='invalid'
    return {'schema':'rag-poison-transfer.generation-incident-diagnostics/v1','read_only':True,
        'protocol':str(protocol_path.resolve()),'protocol_sha256':protocol_pin,'scope':protocol['binding']['scope'],
        'construction_root':str(root.resolve()),'query_ids':ids,'matrix':matrix,'model_binding_sha256':fingerprint(protocol.get('model')),
        'plan_status':plan_status,'journal_counts':counts,'journal_events':events,'issues':issues,
        'query_checkpoints':checkpoints,'expected_query_checkpoint_count':len(ids)*len(matrix),
        'present_query_checkpoint_count':len(checkpoints),'validated_query_checkpoint_count':len(present),'missing_query_checkpoints':missing,
        'present_cell_records':[cell for cell in expected_cells if (root/cell/'construction.json').is_file()],
        'construction_seal_present':seal.is_file(),'inventory_sha256':fingerprint(inventory),'files_sha256':inventory,
        'automatic_retry_permitted':False,'root_cause':'undetermined_from_journals',
        'limitations':['An intent does not establish whether backend execution began or finished.',
            'A missing response cannot distinguish interruption, crash, termination or response-publication failure.',
            'Filesystem times are observations, not authenticated execution or approval timestamps.',
            'Legacy unhashed responses have structural checks, not independent content authentication.',
            'This report is not execution authorization or a scientific approval.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol',type=Path,required=True);p.add_argument('--protocol-sha256',required=True)
    p.add_argument('--construction-dir',type=Path,required=True);p.add_argument('--timezone',default='Asia/Kolkata')
    a=p.parse_args();print(json.dumps(audit(a.protocol,a.protocol_sha256,a.construction_dir,a.timezone),indent=2))

if __name__=='__main__':main()
