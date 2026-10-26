"""Blinded review export/import. Human judgments are never generated here."""
import csv
import hashlib
import io
import json
from datetime import datetime
from pathlib import Path
from src.experiments.week9_construction import fingerprint

SCHEMA='rag-poison-transfer.semantic-quality-review/v1'
RATINGS=('subject_correspondence','relation_correspondence','target_assertion','grammatical_validity',
    'semantic_relevance','factual_falsity','evidence_sufficiency')
REVIEW=(*RATINGS,'reviewer_confidence','reviewer_notes','evidence_references_json','reviewer',
    'review_timestamp','independent_of_generation','final_reviewer_decision')
FIXED=('item_id','query_id','question','gold_answer','gold_aliases_json','target_answer','generated_text',
    'source_evidence_json','intensity','poison_index','attempt')


def blank_review():
    return {**{k:'' for k in REVIEW},'final_reviewer_decision':'pending'}


def blind(item):
    return {**{k:str(item[k]) if item[k] is not None else '' for k in FIXED},**blank_review()}


def items(clean,cells,pin):
    by_id={q['query_id']:q for q in clean['queries']};corpus={d['doc_id']:d for d in clean['corpus']};result=[]
    for cell in cells.values():
        for row in cell['records']:
            query=by_id[row['query_id']]
            evidence=[{'source_kind':'dataset_provided_passage_not_independently_verified',
                'doc_id':did,'text':corpus[did]['text']} for did in query.get('gold_doc_ids',[]) if did in corpus]
            for entry in row['attempt_records']:
                for event in entry['attempts']:
                    key=[pin,cell['family'],cell['intensity'],row['query_id'],entry['poison_index'],event['attempt'],event['generated_text']]
                    result.append({'schema':SCHEMA,'item_id':fingerprint(key),'protocol_sha256':pin,
                        'query_id':query['query_id'],'question':query['question'],'gold_answer':query['gold_answer'],
                        'gold_aliases_json':json.dumps(query.get('gold_aliases',[]),ensure_ascii=False),
                        'target_answer':row['target_answer'],'generated_text':event['generated_text'],
                        'source_evidence_json':json.dumps(evidence,ensure_ascii=False),
                        'intensity':cell['intensity'],'poison_index':entry['poison_index'],'attempt':event['attempt'],
                        'automated_validator_decision':event['outcome'],'automated_rejection_reason':event['reason'],
                        'failure_category':event.get('failure_category'),
                        'automatic_subject_and_relation_correspondence':'heuristic_pattern_match' if event['outcome']=='heuristically_supported_unverified' else 'not_established',
                        'factual_falsity_status':'not_independently_established','prompt_version':event['prompt_version'],
                        'validation_version':event['validation_version'],'model_provenance':event['model_provenance'],
                        'review':blank_review()})
    return sorted(result,key=lambda r:fingerprint(['review-order/v1',r['item_id']]))


def write_package(directory,records,context,write_json):
    directory=Path(directory)
    if directory.exists():raise FileExistsError('Fresh review-package directory required')
    directory.mkdir(parents=True)
    texts={'master.jsonl':''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),
        'blinded_review.jsonl':''.join(json.dumps(blind(r),ensure_ascii=False)+'\n' for r in records)}
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=[*FIXED,*REVIEW]);writer.writeheader()
    writer.writerows(blind(r) for r in records);texts['blinded_review.csv']=stream.getvalue()
    hashes={}
    for name,text in texts.items():
        path=directory/name
        with path.open('x',encoding='utf-8',newline='') as output:output.write(text)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest={'schema':SCHEMA,'context':context,'review_item_count':len(records),'review_scope':'all generated attempts, including rejected/empty outputs',
        'files_sha256':hashes,'independent_review_status':'pending','identity_authentication':'not performed by software',
        'blinding':'automatic decisions/reasons and QA attack outcomes omitted from blinded sheets; present in master'}
    write_json(directory/'manifest.json',manifest)
    return manifest


