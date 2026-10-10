"""Regression tests for ASR evidence-window semantics."""

from src.attacks.asr import evaluate_asr_for_retriever


class FakeDocument:
    def __init__(self, doc_id, text):
        self.doc_id = doc_id
        self.text = text


class FakeRetriever:
    def __init__(self, documents):
        self.documents = documents

    def retrieve(self, question, top_k):
        return self.documents[:top_k]


class FakeGenerator:
    def generate(self, prompt, max_tokens):
        class Result:
            text = "answer_0"

        return Result()


def test_poison_outside_generation_window_is_not_generator_visible():
    """A poison at rank 6 is diagnostic-only when generation uses top 5."""
    clean_docs = [
        FakeDocument(f"clean::{i}", f"Clean document {i}")
        for i in range(10)
    ]

    poison_id = "poison::test::q0::0::abc"
    poisoned_docs = clean_docs[:5] + [
        FakeDocument(poison_id, "Poison evidence")
    ] + clean_docs[6:]

    clean_data = {
        "corpus": [],
        "queries": [{
            "query_id": "q0",
            "question": "Question?",
            "gold_answer": "answer_0",
            "poison_doc_ids": [],
        }],
    }
    poisoned_data = {
        "corpus": [],
        "queries": [{
            "query_id": "q0",
            "question": "Question?",
            "gold_answer": "answer_0",
            "poison_doc_ids": [poison_id],
            "poison_target_answer": "wrong_answer",
        }],
    }

    result = evaluate_asr_for_retriever(
        clean_retriever=FakeRetriever(clean_docs),
        poisoned_retriever=FakeRetriever(poisoned_docs),
        clean_data=clean_data,
        poisoned_data=poisoned_data,
        generator=FakeGenerator(),
        source_pipeline="test",
        target_pipeline="test",
        top_k=5,
        retrieval_metric_k=10,
    )[0]

    assert result["poison_rank"] == 6
    assert len(result["retrieved_doc_ids"]) == 10
    assert result["poison_retrieved"] is False
