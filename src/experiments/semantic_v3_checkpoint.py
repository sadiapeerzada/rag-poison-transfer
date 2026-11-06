"""Write-once, fsynced atomic records and call-level exact replay.

No model loader. A persisted intent without a durable response is ambiguous and
blocks automatic resume. Exactly-once external calls cannot be inferred after a
crash; never regenerate such calls to fill the gap.
"""
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import json
import os
from pathlib import Path
import tempfile

from src.attacks.semantic_quality_targets_v3 import digest
from src.pipelines.generator import GenerationResult


class ResumeBlocked(RuntimeError):
    pass


def publish_json(path, value):
    path = Path(path)
    if path.is_symlink() or path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd,'w') as sink:
            json.dump(value,sink,sort_keys=True,ensure_ascii=False,allow_nan=False)
            sink.write('\n');sink.flush();os.fsync(sink.fileno())
        os.chmod(tmp,0o444)
        os.link(tmp,path)  # Atomic publication without overwrite, including races.
        directory = os.open(path.parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        os.unlink(tmp)


def atomic_record(path, payload):
    publish_json(path, {'payload':payload, 'sha256':digest(payload)})


def read_record(path):
    path=Path(path)
    if path.is_symlink():raise ValueError('Symlink checkpoint forbidden')
    value=json.loads(path.read_text())
    if value['sha256']!=digest(value['payload']):raise ValueError('Checkpoint checksum mismatch')
    return value['payload']


@contextmanager
def writer_lock(root):
    path=Path(root)/'.writer.lock'
    if path.is_symlink():raise ValueError('Symlink lock forbidden')
    with path.open('a') as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:raise ResumeBlocked('Another writer is active') from exc
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


class CallJournal:
    """Wrap a lazy backend; cache every actual call before V3 validation.

    Replay validates request bytes, token cap, seed and pinned model provenance.
    Errors count against the budget and remain infrastructure errors forever.
    """
    def __init__(self, root, context, backend_factory, *, limit=200, interrupt=None, before_call=None, after_call=None):
        if type(limit) is not int or not 1<=limit<=200:raise ValueError('Invalid backend call limit')
        self.root=Path(root);self.context=context;self.factory=backend_factory
        self.limit=limit;self.backend=None;self.seed=None;self.cell=None;self.ordinal=0;self.interrupt=interrupt
        self.model_provenance=context['model_provenance']
        self.before_call=before_call;self.after_call=after_call

    def start_cell(self, cell):self.cell=cell;self.ordinal=0
    def set_seed(self, seed):self.seed=seed

    def generate(self, prompt, max_tokens):
        if self.cell is None or self.seed is None:raise ValueError('Missing cell/seed')
        if max_tokens!=150:raise ValueError('Token budget mismatch')
        key=f'{self.cell}.{self.ordinal:03d}';self.ordinal+=1
        folder=self.root/'calls';intent=folder/(key+'.intent.json');response=folder/(key+'.response.json');error=folder/(key+'.error.json')
        request={'prompt':prompt,'max_tokens':max_tokens,'seed':self.seed,'context':self.context}
        if intent.exists():
            saved_request=read_record(intent)
            if {k:v for k,v in saved_request.items() if k!='admission'}!=request:
                raise ResumeBlocked('Replay request differs from durable intent')
            request=saved_request
            if error.exists():raise ResumeBlocked('Recorded infrastructure error requires independent resolution; no retry')
            if not response.exists():raise ResumeBlocked('Unresolved backend-call intent; no regeneration')
            cached=read_record(response)
            if cached['request_sha256']!=digest(request):raise ValueError('Cached response binding mismatch')
            return GenerationResult(**cached['result'])
        if response.exists() or error.exists():raise ResumeBlocked('Orphaned response/error')
        count=len(list(folder.glob('*.intent.json')))
        if count>=self.limit:raise ResumeBlocked('Backend-call budget exhausted')
        # No reservation, factory creation or backend seeding before admission.
        if self.before_call is not None:
            request['admission']=self.before_call(count)
        atomic_record(intent,request)
        if self.interrupt:self.interrupt('after_intent',key)
        result=None
        try:
            if self.backend is None:
                self.backend=self.factory()
                if self.backend.model_provenance!=self.model_provenance:raise ValueError('Backend provenance mismatch')
            prepare=getattr(self.backend,'prepare',None)
            if prepare is not None:prepare()
            self.backend.set_runtime_seed(self.seed)
            # Loading can take time/change pressure. Recheck immediately before
            # generation as well as before reservation. A late denial is saved
            # as an explicit error and cannot silently replay or reclaim a slot.
            call_admission=self.before_call(count) if self.before_call is not None else None
            result=self.backend.generate(prompt,max_tokens=max_tokens)
            if not isinstance(result,GenerationResult) or not isinstance(result.text,str) or not isinstance(result.backend_prompt,str):
                raise ValueError('Complete typed raw response/backend prompt required')
            atomic_record(response,{'request_sha256':digest(request),'result':asdict(result),
                                    'call_admission':call_admission})
        except Exception as exc:
            atomic_record(error,{'request_sha256':digest(request),'error_type':type(exc).__name__,'message':str(exc),'kind':'infrastructure_error',
                'available_result':asdict(result) if isinstance(result,GenerationResult) else None})
            raise
        if self.interrupt:self.interrupt('after_response',key)
        if self.after_call is not None:self.after_call(key,count+1)
        return result


def verify_journal(root):
    journal_admission(root)
    folder=Path(root)/'calls'
    for intent in folder.glob('*.intent.json'):
        request=read_record(intent);key=intent.name.removesuffix('.intent.json')
        error=folder/(key+'.error.json');response=folder/(key+'.response.json')
        if error.exists() or not response.exists():raise ResumeBlocked('Unresolved or failed call; manual review required')
        if read_record(response)['request_sha256']!=digest(request):raise ValueError('Journal binding mismatch')
    for error in folder.glob('*.error.json'):
        raise ResumeBlocked('Infrastructure error journal requires independent resolution')
    for response in folder.glob('*.response.json'):
        if not (folder/(response.name.removesuffix('.response.json')+'.intent.json')).exists():
            raise ResumeBlocked('Orphaned journal response')
    return len(list(folder.glob('*.intent.json')))


def journal_admission(root):
    """Filename-only recovery guard, safe before query/corpus admission."""
    root=Path(root);folder=root/'calls'
    if root.is_symlink():raise ResumeBlocked('Symlink namespace forbidden')
    for path in root.rglob('*'):
        if path.is_symlink():raise ResumeBlocked('Symlink checkpoint forbidden')
        if path.name.startswith('.pending-'):
            raise ResumeBlocked('Unpublished atomic record; manual review required')
    intents=list(folder.glob('*.intent.json'))
    for intent in intents:
        key=intent.name.removesuffix('.intent.json')
        if (folder/(key+'.error.json')).exists() or not (folder/(key+'.response.json')).exists():
            raise ResumeBlocked('Unresolved or failed call; manual review required')
    for path in folder.glob('*.error.json'):
        raise ResumeBlocked('Infrastructure error journal requires independent resolution')
    for path in folder.glob('*.response.json'):
        if not (folder/(path.name.removesuffix('.response.json')+'.intent.json')).exists():
            raise ResumeBlocked('Orphaned journal response')
    if len(intents)>200:raise ResumeBlocked('Persisted call budget exceeded')
    return len(intents)
