#!/usr/bin/env python3
"""Separate protocol-based Week 9 entrypoint. No human approval downgrade path.

preflight -> freeze-protocol -> construct (all cells) -> externally pinned seal
-> evaluate -> aggregate. No command implicitly executes the next stage.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from run import build_generator, load_dataset
from scripts import run_week9_heldout_poison_matrix as legacy
from scripts.run_week9_matched_poison_comparison import build_matched_retrievers, evaluate_pipeline, validated_top_k
from scripts.audit_phase4d_development_coverage import DEFAULT_ARTIFACT, PINNED_ARTIFACT_SHA256
from scripts.extract_verified_development_queries import extract_verified
from src.attacks.reviewed_target_artifact import read_pinned
from src.attacks import semantic_profiles
from src.evaluation.qa_records import capture_generation, validate_qa
from src.pipelines.generator import GenerationResult, MLXGenerator
from src.experiments.protocol import corpus_fingerprint, query_set_fingerprint
from src.experiments import week9_construction as protocol
from src.utils.seeding import set_seed

PROTOCOL_SCHEMA = "rag-poison-transfer.week9-frozen-construction-protocol/v1"
REPLICATION_PROTOCOL_SCHEMA = "rag-poison-transfer.2wiki-frozen-construction-protocol/v1"
SEAL_SCHEMA = "rag-poison-transfer.week9-complete-construction-seal/v1"
EVALUATION_SCHEMA = "rag-poison-transfer.week9-protocol-evaluation/v1"
CORRECTED_DEVELOPMENT_PROTOCOL_SCHEMA = "rag-poison-transfer.semantic-development-protocol/v2"
DEVELOPMENT_STUDY_PROTOCOL_SCHEMA = "rag-poison-transfer.semantic-development-protocol/v1"
PROFILE_PROTOCOL_SCHEMA = "rag-poison-transfer.week9-profiled-construction-protocol/v1"
RELIABLE_REPLICATION_SCHEMA = "rag-poison-transfer.2wiki-frozen-construction-protocol/v2"
from src.experiments import execution_reliability as reliable

AGGREGATE_SCHEMA = "rag-poison-transfer.week9-protocol-aggregate/v1"
DEV_IDS = ("5ae2c416554299492dc91c67", "5ae143ed55429920d5234360")
PACKAGES = ("mlx", "mlx-lm", "transformers", "sentence-transformers", "datasets", "numpy", "torch")


def sha(path):
    # Model snapshots contain multi-GB files; never duplicate a whole weight file in RAM.
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def write(path, value):
    path = Path(path)
    if path.exists():
        raise FileExistsError("Never overwrite frozen/checkpoint/output artifacts: " + str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    legacy._write_json_atomic(path,value)


def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()


def code_binding():
    if git("status","--porcelain","--untracked-files=all"):
        raise ValueError("Protocol execution requires a clean committed checkout")
    paths = [p for p in git("ls-files").splitlines() if
             (p.startswith(("src/","scripts/")) and p.endswith(".py")) or p == "run.py"]
    return {"git_commit_sha":git("rev-parse","HEAD"),
            "code_fingerprint":protocol.fingerprint({p:sha(ROOT/p) for p in paths})}


def environment():
    values = {"python":sys.version}
    for name in PACKAGES:
        try:
            values[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            values[name] = None
    return values


def metadata(scope):
    dense,rcd,ids,ids_fp,hashes = legacy.validate_frozen_inputs(
        heldout_path=ROOT/legacy.DEFAULT_HELDOUT_MANIFEST,
        dense_config_path=ROOT/legacy.DEFAULT_DENSE_CONFIG, rcd_config_path=ROOT/legacy.DEFAULT_RCD_CONFIG)
    if sha(ROOT/DEFAULT_ARTIFACT) != PINNED_ARTIFACT_SHA256:
        raise ValueError("Pinned development artifact mismatch")
    development, provenance = extract_verified(ROOT/DEFAULT_ARTIFACT,ROOT/legacy.DEFAULT_HELDOUT_MANIFEST)
    if scope not in {"development","heldout"} or len(ids) != 300 or set(DEV_IDS) & set(ids):
        raise ValueError("Invalid cohort/scope or development overlap")
    binding = {"scope":scope,"query_ids":ids if scope == "heldout" else list(DEV_IDS),
        "heldout_manifest_fingerprint":ids_fp, "config_sha256":hashes,
        "development_artifact_sha256":PINNED_ARTIFACT_SHA256,
        "development_query_set_fingerprint":provenance["development_query_set_fingerprint"],
        "dataset":{"loader":rcd["dataset_loader"],"revision":rcd["dataset_revision"],"split":rcd["dataset_split"]},
        "model_identity":rcd["generator_model"], "generator_backend":rcd["generator_backend"],
        "matrix":[list(c) for c in protocol.cells(scope)]}
    return binding,dense,rcd,development


def model_binding(snapshot, identity):
    snapshot = Path(snapshot).expanduser().resolve()
    if (not re.fullmatch(r"[0-9a-f]{40}",snapshot.name) or snapshot.parent.name != "snapshots" or
        snapshot.parent.parent.name != "models--" + identity.replace("/","--")):
        raise ValueError("Model snapshot must be the cached 40-hex revision of the configured repository")
    files = {p.relative_to(snapshot).as_posix():sha(p) for p in sorted(snapshot.rglob("*")) if p.is_file()}
    if not files or "config.json" not in files or not any(p.endswith(".safetensors") for p in files):
        raise ValueError("Complete local model weights/config snapshot required")
    return {"repository":identity,"revision":snapshot.name,"files_sha256":files}


def context_metadata(scope,replication=None):
    if replication is None:
        return metadata(scope)
    from src.experiments.twowiki_replication import metadata as replication_metadata
    _,dense,rcd,_ = metadata("heldout")
    result = replication_metadata(scope,replication,dense,rcd)
    result[0]["config_sha256"] = {"dense":protocol.fingerprint(result[1]),"rcd":protocol.fingerprint(result[2]),
        "base_dense":sha(ROOT/legacy.DEFAULT_DENSE_CONFIG),"base_rcd":sha(ROOT/legacy.DEFAULT_RCD_CONFIG)}
    return result


def study_context(scope,replication,study=None,profile=None):
    if study is not None:
        from src.experiments import semantic_development_study as devstudy
        devstudy.validate(study,scope,replication,profile)
    binding,dense,rcd,development=context_metadata(scope,replication)
    if study is not None:
        full=read_pinned(replication["local_data"],replication["local_data_sha256"])
        manifest=read_pinned(replication["cohort_manifest"],replication["cohort_manifest_sha256"])
        binding=devstudy.bind(binding,full,manifest)
    return binding,dense,rcd,development


def study_fields(value):
    return {"development_study":value["development_study"]} if "development_study" in value else {}


def target_fields(value):
    return {"target_method":value["target_method"]} if "target_method" in value else {}


def validate_target_method(value,scope,study,profile):
    if value is not None:
        from src.attacks.development_targets_v5 import method_module
        method_module(value.get("identifier")).validate(value,scope)
        if study is None or profile is None or profile["identifier"] not in semantic_profiles.DEVELOPMENT_IDENTIFIERS:
            raise ValueError("Corrected target method requires a separate development study/profile")


def manifest_fields(value):
    return {**profile_fields(value),**study_fields(value),**target_fields(value)}


def validation_kwargs(value):
    return {**profile_kwargs(value),**study_fields(value)}


def declared_cells(value):
    return [tuple(c) for c in value["development_study"]["matrix"]] if "development_study" in value else protocol.cells(value["binding"]["scope"])


def profile_fields(value):
    return {"semantic_profile":value["semantic_profile"]} if "semantic_profile" in value else {}


def profile_kwargs(value):
    return {**profile_fields(value),**target_fields(value),"scope":value["binding"]["scope"]} if "semantic_profile" in value else {}


def profile_provenance(value):
    return {**({"semantic_profile_sha256":protocol.fingerprint(value["semantic_profile"])} if "semantic_profile" in value else {}),
        **({"development_study_sha256":protocol.fingerprint(value["development_study"])} if "development_study" in value else {}),
        **({"target_method_sha256":protocol.fingerprint(value["target_method"])} if "target_method" in value else {})}


def frozen_rules(replication=None,profile=None,target_method=None):
    rules=protocol.rules()
    if replication is not None:rules={**rules,"dataset_replication":"risk-disclosed-2wiki/v1"}
    if profile is not None:
        rules={**rules,"semantic_profile":profile["identifier"],"semantic_prompt":profile["prompt_version"],
            "semantic_validator":profile["validation_version"],"retry_policy":profile["retry_policy"]}
    if target_method is not None:rules={**rules,"target_method":target_method["identifier"]}
    return rules


def freeze_protocol(output, scope, snapshot,replication=None,semantic_profile=None,development_study=None,target_method=None):
    legacy._ensure_output_outside_repository(Path(output).parent)
    profile=semantic_profiles.descriptor(semantic_profile,scope) if semantic_profile is not None else None
    study=None
    if development_study is not None:
        from src.experiments.semantic_development_study import descriptor
        study=descriptor(development_study)
    method=None
    if target_method is not None:
        from src.attacks.development_targets_v5 import method_module
        method=method_module(target_method).descriptor(target_method)
    validate_target_method(method,scope,study,profile)
    binding,*_ = study_context(scope,replication,study,profile)
    installed = environment()
    if any(v is None for v in installed.values()):
        raise ValueError("All frozen runtime dependencies must be installed before protocol freeze")
    rules = frozen_rules(replication,profile,method)
    value = {"schema":REPLICATION_PROTOCOL_SCHEMA if replication is not None else PROTOCOL_SCHEMA,"rules":rules,"binding":binding,
        "source":code_binding(),"environment":installed,"model":model_binding(snapshot,binding["model_identity"])}
    if replication is not None:
        value["replication"] = replication
        if replication.get("schema")=="rag-poison-transfer.2wiki-replication-inputs/v2":
            value["schema"]=RELIABLE_REPLICATION_SCHEMA
            value["execution"]=dict(reliable.DEFAULTS)
            value["planned_outputs"]=reliable.planned_outputs(output,"2wiki")
    if profile is not None:
        value.update(schema=PROFILE_PROTOCOL_SCHEMA,semantic_profile=profile)
    if study is not None:value.update(schema=DEVELOPMENT_STUDY_PROTOCOL_SCHEMA,development_study=study)
    if method is not None:value.update(schema=CORRECTED_DEVELOPMENT_PROTOCOL_SCHEMA,target_method=method)
    write(output,value)
    return {"protocol_sha256":sha(output),"scope":scope,"status":"protocol_frozen_no_construction_or_evaluation"}


def load_protocol(path,digest,snapshot=None):
    value = read_pinned(path,digest)
    replication = value.get("replication")
    local = replication is not None and replication.get("schema")=="rag-poison-transfer.2wiki-replication-inputs/v2"
    expected_schema = RELIABLE_REPLICATION_SCHEMA if local else REPLICATION_PROTOCOL_SCHEMA if replication is not None else PROTOCOL_SCHEMA
    if local and value.get("execution")!=reliable.DEFAULTS:raise ValueError("Execution protocol mismatch")
    profile=value.get("semantic_profile")
    if "semantic_profile" in value:
        semantic_profiles.validate(profile,value["binding"]["scope"])
        expected_schema=PROFILE_PROTOCOL_SCHEMA
    if "development_study" in value:
        from src.experiments.semantic_development_study import validate
        validate(value["development_study"],value["binding"]["scope"],replication,profile)
        expected_schema=DEVELOPMENT_STUDY_PROTOCOL_SCHEMA
    method=value.get("target_method")
    if "target_method" in value:
        if method is None:raise ValueError("Missing target method descriptor")
        validate_target_method(method,value["binding"]["scope"],value.get("development_study"),profile)
        expected_schema=CORRECTED_DEVELOPMENT_PROTOCOL_SCHEMA
    expected_rules = frozen_rules(replication,profile,method)
    if value.get("schema") != expected_schema or value.get("rules") != expected_rules:
        raise ValueError("Protocol version/rules mismatch")
    binding,dense,rcd,development = study_context(value["binding"]["scope"],replication,value.get("development_study"),profile)
    if value["binding"] != binding or value["source"] != code_binding() or value["environment"] != environment():
        raise ValueError("Protocol source/config/dataset/environment provenance mismatch")
    if snapshot is not None and value["model"] != model_binding(snapshot,binding["model_identity"]):
        raise ValueError("Model snapshot bytes/revision mismatch")
    return value,dense,rcd,development


def load_clean(value,rcd):
    if "development_study" in value:
        replica=value["replication"]
        full=read_pinned(replica["local_data"],replica["local_data_sha256"])
        by_id={q["query_id"]:q for q in full["queries"]}
        clean={"corpus":full["corpus"],"queries":[by_id[qid] for qid in value["binding"]["query_ids"]]}
        if query_set_fingerprint(clean["queries"])!=value["binding"]["study_query_set_fingerprint"]:
            raise ValueError("Development study query fingerprint mismatch")
        return clean
    if value.get("replication") is not None:
        from src.experiments.twowiki_replication import load_clean as replication_clean
        return replication_clean(value)
    selected = dict(rcd)
    if value["binding"]["scope"] == "development":
        selected.pop("dataset_query_ids_manifest",None)
        selected.update(dataset_query_ids=list(DEV_IDS),dataset_n_samples=None)
    else:
        selected["dataset_query_ids_manifest"] = str(ROOT/legacy.DEFAULT_HELDOUT_MANIFEST)
    clean = load_dataset(selected)
    if [q["query_id"] for q in clean["queries"]] != value["binding"]["query_ids"]:
        raise ValueError("Loaded cohort differs from frozen IDs/order")
    if value["binding"]["scope"] == "development":
        original = {r["query_id"]:r for r in (json.loads(s) for s in (ROOT/DEFAULT_ARTIFACT).read_text().splitlines())}
        for q in clean["queries"]:
            if any(q[k] != original[q["query_id"]][k] for k in ("question","gold_answer","gold_doc_ids")):
                raise ValueError("Development question/gold/document identity mismatch")
    return clean


def runtime_seed(seed):
    set_seed(seed)
    import mlx.core as mx
    mx.random.seed(seed)


def generator(rcd,snapshot):
    reliable.acquire_model_lease()
    # Explicit greedy sampler, never library-default sampling. Config files stay frozen.
    from mlx_lm.sample_utils import make_sampler
    backend = build_generator({**rcd,"generator_model":str(Path(snapshot).resolve())})
    if not isinstance(backend,MLXGenerator):
        raise ValueError("Frozen real MLX backend required")
    original = backend._generate_fn
    sampler = make_sampler(temp=0.0)
    backend._generate_fn = lambda *a,**kw: original(*a,**kw,sampler=sampler)
    return backend


class JournalGenerator:
    """Replay exact recorded responses; an interrupted/failed call is never resampled."""
    def __init__(self,backend,directory,provenance):
        self.backend,self.directory,self.model_provenance = backend,Path(directory),provenance
        self.index = 0
        self.context = {}

    def set_observation_context(self,context):
        self.context = dict(context)

    def generate(self,prompt,max_tokens):
        index,self.index = self.index,self.index+1
        request = {"prompt":prompt,"max_tokens":max_tokens,"provenance":self.model_provenance,"context":self.context}
        intent = self.directory/f"{index:02d}.intent.json"
        response = self.directory/f"{index:02d}.response.json"
        if response.exists() and not intent.exists():
            raise RuntimeError("Orphan generation response; refuse new generation without its original intent")
        if intent.exists():
            if json.loads(intent.read_text()) != request:
                raise ValueError("Generation checkpoint prompt/provenance mismatch")
            if not response.exists():
                raise RuntimeError("Indeterminate interrupted generation; do not retry or silently extend budget")
            saved = json.loads(response.read_text())
            if saved.get("request_fingerprint") != protocol.fingerprint(request) or "error" in saved:
                raise RuntimeError("Failed/inconsistent backend checkpoint; construction remains incomplete")
            record = saved["generation"]
            validate_qa(record,record["extracted_answer"])
            if record["prompt"] != prompt or ("generation_sha256" in saved and saved["generation_sha256"] != protocol.fingerprint(record)):
                raise ValueError("Generation checkpoint response integrity mismatch")
            return GenerationResult(record["raw_response"],record["generator_latency_seconds"],
                record["prompt_tokens"],record["completion_tokens"],record.get("backend_prompt"))
        write(intent,request)
        try:
            result,record = capture_generation(self.backend,prompt,max_tokens)
            validate_qa(record,record["extracted_answer"])
        except Exception as error:
            write(response,{"request_fingerprint":protocol.fingerprint(request),"error_type":type(error).__name__,"error":str(error)})
            raise
        write(response,{"request_fingerprint":protocol.fingerprint(request),"generation":record,"generation_sha256":protocol.fingerprint(record)})
        return result


def validate_generation_journal(directory,expected):
    directory = Path(directory)
    paths = sorted(p.name for p in directory.glob("*") if p.is_file())
    required = sorted(f"{i:02d}.{kind}.json" for i in range(len(expected)) for kind in ("intent","response"))
    if paths != required:
        raise ValueError("Generation journal missing or exceeding frozen call budget")
    for i,(request,observed) in enumerate(expected):
        intent = json.loads((directory/f"{i:02d}.intent.json").read_text())
        saved = json.loads((directory/f"{i:02d}.response.json").read_text())
        if intent != request or saved.get("request_fingerprint") != protocol.fingerprint(request) or "error" in saved:
            raise ValueError("Generation journal request/provenance mismatch")
        actual = saved["generation"]
        validate_qa(actual,actual["extracted_answer"])
        if "generation_sha256" in saved and saved["generation_sha256"] != protocol.fingerprint(actual):
            raise ValueError("Generation journal response integrity mismatch")
        if any(actual.get(k) != v for k,v in observed.items() if k != "elapsed_seconds"):
            raise ValueError("Generated response differs from frozen attempt/evaluation record")


def construction_journals(root,cell,value,digest):
    identity = protocol.cell_id(cell["family"],cell["intensity"],cell["seed"])
    for row in cell["records"]:
        key = hashlib.sha256(row["query_id"].encode()).hexdigest()
        if json.loads((root/identity/"queries"/(key+".json")).read_text()) != row:
            raise ValueError("Terminal query checkpoint differs from sealed cell ledger")
        provenance = {"protocol_sha256":digest,"family":cell["family"],"intensity":cell["intensity"],
                      "seed":cell["seed"],"query_id":row["query_id"],"model":value["model"],
                      "decoding":value["rules"]["decoding"],**profile_provenance(value)}
        expected = []
        for entry in row["attempt_records"]:
            for event in entry["attempts"]:
                if event.get("model_provenance") != provenance:
                    raise ValueError("Semantic attempt model/source provenance mismatch")
                expected.append(({"prompt":event["prompt"],"max_tokens":150,"provenance":provenance,"context":{}},
                                 {"raw_response":event["generated_text"],"prompt":event["prompt"],
                                  "backend_prompt":event["backend_prompt"]}))
        validate_generation_journal(root/identity/"generation"/key,expected)


def make_cell(clean,family,intensity,seed,digest,records,semantic_profile=None,development_study=None,target_method=None):
    return {"schema":protocol.CELL_SCHEMA,"protocol_sha256":digest,"family":family,"intensity":intensity,"seed":seed,
        "query_set_fingerprint":query_set_fingerprint(clean["queries"]),
        "clean_corpus_fingerprint":corpus_fingerprint(clean["corpus"]),"records":records,
        **({"semantic_profile":semantic_profile} if semantic_profile is not None else {}),
        **({"development_study":development_study} if development_study is not None else {}),
        **({"target_method":target_method} if target_method is not None else {})}


def construction_files(root):
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError("Construction directory may not contain symlinks")
        if p.is_file() and p != root/"construction.seal.json":
            files[p.relative_to(root).as_posix()] = sha(p)
    return files


@reliable.exclusive("root")
def construct(path,digest,root,snapshot,max_batches=None):
    root = legacy._ensure_output_outside_repository(Path(root))
    if (root/"construction.seal.json").exists():
        raise ValueError("Already sealed: construction cannot be reopened")
    value,dense,rcd,development = load_protocol(path,digest,snapshot)
    reliable.require_output(value,"construction",root)
    clean = load_clean(value,rcd)
    plan = {"protocol_sha256":digest,"binding":value["binding"],"source":value["source"],**manifest_fields(value),
        "query_set_fingerprint":query_set_fingerprint(clean["queries"]),"clean_corpus_fingerprint":corpus_fingerprint(clean["corpus"])}
    planpath = root/"construction.plan.json"
    if planpath.exists():
        if json.loads(planpath.read_text()) != plan:
            raise ValueError("Construction recovery provenance mismatch")
    else:
        if root.exists() and any(root.iterdir()):
            raise ValueError("Fresh or matching construction root required")
        write(planpath,plan)
    # Refuse unknown/invalid prior calls before loading a model or nominating a target.
    reliable.validate_store(root)
    backend = None
    batch_budget = reliable.BatchBudget(max_batches)
    batch_size = value.get("execution",reliable.DEFAULTS)["batch_size"]
    entries = {}
    for family,intensity,seed in declared_cells(value):
        identity = protocol.cell_id(family,intensity,seed)
        cellpath = root/identity/"construction.json"
        if cellpath.exists():
            cell = json.loads(cellpath.read_text())
        else:
            records = []
            for ordinal,query in enumerate(clean["queries"]):
                if ordinal % batch_size == 0:
                    batch_queries=clean["queries"][ordinal:ordinal+batch_size]
                    if any(not (root/identity/"queries"/(hashlib.sha256(q["query_id"].encode()).hexdigest()+".json")).exists() for q in batch_queries):
                        batch_budget.begin()
                if code_binding() != value["source"]:
                    raise ValueError("Source changed during construction")
                checkpoint = root/identity/"queries"/(hashlib.sha256(query["query_id"].encode()).hexdigest()+".json")
                if checkpoint.exists():
                    record = json.loads(checkpoint.read_text())
                else:
                    target,_ = protocol.select_target(query,development,seed,**({**target_fields(value),"scope":value["binding"]["scope"]} if "target_method" in value else {}))
                    if family == protocol.ATTACKS[1] and target is not None and backend is None:
                        backend = generator(rcd,snapshot)
                    recorded = JournalGenerator(backend,root/identity/"generation"/hashlib.sha256(query["query_id"].encode()).hexdigest(),
                        {"protocol_sha256":digest,"family":family,"intensity":intensity,"seed":seed,
                         "query_id":query["query_id"],"model":value["model"],"decoding":value["rules"]["decoding"],**profile_provenance(value)})
                    record = protocol.construct_query(query,development,family,intensity,seed,recorded,set_runtime_seed=runtime_seed,**profile_kwargs(value))
                    write(checkpoint,record)
                mini = {"queries":[query],"corpus":clean["corpus"]}
                protocol.validate_cell(make_cell(mini,family,intensity,seed,digest,[record],**manifest_fields(value)),mini,development,digest,**validation_kwargs(value))
                records.append(record)
            cell = make_cell(clean,family,intensity,seed,digest,records,**manifest_fields(value))
            protocol.validate_cell(cell,clean,development,digest,**validation_kwargs(value))
            write(cellpath,cell)
        protocol.validate_cell(cell,clean,development,digest,**validation_kwargs(value))
        construction_journals(root,cell,value,digest)
        entries[identity] = {"path":str(cellpath.relative_to(root)),"sha256":sha(cellpath)}
    load_protocol(path,digest,snapshot)  # Recheck source/config/environment/weights at the barrier.
    seal = {"schema":SEAL_SCHEMA,"protocol_sha256":digest,"scope":value["binding"]["scope"],
        "plan":plan,"cells":entries,"files_sha256":construction_files(root)}
    write(root/"construction.seal.json",seal)
    return {"status":"all_construction_frozen_no_evaluation", "construction_seal_sha256":sha(root/"construction.seal.json")}


def load_sealed(path,digest,root,seal_digest):
    value,dense,rcd,development = load_protocol(path,digest)
    root = Path(root).resolve()
    seal = read_pinned(root/"construction.seal.json",seal_digest)
    if (seal.get("schema") != SEAL_SCHEMA or seal.get("protocol_sha256") != digest or
        seal.get("scope") != value["binding"]["scope"] or seal.get("files_sha256") != construction_files(root)):
        raise ValueError("Global construction seal/protocol/file integrity mismatch")
    expected = {protocol.cell_id(*c) for c in declared_cells(value)}
    if set(seal.get("cells",{})) != expected:
        raise ValueError("Complete declared matrix must be frozen before evaluation")
    clean = load_clean(value,rcd)
    expected_plan = {"protocol_sha256":digest,"binding":value["binding"],"source":value["source"],**manifest_fields(value),
        "query_set_fingerprint":query_set_fingerprint(clean["queries"]),
        "clean_corpus_fingerprint":corpus_fingerprint(clean["corpus"])}
    if seal["plan"] != expected_plan or json.loads((root/"construction.plan.json").read_text()) != expected_plan:
        raise ValueError("Sealed dataset/query/corpus fingerprint mismatch")
    cells = {}
    for family,intensity,seed in declared_cells(value):
        identity = protocol.cell_id(family,intensity,seed)
        entry = seal["cells"][identity]
        expected_path = f"{identity}/construction.json"
        if entry.get("path") != expected_path or entry.get("sha256") != sha(root/expected_path):
            raise ValueError("Cell seal identity mismatch")
        cell = json.loads((root/expected_path).read_text())
        if (cell.get("family"),cell.get("intensity"),cell.get("seed")) != (family,intensity,seed):
            raise ValueError("Cell matrix identity mismatch")
        cells[identity] = protocol.validate_cell(cell,clean,development,digest,**validation_kwargs(value))
        construction_journals(root,cell,value,digest)
    return value,dense,rcd,clean,cells


def evaluate(path,digest,root,seal_digest,output,snapshot,max_batches=None):
    # Validate EVERY cell and the complete seal BEFORE constructing any QA backend/retriever.
    value,dense,rcd,clean,cells = load_sealed(path,digest,root,seal_digest)
    if model_binding(snapshot,value["binding"]["model_identity"]) != value["model"]:
        raise ValueError("Evaluation model weights differ from frozen protocol")
    if "execution" in value:
        return reliable.evaluate_replication(path,digest,root,seal_digest,output,snapshot,value,dense,rcd,clean,cells,max_batches)
    output = legacy._ensure_output_outside_repository(Path(output))
    if output == Path(root).resolve() or Path(root).resolve() in output.parents or output.exists():
        raise ValueError("Fresh evaluation directory outside construction root required")
    output.mkdir(parents=True)
    write(output/"evaluation.plan.json",{"schema":EVALUATION_SCHEMA,"protocol_sha256":digest,
        "construction_seal_sha256":seal_digest,"source":value["source"],"scope":value["binding"]["scope"]})
    backend = None
    for identity,cell in cells.items():
        if code_binding() != value["source"]:
            raise ValueError("Source changed during evaluation")
        poisoned = protocol.replay(clean,cell)
        selected = {q["query_id"] for q in poisoned["queries"]}
        valid_clean = {"corpus":clean["corpus"],"queries":[q for q in clean["queries"] if q["query_id"] in selected]}
        paired = {"dense":{},"rcd":{}}
        if selected:
            if backend is None:
                backend = generator(rcd,snapshot)
            retrievers = build_matched_retrievers(dense,rcd,valid_clean,poisoned)
            observed = JournalGenerator(backend,output/identity/"generation",{
                "protocol_sha256":digest,"construction_seal_sha256":seal_digest,
                "model":value["model"],"decoding":value["rules"]["decoding"],"stage":"qa"})
            for arm,(clean_retriever,poisoned_retriever) in retrievers.items():
                runtime_seed(42)
                cfg = dense if arm == "dense" else rcd
                observations = evaluate_pipeline(pipeline=arm,clean_retriever=clean_retriever,
                    poisoned_retriever=poisoned_retriever,clean_data=valid_clean,poisoned_data=poisoned,
                    generator=observed,top_k=validated_top_k(cfg,arm),max_tokens=int(cfg["max_tokens"]))
                paired[arm] = {r["query_id"]:r for r in observations}
        rows = [{"schema":protocol.ROW_SCHEMA,"construction_seal_sha256":seal_digest,
                 "cell_fingerprint":protocol.fingerprint(cell),"pipeline":arm,"query_id":r["query_id"],
                 "construction_status":r["status"],"evaluation_status":"evaluated" if r["status"] == protocol.VALID else "not_evaluated_construction_failed",
                 "measurement":paired[arm].get(r["query_id"])}
                 for arm in ("dense","rcd") for r in cell["records"]]
        protocol.validate_evaluation_rows(rows,cell,clean,seal_digest)
        write(output/identity/"rows.json",rows)
        write(output/identity/"summary.json",{arm:protocol.summarize([r for r in rows if r["pipeline"]==arm]) for arm in ("dense","rcd")})
    load_protocol(path,digest,snapshot)
    write(output/"evaluation.complete.json",{"schema":EVALUATION_SCHEMA,"protocol_sha256":digest,
        "construction_seal_sha256":seal_digest,"scope":value["binding"]["scope"],
        "rows_sha256":{identity:sha(output/identity/"rows.json") for identity in cells},
        "files_sha256":{p.relative_to(output).as_posix():sha(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    return {"status":"complete", "evaluation_completion_sha256":sha(output/"evaluation.complete.json")}


def aggregate(path,digest,root,seal_digest,evaluation,completion_digest,output):
    value,dense,rcd,clean,cells = load_sealed(path,digest,root,seal_digest)
    reliable.require_output(value,"aggregate",output)
    evaluation = Path(evaluation)
    complete = read_pinned(evaluation/"evaluation.complete.json",completion_digest)
    if (complete.get("schema") != EVALUATION_SCHEMA or complete.get("protocol_sha256") != digest or
        complete.get("construction_seal_sha256") != seal_digest or complete.get("scope") != value["binding"]["scope"] or
        set(complete.get("rows_sha256",{})) != set(cells)):
        raise ValueError("Evaluation completion/protocol/matrix provenance mismatch")
    actual_files = {p.relative_to(evaluation).as_posix():sha(p) for p in sorted(evaluation.rglob("*"))
                    if p.is_file() and p != evaluation/"evaluation.complete.json"}
    if complete.get("files_sha256") != actual_files:
        raise ValueError("Evaluation summary/raw-generation file integrity mismatch")
    summaries,groups = {},{}
    for identity,cell in cells.items():
        rows = read_pinned_rows(evaluation/identity/"rows.json",complete["rows_sha256"][identity])
        protocol.validate_evaluation_rows(rows,cell,clean,seal_digest)
        expected = []
        provenance = {"protocol_sha256":digest,"construction_seal_sha256":seal_digest,
            "model":value["model"],"decoding":value["rules"]["decoding"],"stage":"qa"}
        for row in rows:
            if row["measurement"] is None:
                continue
            cfg = dense if row["pipeline"] == "dense" else rcd
            for condition in ("clean","poisoned"):
                observed = row["measurement"][condition+"_condition"]["generation"]
                request = {"prompt":observed["prompt"],"max_tokens":int(cfg["max_tokens"]),"provenance":provenance,
                    "context":{"stage":"qa","pipeline":row["pipeline"],"condition":condition,"query_id":row["query_id"]}}
                expected.append((request,observed))
        if "execution" in value:
            reliable.validate_store(evaluation)
            for row in rows:
                if row["measurement"] is not None:reliable.validate_measurement_link(evaluation,identity,row["pipeline"],row["measurement"])
        else:
            validate_generation_journal(evaluation/identity/"generation",expected)
        summaries[identity] = {arm:protocol.summarize([r for r in rows if r["pipeline"]==arm]) for arm in ("dense","rcd")}
        if json.loads((evaluation/identity/"summary.json").read_text()) != summaries[identity]:
            raise ValueError("Stored summary differs from recomputed failure-aware outcomes")
        groups.setdefault(f"{cell['family']}.intensity-{cell['intensity']}",{})[cell["seed"]] = rows
    intervals = {group:protocol.bootstrap_paired(seeds,value["binding"]["query_ids"]) for group,seeds in groups.items()}
    result = {"schema":AGGREGATE_SCHEMA,"scope":value["binding"]["scope"],"protocol_sha256":digest,
        "construction_seal_sha256":seal_digest,"evaluation_completion_sha256":completion_digest,
        "cells":summaries,"paired_query_cluster_uncertainty":intervals,
        "unique_target_counts_per_query":{q["query_id"]:len({r["target_answer"] for cell in cells.values()
            for r in cell["records"] if r["query_id"]==q["query_id"] and r["target_answer"] is not None}) for q in clean["queries"]},
        "construction_failures_are_not_defense_successes":True,**manifest_fields(value),
        **({"diagnostic_only":True} if "development_study" in value else {}),
        **({"execution_accounting":reliable.accounting(evaluation)} if "execution" in value else {})}
    legacy._ensure_output_outside_repository(Path(output).parent)
    if "execution" in value:reliable.once(output,result)
    else:write(output,result)
    return {"status":"validated_aggregate_written","scope":value["binding"]["scope"]}


def read_pinned_rows(path,digest):
    if sha(path) != digest:
        raise ValueError("Evaluation row fingerprint mismatch")
    rows = json.loads(Path(path).read_text())
    if not isinstance(rows,list):
        raise ValueError("Expected complete evaluation rows")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("preflight","freeze-protocol","construct","evaluate","aggregate"))
    parser.add_argument("--target-method",choices=["development-source-focus-guard/v1","development-source-focus-guard/v2"],help="Opt-in development-only corrected source-focus nomination; freeze/preflight only")
    parser.add_argument("--development-study",choices=["semantic-quality-25/v1"],help="Development-only 25-query semantic intensity-1/3 study; freeze/preflight only")
    parser.add_argument("--semantic-profile",choices=semantic_profiles.IDENTIFIERS,help="Only preflight/freeze; later stages use the pinned protocol exclusively")
    parser.add_argument("--scope",choices=("heldout","development"),default="heldout")
    parser.add_argument("--protocol",type=Path)
    parser.add_argument("--protocol-sha256")
    parser.add_argument("--model-snapshot",type=Path)
    parser.add_argument("--construction-dir",type=Path)
    parser.add_argument("--construction-seal-sha256")
    parser.add_argument("--evaluation-dir",type=Path)
    parser.add_argument("--evaluation-completion-sha256")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--max-batches",type=int)
    parser.add_argument("--replication-spec",type=Path)
    parser.add_argument("--replication-spec-sha256")
    args = parser.parse_args()
    if args.target_method is not None and args.stage not in {"preflight","freeze-protocol"}:
        parser.error("Target method cannot be overridden after freeze")
    if args.development_study is not None and args.stage not in {"preflight","freeze-protocol"}:
        parser.error("Development study cannot be overridden after freeze")
    if args.semantic_profile is not None and args.stage not in {"preflight","freeze-protocol"}:
        parser.error("Profile cannot be overridden after freeze")
    if bool(args.replication_spec) != bool(args.replication_spec_sha256):
        parser.error("Supply both replication input specification and trusted SHA-256")
    replication = read_pinned(args.replication_spec,args.replication_spec_sha256) if args.replication_spec else None
    if replication is not None and args.stage not in {"preflight","freeze-protocol"}:
        parser.error("Later stages take replication inputs only from the frozen protocol")
    if args.stage == "preflight":
        profile=semantic_profiles.descriptor(args.semantic_profile,args.scope) if args.semantic_profile is not None else None
        study=None
        if args.development_study is not None:
            from src.experiments.semantic_development_study import descriptor
            study=descriptor(args.development_study)
        method=None
        if args.target_method is not None:
            from src.attacks.development_targets_v5 import method_module
            method=method_module(args.target_method).descriptor(args.target_method)
        validate_target_method(method,args.scope,study,profile)
        binding,*_ = study_context(args.scope,replication,study,profile)
        result = {"status":"metadata_only_not_scientific_readiness","binding":binding,"rules":frozen_rules(replication,profile,method),
                  **({"semantic_profile":profile} if profile is not None else {}),
                  **({"development_study":study} if study is not None else {}),
                  **({"target_method":method} if method is not None else {}),
                  "individual_target_signatures_required":False,"protocol_frozen":False}
    elif args.stage == "freeze-protocol":
        if not args.output or not args.model_snapshot:
            parser.error("freeze-protocol requires --output and --model-snapshot")
        result = freeze_protocol(args.output,args.scope,args.model_snapshot,replication,**({"semantic_profile":args.semantic_profile} if args.semantic_profile is not None else {}),
            **({"development_study":args.development_study} if args.development_study is not None else {}),
            **({"target_method":args.target_method} if args.target_method is not None else {}))
    else:
        if not args.protocol or not args.protocol_sha256 or not args.construction_dir:
            parser.error("Require --protocol, --protocol-sha256 and --construction-dir")
        if args.stage == "construct":
            if not args.model_snapshot:
                parser.error("construct requires --model-snapshot")
            result = construct(args.protocol,args.protocol_sha256,args.construction_dir,args.model_snapshot,args.max_batches)
        else:
            if not args.construction_seal_sha256:
                parser.error("Evaluation/aggregation requires externally pinned --construction-seal-sha256")
            if args.stage == "evaluate":
                if not args.evaluation_dir or not args.model_snapshot:
                    parser.error("evaluate requires --evaluation-dir and --model-snapshot")
                result = evaluate(args.protocol,args.protocol_sha256,args.construction_dir,args.construction_seal_sha256,args.evaluation_dir,args.model_snapshot,args.max_batches)
            else:
                if not args.evaluation_dir or not args.evaluation_completion_sha256 or not args.output:
                    parser.error("aggregate requires --evaluation-dir, --evaluation-completion-sha256 and --output")
                result = aggregate(args.protocol,args.protocol_sha256,args.construction_dir,args.construction_seal_sha256,args.evaluation_dir,args.evaluation_completion_sha256,args.output)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__ == "__main__":
    try: main()
    except reliable.PauseExecution as pause: print(json.dumps({"status":"paused","reason":str(pause),"resume":"repeat same stage/protocol/output"}));sys.exit(75)
