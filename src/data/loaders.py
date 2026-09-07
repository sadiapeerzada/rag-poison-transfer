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
import json
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

    NOTE (fixed after Week 5-6 attack-sweep attempt): the original mirror
    ("xanhho/2WikiMultihopQA") ships a Python loading script, which
    current `datasets` (v4+) refuses to execute -- same class of problem
    documented in load_hotpotqa_distractor()'s docstring for the original
    bare "hotpot_qa" repo. Switched to "Salesforce/ContextualBench"
    (config "2WikiMultihopQA"), a parquet-native mirror with no script.
    Its split names are train/dev/test (not train/validation/test), so
    "validation" is mapped to "dev" here to keep existing configs
    (dataset_split: validation) working unchanged. Unlike the old
    xanhho mirror, context/supporting_facts here are native nested
    dicts, not JSON-encoded strings -- no json.loads() needed.

    Same corpus-scope correction as `load_hotpotqa_distractor` (review
    #3/#4/#5): merges per-question candidate pools into one
    deduplicated, canonically-ID'd pooled corpus rather than keeping
    each question's pool separate, and attaches `gold_doc_ids` /
    `gold_supporting_facts` resolved against those canonical IDs.
    """
    from datasets import load_dataset
    hf_split = "dev" if split == "validation" else split
    kwargs = {"split": hf_split}
    if revision is not None:
        kwargs["revision"] = revision
    ds = load_dataset("Salesforce/ContextualBench", "2WikiMultihopQA", **kwargs)

    if n_samples is not None:
        rng = random.Random(seed)
        indices = rng.sample(range(len(ds)), min(n_samples, len(ds)))
        ds = ds.select(indices)

    corpus = []
    seen_doc_ids = set()
    queries = []

    for row in ds:
        query_id = row["_id"]
        context = row["context"]  # {'title': [...], 'content': [[sentences...], ...]}
        titles = context["title"]
        contents = context["content"]

        title_to_doc_id = {}
        for title, sentences in zip(titles, contents):
            text = " ".join(sentences)
            doc_id = _canonical_doc_id("2wikimultihopqa", title, text)
            title_to_doc_id[title] = doc_id
            if doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                corpus.append({"doc_id": doc_id, "text": text})

        supporting_facts = row["supporting_facts"]  # {'title': [...], 'sent_id': [...]}
        sf_titles = supporting_facts["title"]
        sf_sent_ids = supporting_facts["sent_id"]
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


def _reconstruct_text(tokens: list[str], is_html: list[bool]) -> str:
    """Join a token span into plain text, dropping HTML structural
    tokens (e.g. '<P>', '</H1>') that Natural Questions' raw token
    stream includes inline."""
    return " ".join(t for t, h in zip(tokens, is_html) if not h)


def load_natural_questions(split: str = "validation", n_samples: int | None = None,
                             seed: int = 42, revision: str | None = None,
                             shuffle_buffer_size: int = 10_000) -> dict:
    """Natural Questions, pooled mini-corpus (same design as
    load_hotpotqa_distractor / load_2wikimultihopqa).

    Unlike nq_open (google-research-datasets/nq_open), which ships ONLY
    questions and short answers with no passage data at all, the full
    `google-research-datasets/natural_questions` dataset provides
    `long_answer_candidates`: a pre-segmented list of candidate
    paragraph spans per question (Google's own HTML-structure parser
    output), directly analogous to HotpotQA's per-question distractor
    pool. This loader uses that field rather than attempting full
    ~21M-passage open-domain retrieval, which is not practical here --
    same corpus-scope tradeoff already made for HotpotQA/2Wiki, now
    documented for NQ too.

    Streamed (the full dataset is 100+ GB): sampling uses a shuffle
    buffer, not a true uniform sample over the full split -- documents
    beyond the buffer window are systematically less likely to be
    selected. Acceptable for a bounded pilot/attack-benchmark sample;
    NOT a substitute for a properly stratified sample if NQ is ever
    used for a headline result.

    Queries with no valid long-answer annotation across all 5 raters
    (i.e. every candidate_index is -1) are skipped -- there is no gold
    document to evaluate retrieval against for these ("no answer"
    questions in NQ's own annotation scheme).
    """
    from datasets import load_dataset
    kwargs = {"split": split, "streaming": True}
    if revision is not None:
        kwargs["revision"] = revision
    ds = load_dataset("google-research-datasets/natural_questions", "default", **kwargs)
    ds = ds.shuffle(seed=seed, buffer_size=shuffle_buffer_size)

    corpus = []
    seen_doc_ids = set()
    queries = []
    n_seen = 0
    n_skipped_no_gold = 0

    for row in ds:
        if n_samples is not None and len(queries) >= n_samples:
            break
        n_seen += 1

        # Pick the first annotator with a real long-answer candidate
        # (NQ has 5 raters per validation question; most questions have
        # some raters marking "no answer" (-1) even when others found one).
        gold_candidate_index = None
        gold_short_answer_text = None
        for ann_idx, long_ann in enumerate(row["annotations"]["long_answer"]):
            if long_ann["candidate_index"] != -1:
                gold_candidate_index = long_ann["candidate_index"]
                short = row["annotations"]["short_answers"][ann_idx]
                if short["text"]:
                    gold_short_answer_text = short["text"][0]
                break

        if gold_candidate_index is None:
            n_skipped_no_gold += 1
            continue

        yes_no = row["annotations"]["yes_no_answer"]
        gold_answer = gold_short_answer_text
        if gold_answer is None:
            # Fall back to yes/no answer if that's what this question has,
            # rather than skipping a perfectly good long-answer example.
            yn = next((v for v in yes_no if v != -1), None)
            if yn == 0:
                gold_answer = "no"
            elif yn == 1:
                gold_answer = "yes"
        if gold_answer is None:
            # Long answer exists but no extractable short/yes-no answer --
            # not usable as a QA gold label for this pipeline.
            n_skipped_no_gold += 1
            continue

        title = row["document"]["title"]
        all_tokens = row["document"]["tokens"]["token"]
        all_is_html = row["document"]["tokens"]["is_html"]

        starts = row["long_answer_candidates"]["start_token"]
        ends = row["long_answer_candidates"]["end_token"]

        gold_doc_id = None
        gold_supporting_facts = []
        for cand_idx, (start, end) in enumerate(zip(starts, ends)):
            text = _reconstruct_text(all_tokens[start:end], all_is_html[start:end])
            if not text.strip():
                continue
            doc_id = _canonical_doc_id("naturalquestions", f"{title}::{cand_idx}", text)
            if doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                corpus.append({"doc_id": doc_id, "text": text})
            if cand_idx == gold_candidate_index:
                gold_doc_id = doc_id
                gold_supporting_facts = [{"title": title, "candidate_index": cand_idx}]

        if gold_doc_id is None:
            # Gold candidate_index pointed at an empty/unreconstructable
            # span -- skip rather than report a query with no real gold doc.
            n_skipped_no_gold += 1
            continue

        queries.append({
            "query_id": row["id"],
            "question": row["question"]["text"],
            "gold_answer": gold_answer,
            "gold_doc_ids": [gold_doc_id],
            "gold_supporting_facts": gold_supporting_facts,
        })

    return {"corpus": corpus, "queries": queries}
