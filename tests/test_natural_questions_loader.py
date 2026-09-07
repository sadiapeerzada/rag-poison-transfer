"""Tests for load_natural_questions.

Uses a mocked datasets.load_dataset (no real network calls) with rows
shaped exactly like real Natural Questions examples, confirmed against
a live sample during development.
"""
import pytest

from src.data.loaders import _reconstruct_text, load_natural_questions


class _FakeStreamingDataset:
    """Minimal stand-in for a HF streaming IterableDataset: supports
    .shuffle() (no-op, for deterministic tests) and iteration."""

    def __init__(self, rows):
        self._rows = rows

    def shuffle(self, seed=None, buffer_size=None):
        return self

    def __iter__(self):
        return iter(self._rows)


def make_nq_row(query_id, question, title, candidates, gold_candidate_index,
                 gold_short_answer_text=None, yes_no_answer=-1, no_gold=False):
    """Build a fake NQ row. `candidates` is a list of plain-text strings
    (already reconstructed, for test simplicity) -- the real function
    reconstructs from raw tokens, tested separately below.
    """
    all_tokens = []
    all_is_html = []
    starts, ends = [], []
    for text in candidates:
        start = len(all_tokens)
        for tok in text.split():
            all_tokens.append(tok)
            all_is_html.append(False)
        starts.append(start)
        ends.append(len(all_tokens))

    long_answer_annotations = [
        {"candidate_index": -1} for _ in range(4)
    ]
    if not no_gold:
        long_answer_annotations.append({"candidate_index": gold_candidate_index})
    else:
        long_answer_annotations.append({"candidate_index": -1})

    short_answers = [
        {"text": []} for _ in range(4)
    ]
    short_answers.append({"text": [gold_short_answer_text] if gold_short_answer_text else []})

    return {
        "id": query_id,
        "question": {"text": question},
        "document": {"title": title, "tokens": {"token": all_tokens, "is_html": all_is_html}},
        "long_answer_candidates": {"start_token": starts, "end_token": ends},
        "annotations": {
            "long_answer": long_answer_annotations,
            "short_answers": short_answers,
            "yes_no_answer": [-1, -1, -1, -1, yes_no_answer],
        },
    }


class TestReconstructText:
    def test_drops_html_tokens(self):
        tokens = ["<P>", "Hello", "world", "</P>"]
        is_html = [True, False, False, True]
        assert _reconstruct_text(tokens, is_html) == "Hello world"

    def test_empty_when_all_html(self):
        assert _reconstruct_text(["<P>", "</P>"], [True, True]) == ""

    def test_no_html_passthrough(self):
        assert _reconstruct_text(["a", "b", "c"], [False, False, False]) == "a b c"


class TestLoadNaturalQuestions:
    def test_basic_extraction(self, monkeypatch):
        row = make_nq_row(
            query_id="q1", question="what is the capital of France",
            title="France",
            candidates=["Paris is the capital of France.", "France is in Europe."],
            gold_candidate_index=0,
            gold_short_answer_text="Paris",
        )
        fake_ds = _FakeStreamingDataset([row])
        monkeypatch.setattr("datasets.load_dataset", lambda *a, **kw: fake_ds)

        data = load_natural_questions(n_samples=1)
        assert len(data["queries"]) == 1
        assert len(data["corpus"]) == 2
        q = data["queries"][0]
        assert q["gold_answer"] == "Paris"
        assert len(q["gold_doc_ids"]) == 1

    def test_gold_doc_id_resolves_to_correct_candidate_text(self, monkeypatch):
        row = make_nq_row(
            query_id="q1", question="test question",
            title="Doc",
            candidates=["wrong candidate text", "correct gold candidate text"],
            gold_candidate_index=1,
            gold_short_answer_text="gold",
        )
        fake_ds = _FakeStreamingDataset([row])
        monkeypatch.setattr("datasets.load_dataset", lambda *a, **kw: fake_ds)

        data = load_natural_questions(n_samples=1)
        q = data["queries"][0]
        gold_doc = next(d for d in data["corpus"] if d["doc_id"] == q["gold_doc_ids"][0])
        assert "correct gold candidate" in gold_doc["text"]

    def test_skips_query_with_no_valid_long_answer(self, monkeypatch):
        row = make_nq_row(
            query_id="q1", question="unanswerable question", title="Doc",
            candidates=["some text"], gold_candidate_index=0, no_gold=True,
        )
        fake_ds = _FakeStreamingDataset([row])
        monkeypatch.setattr("datasets.load_dataset", lambda *a, **kw: fake_ds)

        data = load_natural_questions(n_samples=1)
        assert len(data["queries"]) == 0

    def test_falls_back_to_yes_no_answer(self, monkeypatch):
        row = make_nq_row(
            query_id="q1", question="is Paris in France", title="Doc",
            candidates=["Paris is in France."], gold_candidate_index=0,
            gold_short_answer_text=None, yes_no_answer=1,
        )
        fake_ds = _FakeStreamingDataset([row])
        monkeypatch.setattr("datasets.load_dataset", lambda *a, **kw: fake_ds)

        data = load_natural_questions(n_samples=1)
        assert data["queries"][0]["gold_answer"] == "yes"

    def test_skips_when_long_answer_present_but_no_extractable_answer(self, monkeypatch):
        row = make_nq_row(
            query_id="q1", question="ambiguous question", title="Doc",
            candidates=["some text"], gold_candidate_index=0,
            gold_short_answer_text=None, yes_no_answer=-1,
        )
        fake_ds = _FakeStreamingDataset([row])
        monkeypatch.setattr("datasets.load_dataset", lambda *a, **kw: fake_ds)

        data = load_natural_questions(n_samples=1)
        assert len(data["queries"]) == 0

    def test_dedupes_identical_candidate_text_across_queries(self, monkeypatch):
        shared_text = "This exact paragraph appears in both rows."
        row1 = make_nq_row(
            query_id="q1", question="q1", title="Doc",
            candidates=[shared_text], gold_candidate_index=0, gold_short_answer_text="a",
        )
        row2 = make_nq_row(
            query_id="q2", question="q2", title="Doc",
            candidates=[shared_text], gold_candidate_index=0, gold_short_answer_text="b",
        )
        fake_ds = _FakeStreamingDataset([row1, row2])
        monkeypatch.setattr("datasets.load_dataset", lambda *a, **kw: fake_ds)

        data = load_natural_questions(n_samples=2)
        assert len(data["queries"]) == 2
        assert len(data["corpus"]) == 1  # deduped, same title+text -> same canonical ID

    def test_respects_n_samples_limit(self, monkeypatch):
        rows = [
            make_nq_row(query_id=f"q{i}", question=f"q{i}", title="Doc",
                        candidates=["text"], gold_candidate_index=0, gold_short_answer_text="a")
            for i in range(10)
        ]
        fake_ds = _FakeStreamingDataset(rows)
        monkeypatch.setattr("datasets.load_dataset", lambda *a, **kw: fake_ds)

        data = load_natural_questions(n_samples=3)
        assert len(data["queries"]) == 3
