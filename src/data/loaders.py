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
import hashlib
import random


def _canonical_doc_id(dataset_tag: str, title: str, text: str) -> str:
    """Canonical, content-addressed doc ID: dataset + normalized title +
    content hash. This is deliberately NOT query-scoped, so the same
    Wikipedia article pulled in by multiple questions collapses to one
    corpus entry instead of N duplicates (see supervisor review #5).
    A hash suffix (rather than title alone) guards against two
    same-titled articles with different sentence sets (e.g. dataset
    version drift) silently colliding.
    """
    normalized_title = title.strip().lower().replace(" ", "_")
    content_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{dataset_tag}::{normalized_title}::{content_hash}"


def load_hotpotqa_distractor(split: str = "validation", n_samples: int | None = None,
                              seed: int = 42, revision: str | None = None) -> dict:
    """HotpotQA, distractor setting.

    [RESEARCH INFERENCE, corrected per supervisor review #3] Each HF
    row ships its own ~10-paragraph candidate pool, but this loader
    does NOT keep those pools separate per question. It merges every
    sampled question's paragraphs into one shared, deduplicated corpus
    (canonical doc IDs -- see `_canonical_doc_id`), and every query is
    evaluated by retrieving against that whole merged corpus. So the
    actual setting here is:

        pooled HotpotQA mini-corpus retrieval (N questions -> up to
        ~10*N deduplicated passages, fewer once repeated articles like
        "Albert Einstein" collapse to a single entry)

    NOT the standard per-question 10-doc distractor-pool evaluation
    used in most published HotpotQA work. [RECOMMENDATION, per review]
    Pooling is arguably more interesting for poisoning-transfer
    experiments (a 10-doc closed pool per question leaves little room
    for a poisoned doc to compete), but it must be reported as this
    pooled setting, not as standard distractor-setting HotpotQA.

    Also attaches gold retrieval labels (review #4), required for
    Recall@k / MRR / nDCG@k / PoisonRetrievalRate@k:
      - gold_doc_ids: canonical IDs of this query's supporting-fact
        documents, resolved against the SAME canonical-ID scheme used
        for the corpus (so gold_doc_ids are guaranteed to match
        entries in `corpus`).
      - gold_supporting_facts: the raw HF (title, sent_id) pairs, kept
        for sentence-level analysis / debugging.

    NOTE: uses the namespaced mirror "hotpotqa/hotpot_qa" rather than
    the original bare "hotpot_qa" repo. The original is a legacy
    "loading script" dataset; `datasets` v5.x removed script support,
    and its automatic parquet-fallback has a bug parsing bare-name
    (no-namespace) legacy repos. The namespaced mirror avoids this.
    """
    from datasets import load_dataset
    kwargs = {"split": split}
    if revision is not None:
        kwargs["revision"] = revision
    ds = load_dataset("hotpotqa/hotpot_qa", "distractor", **kwargs)

    if n_samples is not None:
        rng = random.Random(seed)
        indices = rng.sample(range(len(ds)), min(n_samples, len(ds)))
        ds = ds.select(indices)

    corpus = []
    seen_doc_ids = set()  # dedupe across queries (canonical IDs repeat
                           # when the same article is pulled in twice)
    queries = []

    for row in ds:
        query_id = row["id"]
        titles = row["context"]["title"]
        sentences_per_doc = row["context"]["sentences"]

        # title -> canonical doc_id, for resolving this row's supporting
        # facts below (needed since supporting_facts only gives titles,
        # not the merged text we hash into the canonical ID)
        title_to_doc_id = {}
        for title, sentences in zip(titles, sentences_per_doc):
            text = " ".join(sentences)
            doc_id = _canonical_doc_id("hotpotqa", title, text)
            title_to_doc_id[title] = doc_id
            if doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                corpus.append({"doc_id": doc_id, "text": text})

        sf_titles = row["supporting_facts"]["title"]
        sf_sent_ids = row["supporting_facts"]["sent_id"]
        gold_doc_ids = sorted({
            title_to_doc_id[t] for t in sf_titles if t in title_to_doc_id
        })
        gold_supporting_facts = [
            {"title": t, "sent_id": s} for t, s in zip(sf_titles, sf_sent_ids)
        ]

        queries.append({
            "query_id": query_id,
            "question": row["question"],
            "gold_answer": row["answer"],
            "gold_doc_ids": gold_doc_ids,
            "gold_supporting_facts": gold_supporting_facts,
        })

    return {"corpus": corpus, "queries": queries}


def load_2wikimultihopqa(split: str = "validation", n_samples: int | None = None,
                          seed: int = 42, revision: str | None = None) -> dict:
    """2WikiMultiHopQA.

    Same corpus-scope correction as `load_hotpotqa_distractor` (review
    #3/#4/#5): merges per-question candidate pools into one
    deduplicated, canonically-ID'd pooled corpus (see
    `load_hotpotqa_distractor`'s docstring for the full rationale)
    rather than keeping each question's pool separate, and attaches
    `gold_doc_ids` / `gold_supporting_facts` resolved against those
    canonical IDs.
    """
    from datasets import load_dataset
    kwargs = {"split": split}
    if revision is not None:
        kwargs["revision"] = revision
    ds = load_dataset("xanhho/2WikiMultihopQA", **kwargs)

    if n_samples is not None:
        rng = random.Random(seed)
        indices = rng.sample(range(len(ds)), min(n_samples, len(ds)))
        ds = ds.select(indices)

    corpus = []
    seen_doc_ids = set()
    queries = []

    for row in ds:
        query_id = row["_id"]

        title_to_doc_id = {}
        for title, sentences in row["context"]:
            text = " ".join(sentences)
            doc_id = _canonical_doc_id("2wikimultihopqa", title, text)
            title_to_doc_id[title] = doc_id
            if doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                corpus.append({"doc_id": doc_id, "text": text})

        # 2WikiMultiHopQA's supporting_facts is a list of [title, sent_id]
        # pairs (same shape idea as HotpotQA, different container).
        supporting_facts = row.get("supporting_facts", [])
        gold_doc_ids = sorted({
            title_to_doc_id[t] for t, _ in supporting_facts if t in title_to_doc_id
        })
        gold_supporting_facts = [
            {"title": t, "sent_id": s} for t, s in supporting_facts
        ]

        queries.append({
            "query_id": query_id,
            "question": row["question"],
            "gold_answer": row["answer"],
            "gold_doc_ids": gold_doc_ids,
            "gold_supporting_facts": gold_supporting_facts,
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
