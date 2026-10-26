"""No held-out question text or real model calls: synthetic protocol regression tests."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.experiments import week9_construction as p
from scripts import run_week9_protocol_poison_matrix as runner
from src.pipelines.generator import GenerationResult


def q(qid,question,gold):
    return {"query_id":qid,"question":question,"gold_answer":gold,"gold_doc_ids":["clean"]}


@pytest.fixture
def data():
    return {"queries":[q("one","Who wrote the initial book?","Alice Author"),
                       q("two","Describe this category.","Unresolved phrase"),
                       q("three","Who wrote the third book?","Carol Writer")],
            "corpus":[{"doc_id":"clean","text":"Synthetic clean evidence."}]}


@pytest.fixture
def development():
    return [q("dev1","Who wrote the development book?","Bob Writer"),
            q("dev2","Who directed the development film?","Dana Director")]


class Generator:
    def __init__(self,partial=False):
        self.partial = partial
        self.calls = []

    def generate(self,prompt,max_tokens):
        self.calls.append(prompt)
        if 'Reference answer: "' in prompt:
            target = prompt.split('Reference answer: "')[1].split('"')[0]
            text = (f"A discussion mentions {target} without affirming any answer."
                    if self.partial and "historical background" in prompt else
                    f"{target} is the documented answer to this question. The entry gives a direct identifying relationship.")
        else:
            text = "Bob Writer"
        return GenerationResult(text,.1,10,20)


def construct(data,development,family=p.ATTACKS[1],intensity=1,seed=42,backend=None):
    records = [p.construct_query(query,development,family,intensity,seed,backend or Generator(),set_runtime_seed=lambda s:None)
               for query in data["queries"]]
    return runner.make_cell(data,family,intensity,seed,"a"*64,records)


def test_rules_fixed_matrix_and_deterministic_selection(data,development):
    assert len(p.cells()) == 12 and p.SEEDS == (42,43,44) and p.INTENSITIES == (1,3)
    assert p.rules()["version"] == p.VERSION
    first = p.select_target(data["queries"][0],development,42)
    assert first[0] is not None
    assert first == p.select_target(data["queries"][0],list(reversed(development)),42)
    assert first[0] != data["queries"][0]["gold_answer"]
    assert p.derived_seed(42,"one","target-selection") != p.derived_seed(43,"one","target-selection")
    aliases = {**data["queries"][0],"gold_aliases":["Bob Writer","Dana Director"]}
    assert p.select_target(aliases,development,42)[0] is None
    incompatible = [q("dev","What year did this happen?","1900")]
    assert p.select_target(data["queries"][0],incompatible,42)[0] is None


def test_full_population_partial_construction_discards_all_partials(data,development):
    backend = Generator(partial=True)
    cell = construct(data,development,intensity=3,backend=backend)
    assert [r["status"] for r in cell["records"]] == [p.SEMANTIC_FAILED,p.TARGET_FAILED,p.SEMANTIC_FAILED]
    row = cell["records"][0]
    assert row["documents"] == [] and len(row["partial_documents"]) == 2
    assert [len(a["attempts"]) for a in row["attempt_records"]] == [1,2,1]
    assert all(a["attempts"][0]["generated_text"] for a in row["attempt_records"])
    p.validate_cell(cell,data,development,"a"*64)
    replayed = p.replay(data,cell)
    assert replayed["queries"] == [] and replayed["corpus"] == data["corpus"]


@pytest.mark.parametrize("change",[
    lambda c:c.update(protocol_sha256="b"*64),
    lambda c:c["records"].pop(),
    lambda c:c["records"][0].update(target_answer="Different"),
    lambda c:c["records"][0]["documents"][0].update(text="Changed bytes"),
    lambda c:c["records"][0].update(documents=[]),
    lambda c:c["records"][0]["attempt_records"][0]["attempts"][0].update(prompt_revision=99),
])
def test_ledger_tampering_fails(data,development,change):
    cell = construct(data,development)
    change(cell)
    with pytest.raises(ValueError):
        p.validate_cell(cell,data,development,"a"*64)


def test_all_300_failures_retained_without_model_calls(development):
    data = {"queries":[q(f"synthetic-{i}","Describe this category.","Unresolved phrase") for i in range(300)],"corpus":[]}
    backend = Generator()
    cell = construct(data,development,backend=backend)
    p.validate_cell(cell,data,development,"a"*64)
    assert len(cell["records"]) == 300 and not backend.calls
    rows = [{"construction_status":p.TARGET_FAILED,"measurement":None} for _ in range(300)]
    summary = p.summarize(rows)
    assert summary["end_to_end_targeted_asr"] == p.rate(0,300)
    assert summary["conditional_targeted_asr_valid"] == p.rate(0,0)
    assert summary["evaluated"] == 0 and summary["failed"] == 300


def test_journal_replays_exact_response_and_never_retries_unknown_call(tmp_path):
    backend = Generator()
    first = runner.JournalGenerator(backend,tmp_path,{"model":"synthetic"})
    first.generate("Software fixture QA",64)
    second = runner.JournalGenerator(backend,tmp_path,{"model":"synthetic"})
    assert second.generate("Software fixture QA",64).text == "Bob Writer"
    assert len(backend.calls) == 1
    with pytest.raises(ValueError,match="provenance"):
        runner.JournalGenerator(backend,tmp_path,{"model":"changed"}).generate("Software fixture QA",64)
    (tmp_path/"00.response.json").unlink()
    with pytest.raises(RuntimeError,match="Indeterminate"):
        runner.JournalGenerator(backend,tmp_path,{"model":"synthetic"}).generate("Software fixture QA",64)
    assert len(backend.calls) == 1


def harness(monkeypatch,data,development):
    value = {"schema":runner.PROTOCOL_SCHEMA,"rules":p.rules(),"source":{"git_commit_sha":"c"*40},
        "binding":{"scope":"development","query_ids":[q["query_id"] for q in data["queries"]],"model_identity":"fixture"},
        "model":{"revision":"d"*40}}
    config = {"top_k":3,"max_tokens":64}
    monkeypatch.setattr(runner,"load_protocol",lambda *a:(value,config,config,development))
    monkeypatch.setattr(runner,"load_clean",lambda *a:copy.deepcopy(data))
    monkeypatch.setattr(runner,"code_binding",lambda:value["source"])
    monkeypatch.setattr(runner,"model_binding",lambda *a:value["model"])
    monkeypatch.setattr(runner,"runtime_seed",lambda s:None)
    backend = Generator()
    monkeypatch.setattr(runner,"generator",lambda *a:backend)
    snapshots = []
    class Retriever:
        def __init__(self,corpus):
            self.docs = [SimpleNamespace(**d) for d in corpus]
        def retrieve(self,question,top_k):
            return self.docs[:top_k]
    def matched(dense,rcd,clean,poisoned):
        snapshots.append(copy.deepcopy(poisoned))
        return {arm:(Retriever(clean["corpus"]),Retriever(poisoned["corpus"])) for arm in ("dense","rcd")}
    monkeypatch.setattr(runner,"build_matched_retrievers",matched)
    return value,backend,snapshots


def test_global_barrier_evaluation_ledger_metrics_and_pairing(tmp_path,monkeypatch,data,development):
    value,backend,snapshots = harness(monkeypatch,data,development)
    root = tmp_path/"construction"
    result = runner.construct(Path("unused"),"a"*64,root,Path("fixture"))
    seal_digest = result["construction_seal_sha256"]
    assert len(list(root.glob("*/construction.json"))) == 2
    calls_before = len(backend.calls)
    # No QA/retriever call occurs in construction, and partial seals cannot evaluate.
    assert all('Reference answer: "' in prompt for prompt in backend.calls) and snapshots == []
    sealpath = root/"construction.seal.json"
    seal = json.loads(sealpath.read_text())
    bad = copy.deepcopy(seal)
    bad["cells"].pop(next(iter(bad["cells"])))
    sealpath.write_text(json.dumps(bad))
    with pytest.raises(ValueError,match="Complete declared matrix"):
        runner.evaluate(Path("unused"),"a"*64,root,runner.sha(sealpath),tmp_path/"bad",Path("fixture"))
    assert len(backend.calls) == calls_before and snapshots == []
    sealpath.write_text(json.dumps(seal))
    # Byte hash changed by formatting; use the externally supplied new exact pin in this test.
    seal_digest = runner.sha(sealpath)
    output = tmp_path/"evaluation"
    runner.evaluate(Path("unused"),"a"*64,root,seal_digest,output,Path("fixture"))
    assert len(snapshots) == 2
    for identity in seal["cells"]:
        rows = json.loads((output/identity/"rows.json").read_text())
        assert len(rows) == 6
        failed = [r for r in rows if r["query_id"]=="two"]
        assert len(failed) == 2 and all(r["measurement"] is None for r in failed)
        dense = [r for r in rows if r["pipeline"]=="dense"]
        summary = p.summarize(dense)
        assert summary["attempted"]==3 and summary["valid"]==summary["evaluated"]==2
        assert summary["end_to_end_targeted_asr"]["denominator"]==3
        assert summary["conditional_targeted_asr_valid"]["denominator"]==2
        for qid in ("one","three"):
            pair = [r["measurement"] for r in rows if r["query_id"]==qid]
            assert pair[0]["poison_doc_ids"]==pair[1]["poison_doc_ids"]
        bad = copy.deepcopy(rows)
        bad[1]["measurement"] = {}
        cell = json.loads((root/identity/"construction.json").read_text())
        with pytest.raises(ValueError,match="fabricate"):
            p.validate_evaluation_rows(bad,cell,data,seal_digest)
        interval = p.bootstrap_paired({42:rows,43:rows,44:rows},value["binding"]["query_ids"],replicates=8)
        assert interval["unique_queries"]==3 and interval["poison_seeds"]==[42,43,44]
        assert interval["metrics"]["end_to_end_targeted_asr"]["ci95_percentile"]==[0,0]
    # Changed frozen bytes fail globally, before another model/retriever is built.
    (root/"extra.json").write_text("{}")
    with pytest.raises(ValueError,match="integrity"):
        runner.evaluate(Path("unused"),"a"*64,root,seal_digest,tmp_path/"tampered",Path("fixture"))


def test_protocol_version_and_source_binding_rejected_before_data(monkeypatch,tmp_path):
    value = {"schema":runner.PROTOCOL_SCHEMA,"rules":{**p.rules(),"version":"stale"}}
    path = tmp_path/"protocol.json"
    path.write_text(json.dumps(value))
    monkeypatch.setattr(runner,"load_clean",lambda *a:pytest.fail("No cohort data on stale protocol"))
    with pytest.raises(ValueError,match="version/rules"):
        runner.load_protocol(path,runner.sha(path))


def test_metadata_preflight_never_loads_heldout_text_or_model(monkeypatch):
    monkeypatch.setattr(runner,"load_dataset",lambda *a:pytest.fail("No held-out text in preflight"))
    monkeypatch.setattr(runner,"build_generator",lambda *a:pytest.fail("No model in preflight"))
    binding,_,_,development = runner.metadata("heldout")
    assert len(binding["query_ids"])==300 and len(binding["matrix"])==12
    assert not set(binding["query_ids"]) & {q["query_id"] for q in development}
    assert binding["dataset"]["revision"]=="1908d6afbbead072334abe2965f91bd2709910ab"


def test_model_snapshot_exact_bytes_and_protocol_freeze_validation(tmp_path,monkeypatch):
    snapshot = tmp_path/"models--fixture--model"/"snapshots"/("a"*40)
    snapshot.mkdir(parents=True)
    (snapshot/"config.json").write_text('{"software_fixture_only":true}')
    (snapshot/"model.safetensors").write_bytes(b"not real weights; software test only")
    binding = runner.model_binding(snapshot,"fixture/model")
    value = {"scope":"development","model_identity":"fixture/model"}
    monkeypatch.setattr(runner,"metadata",lambda s:(value,{}, {},[]))
    monkeypatch.setattr(runner,"code_binding",lambda:{"git_commit_sha":"b"*40,"code_fingerprint":"c"*64})
    monkeypatch.setattr(runner,"environment",lambda:{"python":"software fixture"})
    path = tmp_path/"protocol.json"
    result = runner.freeze_protocol(path,"development",snapshot)
    assert result["status"]=="protocol_frozen_no_construction_or_evaluation"
    runner.load_protocol(path,runner.sha(path),snapshot)
    with pytest.raises(FileExistsError):
        runner.freeze_protocol(path,"development",snapshot)
    (snapshot/"model.safetensors").write_bytes(b"changed software test bytes")
    assert runner.model_binding(snapshot,"fixture/model") != binding
    with pytest.raises(ValueError,match="snapshot bytes"):
        runner.load_protocol(path,runner.sha(path),snapshot)
    monkeypatch.setattr(runner,"code_binding",lambda:{"git_commit_sha":"changed"})
    with pytest.raises(ValueError,match="provenance"):
        runner.load_protocol(path,runner.sha(path))


def test_all_twelve_cells_keep_all_300_failure_records(tmp_path,monkeypatch,development):
    data = {"queries":[q(f"synthetic-population-{i}","Describe this category.","Unresolved phrase") for i in range(300)],
            "corpus":[{"doc_id":"clean","text":"Software fixture."}]}
    value,backend,snapshots = harness(monkeypatch,data,development)
    value["binding"]["scope"]="heldout"
    root = tmp_path/"construction"
    result = runner.construct(Path("unused"),"a"*64,root,Path("fixture"))
    assert len(list(root.glob("*/construction.json")))==12
    output = tmp_path/"evaluation"
    runner.evaluate(Path("unused"),"a"*64,root,result["construction_seal_sha256"],output,Path("fixture"))
    assert len(list(output.glob("*/rows.json")))==12
    assert not backend.calls and not snapshots
    rows = json.loads(next(output.glob("*/rows.json")).read_text())
    assert len(rows)==600 and all(r["measurement"] is None for r in rows)
    interval = p.bootstrap_paired({42:rows,43:rows,44:rows},value["binding"]["query_ids"],replicates=3)
    assert interval["metrics"]["end_to_end_targeted_asr"]["ci95_percentile"]==[0,0]
    assert interval["metrics"]["conditional_targeted_asr_valid"]["ci95_percentile"] is None


def test_aggregate_recomputes_and_rejects_changed_rows(tmp_path,monkeypatch,data,development):
    value,_,_ = harness(monkeypatch,data,development)
    root,out = tmp_path/"construction",tmp_path/"evaluation"
    seal = runner.construct(Path("unused"),"a"*64,root,Path("fixture"))["construction_seal_sha256"]
    completion = runner.evaluate(Path("unused"),"a"*64,root,seal,out,Path("fixture"))["evaluation_completion_sha256"]
    original_bootstrap = p.bootstrap_paired
    monkeypatch.setattr(p,"bootstrap_paired",lambda seeds,ids:original_bootstrap(seeds,ids,replicates=4))
    report = tmp_path/"aggregate.json"
    runner.aggregate(Path("unused"),"a"*64,root,seal,out,completion,report)
    result = json.loads(report.read_text())
    assert result["construction_failures_are_not_defense_successes"] is True
    assert len(result["cells"])==2
    one = next(out.glob("*/rows.json"))
    one.write_text("[]")
    with pytest.raises(ValueError,match="integrity"):
        runner.aggregate(Path("unused"),"a"*64,root,seal,out,completion,tmp_path/"bad.json")


def test_attempts_cross_checked_against_actual_journal(tmp_path,monkeypatch,data,development):
    value,_,_ = harness(monkeypatch,data,development)
    root = tmp_path/"construction"
    runner.construct(Path("unused"),"a"*64,root,Path("fixture"))
    identity = p.cell_id(p.ATTACKS[1],1,42)
    cell = json.loads((root/identity/"construction.json").read_text())
    response = next((root/identity/"generation").glob("*/*.response.json"))
    saved = json.loads(response.read_text())
    saved["generation"]["raw_response"]="Changed journal output."
    saved["generation"]["extracted_answer"]="Changed journal output."
    # Keep the journal internally consistent to exercise the separate sealed-attempt check.
    saved["generation_sha256"]=p.fingerprint(saved["generation"])
    response.write_text(json.dumps(saved))
    with pytest.raises(ValueError,match="differs from frozen attempt"):
        runner.construction_journals(root,cell,value,"a"*64)


def test_infrastructure_failure_is_not_a_scientific_zero(data,development,tmp_path):
    class Broken:
        calls = 0
        def generate(self,prompt,max_tokens):
            self.calls += 1
            raise RuntimeError("software fixture backend error")
    backend = Broken()
    wrapped = runner.JournalGenerator(backend,tmp_path,{"model":"software fixture"})
    with pytest.raises(RuntimeError,match="backend error"):
        p.construct_query(data["queries"][0],development,p.ATTACKS[1],1,42,wrapped,set_runtime_seed=lambda s:None)
    with pytest.raises(RuntimeError,match="Failed/inconsistent"):
        p.construct_query(data["queries"][0],development,p.ATTACKS[1],1,42,
            runner.JournalGenerator(backend,tmp_path,{"model":"software fixture"}),set_runtime_seed=lambda s:None)
    assert backend.calls==1


def test_independent_generation_and_diagnostic_rankings(data,development,tmp_path,monkeypatch):
    harness(monkeypatch,data,development)
    class Retriever:
        def __init__(self,corpus):
            self.docs=[SimpleNamespace(**d) for d in corpus]
        def retrieve(self,question,top_k):
            return [self.docs[-1]] if top_k==3 and len(self.docs)>1 else self.docs[:top_k]
    monkeypatch.setattr(runner,"build_matched_retrievers",lambda a,b,clean,poisoned:{
        arm:(Retriever(clean["corpus"]),Retriever(poisoned["corpus"])) for arm in ("dense","rcd")})
    root,out = tmp_path/"construction",tmp_path/"evaluation"
    seal = runner.construct(Path("unused"),"a"*64,root,Path("fixture"))["construction_seal_sha256"]
    runner.evaluate(Path("unused"),"a"*64,root,seal,out,Path("fixture"))
    rows=json.loads(next(out.glob("*/rows.json")).read_text())
    measured=next(r["measurement"] for r in rows if r["measurement"])
    obs=measured["poisoned_condition"]
    assert obs["generation_evidence_doc_ids"] != obs["retrieved_doc_ids"][:len(obs["generation_evidence_doc_ids"])]
