import pytest
from datasets import load_dataset as real_load_dataset
from src.data import loaders


class FakeDataset:
    def __init__(self, rows):
        self.rows = list(rows)

    def __getitem__(self, key):
        return [row[key] for row in self.rows]

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return len(self.rows)

    def select(self, indices):
        return FakeDataset([self.rows[i] for i in indices])


def make_row(query_id):
    title = f"Title {query_id}"
    return {
        "id": query_id,
        "context": {
            "title": [title],
            "sentences": [[f"Text for {query_id}."]],
        },
        "supporting_facts": {
            "title": [title],
            "sent_id": [0],
        },
        "question": f"Question {query_id}?",
        "answer": f"Answer {query_id}",
    }


@pytest.fixture
def patch_dataset(monkeypatch):
    captured = {}
    rows = [make_row("q1"), make_row("q2"), make_row("q3")]

    def fake_load_dataset(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeDataset(rows)

    monkeypatch.setattr("datasets.load_dataset", fake_load_dataset)
    return captured, rows


def test_selects_exact_ids_in_manifest_order(patch_dataset):
    captured, _ = patch_dataset

    result = loaders.load_hotpotqa_distractor(
        split="validation",
        revision="revision-test",
        query_ids=["q3", "q1"],
    )

    assert [q["query_id"] for q in result["queries"]] == ["q3", "q1"]
    assert captured["kwargs"]["split"] == "validation"
    assert captured["kwargs"]["revision"] == "revision-test"


def test_missing_query_id_fails_closed(patch_dataset):
    with pytest.raises(ValueError, match="missing from dataset"):
        loaders.load_hotpotqa_distractor(query_ids=["q-missing"])


def test_duplicate_requested_ids_are_rejected(patch_dataset):
    with pytest.raises(ValueError, match="duplicate IDs"):
        loaders.load_hotpotqa_distractor(query_ids=["q1", "q1"])


def test_duplicate_dataset_ids_are_rejected(patch_dataset):
    _, rows = patch_dataset
    rows.append(make_row("q1"))

    with pytest.raises(ValueError, match="duplicate requested query ID"):
        loaders.load_hotpotqa_distractor(query_ids=["q1"])
