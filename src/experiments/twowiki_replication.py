"""Explicit risk-disclosed 2Wiki adapter, separate from frozen HotpotQA inputs."""
import hashlib
import json
from pathlib import Path

from src.attacks.reviewed_target_artifact import read_pinned
from src.experiments.protocol import query_set_fingerprint

SCHEMA='rag-poison-transfer.2wiki-replication-inputs/v1'
LOCAL_SCHEMA='rag-poison-transfer.2wiki-replication-inputs/v2'
REVISION='9823f70484dea525100394220b0ea5184d0eeb7b'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cohort(path,pin):
    manifest=read_pinned(path,pin)
    if (manifest.get('schema')!='rag-poison-transfer.2wiki-disjoint-cohort-manifest/v1' or
        manifest.get('dataset_revision')!=REVISION or manifest.get('complete_historical_nonoverlap_certified') is not False or
        not manifest.get('known_historical_nonoverlap_verified') or manifest.get('development_heldout_id_overlap')!=0):
        raise ValueError('2Wiki cohort provenance or exposure disclosure mismatch')
    policy=read_pinned(Path(path).parent/'cohort_policy.json',manifest['policy_sha256'])
    historical=set(policy['known_historical_ids'])
    from src.experiments.week9_construction import fingerprint
    for split in ('train','dev'):
        rows=manifest['cohorts'][split]
        if len(rows)!=300 or len({r['query_id'] for r in rows})!=300 or fingerprint(rows)!=manifest['cohort_fingerprints'][split]:
            raise ValueError('Frozen 2Wiki cohort count/fingerprint mismatch')
        if historical&{r['query_id'] for r in rows}:raise ValueError('Known historical ID overlap')
    if {r['query_id'] for r in manifest['cohorts']['train']}&{r['query_id'] for r in manifest['cohorts']['dev']}:
        raise ValueError('Development/held-out overlap')
    return manifest


def fetch_selected(split,ids):
    """Only convert frozen selected rows to Python; no model or answer-driven selection."""
    from huggingface_hub import HfApi,HfFileSystem
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    info=HfApi().dataset_info('Salesforce/ContextualBench',revision=REVISION,files_metadata=True)
    if info.sha!=REVISION:raise ValueError('2Wiki revision mismatch')
    rows={};fs=HfFileSystem()
    for entry in info.siblings:
        if not entry.rfilename.startswith('2WikiMultihopQA/'+split+'-'):continue
        with fs.open('datasets/Salesforce/ContextualBench@'+REVISION+'/'+entry.rfilename,'rb',block_size=8*1024*1024) as stream:
            table=pq.read_table(stream,columns=['_id','question','answer','context','supporting_facts'])
        selected=table.filter(pc.is_in(table['_id'],value_set=pa.array(ids))).to_pylist()
        for row in selected:
            if row['_id'] in rows:raise ValueError('Duplicate dataset query ID')
            rows[row['_id']]=row
    if set(rows)!=set(ids):raise ValueError('Missing frozen 2Wiki IDs')
    corpus={};queries=[]
    for qid in ids:
        row=rows[qid];titles={}
        for title,sentences in zip(row['context']['title'],row['context']['content']):
            text=' '.join(sentences);doc='2wikimultihopqa::'+title.strip().lower().replace(' ','_')+'::'+hashlib.sha1(text.encode()).hexdigest()[:10]
            titles[title]=doc;corpus.setdefault(doc,text)
        queries.append({'query_id':qid,'question':row['question'],'gold_answer':row['answer'],
            'gold_doc_ids':sorted({titles[t] for t in row['supporting_facts']['title'] if t in titles}),
            'gold_supporting_facts':[{'title':t,'sent_id':s} for t,s in zip(row['supporting_facts']['title'],row['supporting_facts']['sent_id'])]})
    return {'queries':queries,'corpus':[{'doc_id':d,'text':t} for d,t in corpus.items()]}


