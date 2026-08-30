"""Real dataset loaders for NQ-open, HotpotQA, and 2WikiMultiHopQA.

*** IMPORTANT -- READ BEFORE USING FOR REAL RESULTS ***

The corpus-scope choices below are [REC] -- my recommendations for
making these datasets tractable on a MacBook Air M4 with no cloud GPU
(Section L of the foundation doc) -- NOT yet confirmed by your
supervisor. Do not report numbers from these loaders as final results
until he's signed off on:
  1. Test-set subsampling (N ~= 150-300 queries/dataset)
  2. HotpotQA/2WikiMultiHopQA: using each dataset's own provided
     per-question candidate pool instead of full open-domain retrieval
  3. NQ-open: using a prebuilt passage index instead of re-embedding
     the full ~21M-passage Wikipedia corpus from scratch

These loaders download data via the `datasets` library the first time
they run -- requires internet access to Hugging Face, so run this on
your Mac, not in a sandbox with restricted network access.

Until confirmed, treat anything loaded here as DEV-SCALE / PILOT DATA
for testing the pipeline -- not a frozen benchmark.
"""
import random


def load_hotpotqa_distractor(split: str = "validation", n_samples: int | None = None,
                              seed: int = 42) -> dict:
    """HotpotQA, distractor setting: each question ships with its own
    ~10-paragraph candidate pool (mix of gold + distractor paragraphs).
    This is the standard evaluation setting for this dataset in most
    published work [RESEARCH INFERENCE] -- not full open-domain
    retrieval over all of Wikipedia.

    NOTE: uses the namespaced mirror "hotpotqa/hotpot_qa" rather than
    the original bare "hotpot_qa" repo. The original is a legacy
    "loading script" dataset; `datasets` v5.x removed script support,
    and its automatic parquet-fallback has a bug parsing bare-name
    (no-namespace) legacy repos. The namespaced mirror avoids this.
    """
    from datasets import load_dataset
    ds = load_dataset("hotpotqa/hotpot_qa", "distractor", split=split)

    if n_samples is not None:
        rng = random.Random(seed)
        indices = rng.sample(range(len(ds)), min(n_samples, len(ds)))
        ds = ds.select(indices)

    corpus, queries = [], []
    for row in ds:
        query_id = row["id"]
        titles = row["context"]["title"]
        sentences_per_doc = row["context"]["sentences"]
        for title, sentences in zip(titles, sentences_per_doc):
            doc_id = f"{query_id}::{title}"
            corpus.append({"doc_id": doc_id, "text": " ".join(sentences)})
        queries.append({
            "query_id": query_id,
            "question": row["question"],
            "gold_answer": row["answer"],
        })
    return {"corpus": corpus, "queries": queries}


def load_2wikimultihopqa(split: str = "validation", n_samples: int | None = None,
                          seed: int = 42) -> dict:
    """2WikiMultiHopQA: similarly ships a per-question candidate pool.
    [REC] Same corpus-scope reasoning as HotpotQA above -- use the
    provided candidate pool, not full open-domain retrieval.
    """
    from datasets import load_dataset
    ds = load_dataset("xanhho/2WikiMultihopQA", split=split)

    if n_samples is not None:
        rng = random.Random(seed)
        indices = rng.sample(range(len(ds)), min(n_samples, len(ds)))
        ds = ds.select(indices)

    corpus, queries = [], []
    for row in ds:
        query_id = row["_id"]
        for title, sentences in row["context"]:
            doc_id = f"{query_id}::{title}"
            corpus.append({"doc_id": doc_id, "text": " ".join(sentences)})
        queries.append({
            "query_id": query_id,
            "question": row["question"],
            "gold_answer": row["answer"],
        })
    return {"corpus": corpus, "queries": queries}


def load_nq_open_pilot(n_samples: int = 200, seed: int = 42) -> dict:
    """NQ-open, PILOT VERSION ONLY.

    [REC -- NOT YET APPROVED] Real NQ-open evaluation requires the full
    ~21M-passage Wikipedia corpus (typically via a prebuilt DPR-style
    index), which is not practical to build from scratch on a MacBook
    Air. This pilot loader instead builds a SMALL per-query corpus by
    sampling a handful of NQ questions and using only their associated
    short/long answer context as "the corpus" -- i.e. an easier,
    non-adversarial retrieval setting, NOT equivalent to open-domain
    NQ retrieval.

    Use this ONLY to test pipeline wiring on real NQ *questions*. Do
    not report EM/F1 from this as an NQ-open baseline result -- flag
    this limitation explicitly to your supervisor if you use it before
    a real prebuilt index is set up.
    """
    from datasets import load_dataset
    ds = load_dataset("google-research-datasets/nq_open", split="validation")
    rng = random.Random(seed)
    indices = rng.sample(range(len(ds)), min(n_samples, len(ds)))
    ds = ds.select(indices)

    queries = []
    for i, row in enumerate(ds):
        queries.append({
            "query_id": f"nq_{i}",
            "question": row["question"],
            "gold_answer": row["answer"][0] if row["answer"] else "",
        })
    # NOTE: nq_open (unlike hotpot_qa) does not ship per-question
    # candidate passages -- there is no legitimate "corpus" here yet.
    # A real corpus (prebuilt DPR index) must be wired in before this
    # is usable for anything beyond question-list inspection.
    return {"corpus": [], "queries": queries}
