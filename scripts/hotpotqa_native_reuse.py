"""Read-only native HotpotQA adapter. All returned rows are PRIVATE.

Only verified manifests, journals, model bytes and explicit backend settings can
supply reusable rows. No model is imported/loaded here. Clean identities are
explicitly attack-neutral because a clean physical response predates assignment.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile
import io
from scripts.audit_e1_e2_reuse import digest, sha, binding_key, complete
from scripts import audit_hotpotqa_transfer_raw_offline as audit
from src.evaluation.qa_records import validate_qa, MEASUREMENT_SCHEMA, EXTRACTOR_VERSION
from src.experiments.protocol import corpus_fingerprint

CANDIDATE_PIN='97960932066b24f172fc566dd29808dc191cb85aa08cf995ffbd04c91d809f23'
ROOT=Path(__file__).resolve().parents[1]


def read(path):
    path=Path(path)
    if path.is_symlink():raise ValueError('Symlink native record')
    return json.loads(path.read_text())


def verify(root,snapshot):
    root,snapshot=Path(root),Path(snapshot)
    audit.require_pin(root/'execution/candidates/candidates.complete.json',CANDIDATE_PIN)
    receipt=audit.audit(root/'protocol.json',root/'execution/selection',root/'execution/evaluation',
                        root/'execution/aggregate.json',ROOT/'paper/results/hotpotqa_transfer_43f3f652460a/aggregate_public.json',root/'execution/candidates')
    spec=read(root/'protocol.json')
    if read(root/'execution/selection/selection.seal.json')['candidate_library_completion_sha256']!=CANDIDATE_PIN:
        raise ValueError('Candidate lineage mismatch')
    actual={p.relative_to(snapshot).as_posix():sha(p) for p in snapshot.rglob('*') if p.is_file()}
    if actual!=spec['model']['files_sha256'] or snapshot.name!=spec['model']['revision']:
        raise ValueError('Model snapshot mismatch')
    # Authenticate historical implementation from Git objects, without executing it.
    archive=subprocess.check_output(['git','archive',spec['source']['git_commit_sha'],'src','scripts','run.py'],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        files={m.name:tar.extractfile(m).read() for m in tar if m.isfile() and (m.name.endswith('.py') or m.name=='run.py')}
    hashes={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    if digest(hashes)!=spec['source']['code_fingerprint']:
        raise ValueError('Historical code fingerprint mismatch')
    critical=['src/pipelines/generator.py','src/retrieval/bm25.py','src/retrieval/dense.py',
              'src/retrieval/reranker.py','src/defenses/rcd/retriever.py','src/attacks/asr.py',
              'src/evaluation/qa_records.py','src/evaluation/metrics.py']
    for name in critical:
        if sha(ROOT/name)!=hashes[name]:raise ValueError('Historical core implementation differs')
    receipt['model_snapshot_verified']=True
    receipt['historical_code_verified']=True
    return spec,receipt


def backend_binding(spec):
    tokenfiles={k:v for k,v in spec['model']['files_sha256'].items() if not k.endswith('.safetensors') and not k.endswith('.index.json')}
    return dict(model_snapshot_sha256=digest(spec['model']),tokenizer_sha256=digest(tokenfiles),
                backend_environment=spec['environment'],
                generator_config={'backend':'mlx','model':spec['model']['repository'],'max_tokens':64,
                                  'generator_implementation_sha256':sha(ROOT/'src/pipelines/generator.py')},
                decoding={'temperature':0.,'sampler':'explicit greedy','qa_seed':42,'max_tokens':64},
                scoring={'schema':MEASUREMENT_SCHEMA,'extractor':EXTRACTOR_VERSION,'normalization':'squad-style/v1'})


def normalize(spec,query,choice,condition,config,corpus_sha,evidence,prompt,backend_prompt,observation_id):
    clean=condition=='clean'
    row={**backend_binding(spec),'observation_id':observation_id,'query_id':query['query_id'],
         'query_sha256':choice['query_fingerprint'],
         'target_assignment_sha256':digest('clean-no-attack' if clean else {'query':query['query_id'],'target':choice['target_answer']}),
         'candidate_sha256':digest('clean-no-poison' if clean else {'documents':choice['documents'],'target':choice['target_answer']}),
         'poison_corpus_sha256':corpus_sha,'retrieval_config':config,'retrieval_evidence':evidence,
         'prompt':prompt,'backend_prompt':backend_prompt}
    if not complete(row):raise ValueError('Incomplete normalized binding')
    return row


class NativeAdapter:
    def __init__(self,root,spec):
        self.root=Path(root);self.spec=spec
        self.evaluation=self.root/'execution/evaluation'
        self.origins={}
        self.scanned=False

    def scan_origins(self):
        if self.scanned:return
        for p in self.evaluation.joinpath('calls').rglob('*.response.json'):
            saved=read(p)
            if saved.get('execution',{}).get('backend_call_executed') is True:
                g=saved['generation'];validate_qa(g,g['extracted_answer'])
                if saved['generation_sha256']!=digest(g):raise ValueError('Corrupt physical generation')
                self.origins.setdefault(digest(g),[]).append(p)
        self.scanned=True

    def observation(self,cid,source,pipeline,query,choice,condition,measurement):
        """Resolve replay/cache provenance to a genuine completed physical call."""
        token=hashlib.sha256(query['query_id'].encode()).hexdigest()
        directory=self.evaluation/'calls'/cid/source/pipeline/token
        index=0 if condition=='clean' else 1
        intent=read(directory/f'{index:02d}.intent.json');saved=read(directory/f'{index:02d}.response.json')
        g=saved['generation'];validate_qa(g,g['extracted_answer'])
        if saved['request_fingerprint']!=digest(intent) or saved['generation_sha256']!=digest(g):
            raise ValueError('Native request/generation fingerprint mismatch')
        if intent['context'].get('query_id')!=query['query_id'] or intent['context'].get('condition')!=condition or intent['context'].get('pipeline')!=pipeline:
            raise ValueError('Native QA context mismatch')
        observed=measurement[condition+'_condition'];og=observed['generation']
        for key in ('prompt','backend_prompt','raw_response','extracted_answer'):
            if og[key]!=g[key]:raise ValueError('Measurement differs from journal')
        e=intent['effective']
        if e['model']!=self.spec['model'] or e['environment']!=self.spec['environment'] or e['qa_seed']!=42 or intent['max_tokens']!=64:
            raise ValueError('Native backend conditions mismatch')
        if e['decoding']!=self.spec['rules']['decoding']:raise ValueError('Native decoding mismatch')
        # Some measurements retain deeper diagnostic evidence. Match the
        # generator-visible IDs in their original order, never the diagnostic k.
        measured={d['doc_id']:d for d in observed['retrieved_evidence']}
        visible=[measured.get(doc_id) for doc_id in observed['generation_evidence_doc_ids']]
        if (len(measured)!=len(observed['retrieved_evidence']) or intent['prompt']!=g['prompt']
                or [{'doc_id':d['doc_id'],'text':d['text']} for d in intent['evidence']]!=visible
                or [d['doc_id'] for d in intent['evidence']]!=observed['generation_evidence_doc_ids']):
            raise ValueError('Native evidence/prompt mismatch')
        physical=directory/f'{index:02d}.response.json'
        if saved['execution']['kind']=='clean_cache_hit':
            entry=self.evaluation/'clean-cache'/(saved['execution']['cache_key']+'.json')
            cache=read(entry)
            if sha(entry)!=saved['execution']['cache_entry_sha256'] or cache['generation']!=saved['execution']['origin_generation']:
                raise ValueError('Clean cache origin mismatch')
            self.scan_origins()
            paths=self.origins.get(digest(cache['generation']),[])
            if not paths:raise ValueError('Unresolved physical clean origin')
            # Require full request-effective parity, not just identical answers.
            matches=[]
            for path in paths:
                oi=read(path.with_name(path.name.replace('.response.','.intent.')))
                if all(oi[k]==intent[k] for k in ('effective','prompt','max_tokens','evidence')):
                    matches.append(path)
            if not matches:raise ValueError('Cached physical backend binding differs')
            physical=min(matches)
        elif saved['execution'].get('backend_call_executed') is not True:
            raise ValueError('Unverified physical backend execution')
        row=normalize(self.spec,query,choice,condition,e['retriever_config'],e['corpus_fingerprint'],
                      intent['evidence'],g['prompt'],g['backend_prompt'],
                      digest([cid,source,pipeline,query['query_id'],condition]))
        row.update(provenance='physical_completed',physical_call_id=digest(['native-evaluation',sha(physical),physical.relative_to(self.evaluation).as_posix()]),
                   raw_response=g['raw_response'],native_observation_id=physical.relative_to(self.evaluation).as_posix(),generation=g)
        return row
