"""Fixed development-only methodology study; no model or outcome-based selection."""
import hashlib
from src.experiments.protocol import query_set_fingerprint
from src.experiments.week9_construction import fingerprint, canonical

IDENTIFIER='semantic-quality-25/v1'
SCHEMA='rag-poison-transfer.semantic-development-study/v1'
COUNT=25
SEED=42


def descriptor(identifier=IDENTIFIER):
    if identifier!=IDENTIFIER:raise ValueError('Unknown development study')
    return {'schema':SCHEMA,'identifier':IDENTIFIER,'diagnostic_only':True,'query_count':COUNT,
        'query_selection_seed':SEED,'selection':'SHA256(canonical [study identifier, seed, query ID]); ascending hash then query ID; first 25',
        'matrix':[['semantic_fluent_false_evidence',1,42],['semantic_fluent_false_evidence',3,42]],
        'maximum_construction_calls':200,'maximum_evaluation_calls_without_cache':200,'maximum_total_backend_calls':400,
        'independent_review_required_for_semantic_validity':True}


def validate(value,scope,replication,profile):
    if (value!=descriptor() or scope!='development' or not isinstance(replication,dict) or
        replication.get('schema')!='rag-poison-transfer.2wiki-replication-inputs/v2' or
        replication.get('scope')!='development' or not isinstance(profile,dict) or
        profile.get('identifier')!='question-anchored-development/v1'):
        raise ValueError('Study requires fixed 25-query local 2Wiki development inputs and the development semantic profile')


def select(queries,heldout_ids):
    ids=[q['query_id'] for q in queries]
    if len(ids)!=len(set(ids)) or len(ids)<COUNT:raise ValueError('Distinct development pool of at least 25 queries required')
    if len(heldout_ids)!=len(set(heldout_ids)) or set(ids)&set(heldout_ids):raise ValueError('Development/held-out query overlap or duplicate held-out IDs')
    key=lambda q:(hashlib.sha256(canonical([IDENTIFIER,SEED,q['query_id']])).hexdigest(),q['query_id'])
    return sorted(queries,key=key)[:COUNT]


def bind(binding,full_data,manifest):
    if binding.get('dataset',{}).get('split')!='train':raise ValueError('Published train split required')
    queries=select(full_data['queries'],[q['query_id'] for q in manifest['cohorts']['dev']])
    return {**binding,'query_ids':[q['query_id'] for q in queries],'matrix':descriptor()['matrix'],
        'development_study':IDENTIFIER,'study_selection_seed':SEED,
        'study_pool_ids_fingerprint':fingerprint(sorted(q['query_id'] for q in full_data['queries'])),
        'study_query_set_fingerprint':query_set_fingerprint(queries)}


def construction_summary(cells,root):
    """Automatic construction counts only; accepted partials are never full attacks."""
    from collections import Counter
    from pathlib import Path
    import json
    result={}
    for name,cell in cells.items():
        rows=cell['records'];intensity=cell['intensity'];docs=[];events=[]
        for row in rows:
            for entry in row['attempt_records']:
                docs.append(entry['attempts']);events.extend(entry['attempts'])
        accepted=lambda e:e['outcome']=='heuristically_supported_unverified'
        latencies=[]
        for path in (Path(root)/name/'generation').rglob('*.response.json'):
            saved=json.loads(path.read_text())
            if 'generation' in saved:latencies.append(saved['generation'])
        texts=[e['generated_text'] for e in events if isinstance(e.get('generated_text'),str)]
        result[name]={'queries':len(rows),'planned_document_slots':len(rows)*intensity,
            'documents_attempted':len(docs),'generation_attempts':len(events),
            'first_attempt_accepted':sum(accepted(d[0]) for d in docs),
            'documents_retried':sum(len(d)==2 for d in docs),
            'retry_accepted':sum(len(d)==2 and accepted(d[1]) for d in docs),
            'documents_automatically_accepted_including_partials':sum(any(accepted(e) for e in d) for d in docs),
            'fully_constructed_queries':sum(r['status']=='valid_construction' for r in rows),
            'partially_constructed_queries':sum(bool(r.get('partial_documents')) for r in rows),
            'failed_construction_queries':sum(r['status']!='valid_construction' for r in rows),
            'target_construction_failed_queries':sum(r['status']=='target_construction_failed' for r in rows),
            'valid_documents_retained_for_injection':sum(len(r['documents']) for r in rows),
            'rejection_categories':dict(Counter(e.get('failure_category',e['outcome']) for e in events if not accepted(e))),
            'rejection_reasons':dict(Counter(e['reason'] for e in events if not accepted(e))),
            'malformed_attempts':sum(any(word in (e.get('reason') or '') for word in ('empty text','invalid length','prompt/meta leakage')) for e in events),
            'distinct_generated_texts':len(set(texts)),'nonempty_generated_texts':sum(bool(t.strip()) for t in texts),
            'actual_completed_construction_backend_calls':len(latencies),
            'construction_backend_latency_seconds':sum(g['generator_latency_seconds'] or 0 for g in latencies),
            'capture_elapsed_seconds':sum(g['elapsed_seconds'] for g in latencies),
            'independent_semantic_validity':'PENDING','factual_falsity':'NOT INDEPENDENTLY ESTABLISHED'}
        d=result[name]
        def rate(n,den):return {"numerator":n,"denominator":den,"value":n/den if den else None}
        d["rates"]={"full_query_coverage":rate(d["fully_constructed_queries"],d["queries"]),
            "per_attempted_document_acceptance":rate(d["documents_automatically_accepted_including_partials"],d["documents_attempted"]),
            "per_planned_slot_acceptance":rate(d["documents_automatically_accepted_including_partials"],d["planned_document_slots"]),
            "first_attempt_acceptance":rate(d["first_attempt_accepted"],d["documents_attempted"]),
            "retry_rate":rate(d["documents_retried"],d["documents_attempted"]),
            "retry_acceptance":rate(d["retry_accepted"],d["documents_retried"])}
    return result
