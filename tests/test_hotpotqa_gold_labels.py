"""Tests for gold_doc_ids extraction in load_hotpotqa_distractor.

Uses a synthetic row matching HotpotQA's real schema via monkeypatching
datasets.load_dataset -- tests the extraction LOGIC without needing a
real network call.

IMPORTANT: expected doc_ids are computed via the SAME _canonical_doc_id
function the loader uses (dataset + normalized_title + content_hash),
not hardcoded literal strings. Hardcoding e.g. "q001::Eiffel Tower"
would silently test for the OLD query-scoped ID scheme (review #3/#5:
same article across different questions became different documents),
which is exactly the bug that was fixed -- a test with the old format
baked in would fail against correct code and look like a regression.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.loaders import _canonical_doc_id


class _FakeHFDataset:
    def __init__(self, rows):
        self._rows = rows

    def __len__(self):
        return len(self._rows)

    def select(self, indices):
        return _FakeHFDataset([self._rows[i] for i in indices])

    def __iter__(self):
        return iter(self._rows)


def _fake_row(query_id, question, answer, context_titles_sentences, supporting_titles):
    return {
        "id": query_id,
        "question": question,
        "answer": answer,
        "context": {
            "title": [t for t, _ in context_titles_sentences],
            "sentences": [s for _, s in context_titles_sentences],
        },
        "supporting_facts": {
            "title": supporting_titles,
            "sent_id": [0] * len(supporting_titles),
        },
    }


def test_gold_doc_ids_extracted_correctly(monkeypatch):
    import datasets as hf_datasets

    context = [
        ("Eiffel Tower", ["The Eiffel Tower is in Paris."]),
        ("Gustave Eiffel", ["Gustave Eiffel was an engineer."]),
        ("Unrelated Distractor", ["This paragraph is irrelevant."]),
    ]
    fake_rows = [_fake_row(
        query_id="q001",
        question="Where was the Eiffel Tower built and by whom?",
        answer="Paris, by Gustave Eiffel",
        context_titles_sentences=context,
        supporting_titles=["Eiffel Tower", "Gustave Eiffel"],
    )]
    monkeypatch.setattr(hf_datasets, "load_dataset", lambda *a, **kw: _FakeHFDataset(fake_rows))

    from src.data.loaders import load_hotpotqa_distractor
    result = load_hotpotqa_distractor(split="validation", n_samples=None)

    assert len(result["queries"]) == 1
    assert len(result["corpus"]) == 3
    query = result["queries"][0]

    # Expected IDs computed via the SAME function the loader uses --
    # not hardcoded, so this test tracks the real scheme even if the
    # hash algorithm or normalization rule changes later.
    expected_gold = {
        _canonical_doc_id("hotpotqa", "Eiffel Tower", "The Eiffel Tower is in Paris."),
        _canonical_doc_id("hotpotqa", "Gustave Eiffel", "Gustave Eiffel was an engineer."),
    }
    assert set(query["gold_doc_ids"]) == expected_gold

    distractor_id = _canonical_doc_id("hotpotqa", "Unrelated Distractor", "This paragraph is irrelevant.")
    assert distractor_id not in query["gold_doc_ids"]

    corpus_ids = {d["doc_id"] for d in result["corpus"]}
    for gold_id in query["gold_doc_ids"]:
        assert gold_id in corpus_ids, f"{gold_id} is gold but missing from corpus"


def test_gold_doc_ids_deduplicated_when_title_appears_multiple_times_in_supporting_facts(monkeypatch):
    """HotpotQA's supporting_facts can list the same title twice (e.g.
    two different sentences from the same article are both supporting
    facts). gold_doc_ids should still collapse to ONE canonical id, not
    two copies of it.
    """
    import datasets as hf_datasets

    context = [("Paragraph A", ["Sentence one.", "Sentence two."])]
    fake_rows = [_fake_row(
        query_id="q002",
        question="Multi-sentence support test",
        answer="Some answer",
        context_titles_sentences=context,
        supporting_titles=["Paragraph A", "Paragraph A"],  # same title, twice
    )]
    monkeypatch.setattr(hf_datasets, "load_dataset", lambda *a, **kw: _FakeHFDataset(fake_rows))

    from src.data.loaders import load_hotpotqa_distractor
    result = load_hotpotqa_distractor(split="validation", n_samples=None)

    expected_id = _canonical_doc_id("hotpotqa", "Paragraph A", "Sentence one. Sentence two.")
    assert result["queries"][0]["gold_doc_ids"] == [expected_id]


def test_gold_doc_ids_collapse_across_two_questions_sharing_an_article(monkeypatch):
    """The scenario the OLD query-scoped ID scheme got wrong: two
    different questions both cite the same real-world article. Their
    gold_doc_ids should point at the SAME canonical corpus entry, not
    two separate near-duplicate documents.
    """
    import datasets as hf_datasets

    shared_text = "Albert Einstein developed the theory of relativity."
    fake_rows = [
        _fake_row(
            query_id="q010", question="Who developed relativity?", answer="Einstein",
            context_titles_sentences=[("Albert Einstein", [shared_text])],
            supporting_titles=["Albert Einstein"],
        ),
        _fake_row(
            query_id="q011", question="What theory did Einstein develop?", answer="Relativity",
            context_titles_sentences=[("Albert Einstein", [shared_text])],
            supporting_titles=["Albert Einstein"],
        ),
    ]
    monkeypatch.setattr(hf_datasets, "load_dataset", lambda *a, **kw: _FakeHFDataset(fake_rows))

    from src.data.loaders import load_hotpotqa_distractor
    result = load_hotpotqa_distractor(split="validation", n_samples=None)

    # only ONE corpus entry for the shared article, not two
    assert len(result["corpus"]) == 1

    gold_q010 = result["queries"][0]["gold_doc_ids"]
    gold_q011 = result["queries"][1]["gold_doc_ids"]
    assert gold_q010 == gold_q011  # both point at the same canonical doc