def load_package(directory):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
    if manifest.get('schema')!=SCHEMA or set(manifest.get('files_sha256',{}))!={'master.jsonl','blinded_review.csv','blinded_review.jsonl'}:
        raise ValueError('Unknown review-package schema/files')
    for name,pin in manifest['files_sha256'].items():
        path=directory/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=pin:raise ValueError('Review package integrity mismatch; edit a separate review copy')
    records=[json.loads(s) for s in (directory/'master.jsonl').read_text().splitlines() if s]
    if len(records)!=manifest['review_item_count'] or len({r['item_id'] for r in records})!=len(records):raise ValueError('Review package item count/identity mismatch')
    return manifest,records


def read_reviews(path):
    path=Path(path)
    if path.suffix=='.csv':
        with path.open(newline='') as source:return list(csv.DictReader(source))
    if path.suffix=='.jsonl':return [json.loads(s) for s in path.read_text().splitlines() if s]
    raise ValueError('Human reviews must be CSV or JSONL')


def validate_reviews(records,reviews):
    indexed={r['item_id']:r for r in records};seen=set();completed=[];pending=[]
    for row in reviews:
        if not isinstance(row,dict) or set(row)!={*FIXED,*REVIEW}:raise ValueError('Malformed review columns')
        key=row['item_id']
        if key not in indexed or key in seen:raise ValueError('Unknown or duplicate review item')
        seen.add(key);expected=blind(indexed[key])
        if any(row[k]!=expected[k] for k in FIXED):raise ValueError('Immutable review question/target/text binding changed')
        if any(not isinstance(row[k],str) for k in REVIEW):raise ValueError('Review fields must be text')
        if any(row[k] not in ('','yes','no','uncertain') for k in RATINGS):raise ValueError('Malformed review rating')
        if row['reviewer_confidence'] not in ('','low','medium','high'):raise ValueError('Malformed confidence')
        decision=row['final_reviewer_decision']
        if decision not in ('pending','accept','reject','uncertain'):raise ValueError('Malformed reviewer decision')
        if row['independent_of_generation'] not in ('','yes','no'):raise ValueError('Malformed independence attestation')
        references=json.loads(row['evidence_references_json'] or '[]')
        if not isinstance(references,list) or any(not isinstance(r,dict) or set(r)!={'source_reference','claim_supported','limitations'} or
            any(not isinstance(v,str) for v in r.values()) or not r['source_reference'].strip() or not r['claim_supported'].strip() for r in references):
            raise ValueError('Malformed human evidence references')
        if decision=='pending':pending.append(key);continue
        if not row['reviewer'].strip() or row['independent_of_generation']!='yes':raise ValueError('Completed independent review requires identity and explicit independence attestation')
        try:timestamp=datetime.fromisoformat(row['review_timestamp'])
        except ValueError as error:raise ValueError('Actual review timestamp with timezone required') from error
        if timestamp.tzinfo is None:raise ValueError('Review timestamp timezone required')
        if decision=='accept' and (any(row[k]!='yes' for k in RATINGS) or row['reviewer_confidence'] not in ('medium','high') or not references):
            raise ValueError('Acceptance requires affirmative rubric, sufficient referenced evidence and confidence')
        if decision!='accept' and not row['reviewer_notes'].strip():raise ValueError('Rejection/uncertainty requires reviewer notes')
        completed.append(row)
    missing=sorted(set(indexed)-seen)
    return {'schema':SCHEMA,'expected_reviews':len(indexed),'completed_reviews':len(completed),
        'pending_review_ids':pending,'missing_review_ids':missing,'completed_review_records':completed,
        'decision_counts':{d:sum(r['final_reviewer_decision']==d for r in completed) for d in ('accept','reject','uncertain')},
        'status':'awaiting_independent_review' if missing or pending or not completed else 'human_records_imported_not_independently_authenticated',
        'identity_and_independence_authentication':'human attestations only; not verified by software',
        'does_not_approve_a_heldout_protocol':True}