def verify_questions(data,records):
    if [q['query_id'] for q in data['queries']]!=[r['query_id'] for r in records]:raise ValueError('2Wiki ID ordering mismatch')
    for query,record in zip(data['queries'],records):
        if hashlib.sha256(query['question'].encode()).hexdigest()!=record['question_sha256']:raise ValueError('2Wiki question identity mismatch')


def metadata(scope,replication,dense,rcd):
    if replication.get('schema') not in (SCHEMA,LOCAL_SCHEMA):raise ValueError('Explicit new 2Wiki replication schema required')
    manifest=load_cohort(replication['cohort_manifest'],replication['cohort_manifest_sha256'])
    development=read_pinned(replication['development_data'],replication['development_data_sha256'])
    verify_questions(development,manifest['cohorts']['train'])
    selected=manifest['cohorts']['dev'] if scope=='heldout' else manifest['cohorts']['train'][:2]
    override={'dataset_loader':'load_2wikimultihopqa','dataset_split':'dev' if scope=='heldout' else 'train','dataset_revision':REVISION}
    dense={**dense,**override};rcd={**rcd,**override}
    if replication['schema']==LOCAL_SCHEMA:
        from scripts.run_week9_protocol_poison_matrix import model_binding
        for name,identity in [('embedder','BAAI/bge-small-en-v1.5'),('reranker','cross-encoder/ms-marco-MiniLM-L-6-v2')]:
            entry=replication['retrieval_snapshots'][name]
            if model_binding(entry['path'],identity)!=entry['binding']:raise ValueError('2Wiki retrieval snapshot mismatch')
        dense['embedder_model']=rcd['embedder_model']=replication['retrieval_snapshots']['embedder']['path']
        load_local(replication,scope,manifest)
    dense.pop('dataset_query_ids_manifest',None);rcd.pop('dataset_query_ids_manifest',None)
    from src.experiments.week9_construction import cells
    binding={'scope':scope,'query_ids':[r['query_id'] for r in selected],
        'dataset':{'loader':'load_2wikimultihopqa','revision':REVISION,'split':'dev' if scope=='heldout' else 'train'},
        'model_identity':rcd['generator_model'],'generator_backend':rcd['generator_backend'],
        'matrix':[list(c) for c in cells(scope)],'cohort_manifest_sha256':replication['cohort_manifest_sha256'],
        'development_artifact_sha256':replication['development_data_sha256'],
        'development_query_set_fingerprint':query_set_fingerprint(development['queries']),
        'complete_historical_nonoverlap_certified':False,
        'historical_exposure_risk':'unknown historical 25-query sweep; known 300 IDs excluded; not an untouched test set'}
    return binding,dense,rcd,[{k:q[k] for k in ('query_id','question','gold_answer')} for q in development['queries']]


def load_clean(value):
    replication=value['replication'];manifest=load_cohort(replication['cohort_manifest'],replication['cohort_manifest_sha256'])
    if replication['schema']==LOCAL_SCHEMA:return load_local(replication,value['binding']['scope'],manifest)
    if value['binding']['scope']=='development':
        complete=read_pinned(replication['development_data'],replication['development_data_sha256'])
        data={'corpus':complete['corpus'],'queries':complete['queries'][:2]}
        verify_questions(data,manifest['cohorts']['train'][:2])
        return data
    data=fetch_selected('dev',value['binding']['query_ids'])
    verify_questions(data,manifest['cohorts']['dev'])
    return data


def load_local(replication,scope,manifest):
    if replication['scope']!=scope:raise ValueError('Local 2Wiki input scope mismatch')
    data=read_pinned(replication['local_data'],replication['local_data_sha256'])
    expected=manifest['cohorts']['dev'] if scope=='heldout' else manifest['cohorts']['train']
    verify_questions(data,expected)
    from src.experiments.protocol import corpus_fingerprint
    if (query_set_fingerprint(data['queries'])!=replication['local_query_fingerprint'] or
        corpus_fingerprint(data['corpus'])!=replication['local_corpus_fingerprint']):raise ValueError('Local 2Wiki input fingerprint mismatch')
    return data if scope=='heldout' else {'corpus':data['corpus'],'queries':data['queries'][:2]}
