from src.defenses.rcd.core import build_consistency_signals
from src.defenses.rcd.redundancy import evidence_redundancy
from src.defenses.rcd.conflict import evidence_conflict_scores
from src.defenses.rcd.scoring import score_documents
from dataclasses import dataclass

@dataclass
class RetrievedDocument:
    doc_id: str
    text: str


def test_rcd_components_smoke():
    retriever_rankings = [
        ["d1", "d2", "d3"],
        ["d1", "d3", "d2"],
    ]

    rewrite_rankings = [
        ["d1", "d2", "d3"],
        ["d1", "d3", "d2"],
    ]

    signals = build_consistency_signals(
        retriever_rankings,
        rewrite_rankings,
        top_k=3,
    )

    documents = [
        RetrievedDocument("d1", "Paris is the capital of France."),
        RetrievedDocument("d2", "Berlin is the capital of Germany."),
        RetrievedDocument("d3", "Madrid is the capital of Spain."),
    ]

    redundancy = evidence_redundancy(documents)
    conflict = evidence_conflict_scores(documents)

    scores = score_documents(
        signals,
        redundancy,
        conflict,
        base_rankings=["d1", "d2", "d3"],
    )

    assert scores
    assert "d1" in scores
    assert scores["d1"].final_score >= scores["d3"].final_score

def test_claim_conflict_distinguishes_related_and_unrelated_years():
    from src.defenses.rcd.conflict import claim_conflict

    assert claim_conflict(
        "The company was founded in 1990.",
        "The company was founded in 2000.",
    ) == 1.0

    assert claim_conflict(
        "The company was founded in 1990.",
        "The capital city was Paris in 2000.",
    ) == 0.0

    assert claim_conflict(
        "The company was founded in 1990.",
        "The company was founded in 1990.",
    ) == 0.0
