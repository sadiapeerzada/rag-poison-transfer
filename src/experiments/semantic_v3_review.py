"""Offline exports from complete, pinned construction records. No QA/ASR metrics."""
from pathlib import Path
from src.attacks.semantic_quality_targets_v3 import digest
from src.experiments.semantic_v3_preparation import blinded_forms, file_sha
from src.experiments.semantic_v3_checkpoint import read_record, publish_json, verify_journal
from src.experiments.semantic_v3_pilot import preflight


def sealed_records(root, manifest_reference, *, authorization_reference=None):
    _,values,_,_=preflight(manifest_reference,authorization_reference=authorization_reference);root=Path(root)
    seal=read_record(root/'complete.seal.json')
    if seal['context']['manifest_sha256']!=manifest_reference['sha256']:raise ValueError('Review seal manifest mismatch')
    expected={f'records/i{i}-{digest(q)}.json' for i in (1,3) for q in values['cohort']['query_ids']}
    if set(seal['record_sha256'])!=expected:raise ValueError('Incomplete sealed review population')
    if seal['backend_calls']!=verify_journal(root):raise ValueError('Sealed call count mismatch')
    if seal['journal_sha256']!={str(p.relative_to(root)):file_sha(p) for p in (root/'calls').glob('*.json')}:
        raise ValueError('Sealed call journal mutated')
    if seal.get('resource_sha256')!={str(p.relative_to(root)):file_sha(p) for p in (root/'resources').glob('*.json')} or seal.get('resource_clock_sha256')!=file_sha(root/'resource.clock.json'):
        raise ValueError('Sealed resource telemetry mutated')
    records=[]
    for name in sorted(expected):
        if file_sha(root/name)!=seal['record_sha256'][name]:raise ValueError('Sealed record mutated')
        records.append(read_record(root/name))
    return records,values,seal


def construction_summary(root, manifest_reference, *, authorization_reference=None):
    records,values,seal=sealed_records(root,manifest_reference,authorization_reference=authorization_reference)
    groups={}
    for intensity in (1,3):
        rows=[r for r in records if r['intensity']==intensity]
        groups[str(intensity)]={'attempted_queries':len(rows),
           'valid_constructions':sum(r['status']=='valid_construction' for r in rows),
           'target_abstentions':sum(r['status']=='target_construction_failed' for r in rows),
           'semantic_failures':sum(r['status']=='semantic_construction_failed' for r in rows),
           'duplicate_slots_among_successful_and_partial_documents':sum(r.get('document_diversity',{}).get('duplicate_slots',0) for r in rows),
           'independent_semantic_review':'pending_not_inferred_from_heuristics'}
    return {'scope':'development','stage':'construction-only','groups':groups,
            'study_kind':('nonprospective-development-diagnostic' if values['cohort'].get('prospective_evidence') is False else 'prospective-development-pilot'),
            'independent_confirmation':False,
            'backend_calls':seal['backend_calls'],'execution_kind':seal['execution_kind'],
            'retrieval_or_QA_outcomes':'not_evaluated'}


def export_semantic_review(root, manifest_reference, public_directory, private_directory, *, authorization_reference=None):
    records,values,seal=sealed_records(root,manifest_reference,authorization_reference=authorization_reference)
    public=Path(public_directory).resolve();private=Path(private_directory).resolve()
    if public==private or public in private.parents or private in public.parents:
        raise ValueError('Private mapping and public review must be separate directories')
    public.mkdir(parents=True,exist_ok=False);private.mkdir(parents=True,exist_ok=False)
    queries={q['query_id']:q for q in values['data']['queries']};targets={t['query_id']:t for t in values['targets']}
    attempts=[];mapping=[]
    for r in records:
        q=queries[r['query_id']]
        for slot in r['attempt_records']:
            for attempt in slot['attempts']:
                if attempt['generated_text'] is None:continue
                evidence=[ref for c in targets[q['query_id']]['candidates'] for ref in c['packet']['payload']['evidence']]
                attempts.append({'query_id':q['query_id'],'question':q['question'],'target':r['target'],
                       'gold_answer':q['gold_answer'],'gold_aliases':q.get('gold_aliases',[]),
                       'text':attempt['generated_text'],'evidence':evidence})
                mapping.append({'query_id':q['query_id'],'intensity':r['intensity'],'slot':slot['poison_index'],
                                'attempt':attempt['attempt'],'heuristic_outcome':attempt['outcome'],'reason':attempt['reason']})
    forms,order=blinded_forms(attempts)
    # Two blank independent passes; no assigned identity or approval invented.
    publish_json(public/'reviewer_A.blank.json',forms);publish_json(public/'reviewer_B.blank.json',forms)
    publish_json(private/'unblinding.json',[{**m,**mapping[m['original_index']]} for m in order])
    publish_json(private/'export_provenance.json',{'source_seal_sha256':file_sha(Path(root)/'complete.seal.json'),
                 'manifest_sha256':manifest_reference['sha256'],'attempt_count':len(attempts),'seed':42})
    return len(attempts)
