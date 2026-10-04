"""Query rewrites for the Retrieval-Consistency Defense (RCD).

Rewrites depend ONLY on the question text, never on the corpus, so they
are generated once and reused for the clean corpus, every poisoned corpus,
every source/target pipeline and every ablation. Generation is the only
GPU-costly part of RCD, so the cache is append-only JSONL: if a Kaggle
session dies mid-run, re-running resumes where it stopped.

The cache is keyed by normalised question text (not query_id) so a
DefendedRetriever, which only receives the question string, can look up
rewrites without any extra plumbing.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

REWRITE_PROMPT = (
    "Rewrite the question below in {n} different ways that ask for exactly the "
    "same information. Keep every name, date, title and number unchanged. "
    "Change only the wording or sentence structure. Do NOT answer the question "
    "and do NOT add new information.\n\n"
    "Question: {question}\n\n"
    "Write each rewrite on its own line, numbered 1 to {n}, and nothing else."
)


def question_key(question: str) -> str:
    norm = " ".join(question.lower().split())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def parse_rewrites(raw: str, original: str, n: int) -> list[str]:
    """Turn raw generator output into up to n clean, distinct rewrites."""
    seen = {" ".join(original.lower().split())}
    out: list[str] = []
    for line in raw.splitlines():
        line = re.sub(r"^\s*(?:\d+[\.\)]|[-*•])\s*", "", line).strip().strip('"').strip()
        if len(line.split()) < 3:
            continue
        norm = " ".join(line.lower().split())
        if norm in seen:
            continue
        seen.add(norm)
        out.append(line)
        if len(out) == n:
            break
    return out


def generate_rewrites(generator, question: str, n: int = 3, max_tokens: int = 160) -> list[str]:
    raw = generator.generate(REWRITE_PROMPT.format(n=n, question=question), max_tokens=max_tokens)
    return parse_rewrites(raw.text, question, n)


class RewriteCache:
    """Append-only JSONL cache of {question -> rewrites}."""

    def __init__(self, path: str | None = None, generator=None, max_tokens: int = 160):
        self.path = path
        self.generator = generator
        self.max_tokens = max_tokens
        self._store: dict[str, list[str]] = {}
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        row = json.loads(line)
                        self._store[row["key"]] = row["rewrites"]

    def __len__(self) -> int:
        return len(self._store)

    def put(self, question: str, rewrites: list[str]) -> None:
        key = question_key(question)
        self._store[key] = list(rewrites)
        if self.path:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "question": question, "rewrites": rewrites},
                                   ensure_ascii=False) + "\n")
                f.flush()

    def get_rewrites(self, question: str, n: int) -> list[str]:
        """First n cached rewrites; generates (and caches) on a miss if a
        generator was supplied, otherwise raises so a missing rewrite can
        never silently turn into 'no rewrites'."""
        key = question_key(question)
        if key not in self._store:
            if self.generator is None:
                raise KeyError(
                    f"No cached rewrites for question {question[:60]!r} and no "
                    "generator attached. Run prefill() first."
                )
            self.put(question, generate_rewrites(self.generator, question, max(n, 4), self.max_tokens))
        return self._store[key][:n]

    def prefill(self, questions: list[str], n: int = 4, progress_every: int = 25) -> None:
        """Generate rewrites for all questions not yet cached (resumable)."""
        if self.generator is None:
            raise ValueError("prefill() needs a generator.")
        todo = [q for q in dict.fromkeys(questions) if question_key(q) not in self._store]
        for i, q in enumerate(todo, 1):
            self.put(q, generate_rewrites(self.generator, q, n, self.max_tokens))
            if progress_every and i % progress_every == 0:
                print(f"[rewrites] {i}/{len(todo)} generated", flush=True)

