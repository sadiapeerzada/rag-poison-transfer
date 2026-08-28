"""Generator interface.

Two backends:
- MLXGenerator: real 4-bit quantized model via mlx-lm (Section L of the
  foundation doc). Requires `pip install mlx-lm` and a model download,
  so it only runs on your Mac with internet access — not in a sandbox
  with restricted network access.
- MockGenerator: deterministic stub used for smoke-testing the pipeline
  wiring (retrieval -> prompt -> "generation" -> scoring) without
  needing any model weights. Never use this for real results — it does
  not do real language generation.

Both implement the same .generate(prompt) -> GenerationResult contract
so the rest of the pipeline never needs to know which one is active.
"""
import time
from dataclasses import dataclass


@dataclass
class GenerationResult:
    text: str
    latency_seconds: float
    prompt_tokens: int
    completion_tokens: int


class MockGenerator:
    """Deterministic stub for pipeline-wiring tests only. Not a real model."""

    def __init__(self):
        pass

    def generate(self, prompt: str, max_tokens: int = 64) -> GenerationResult:
        start = time.time()
        # Deterministic "answer" so tests are reproducible: just echoes
        # whether the gold-looking answer text appears in the prompt's
        # evidence, which is enough to sanity-check EM/F1 scoring logic.
        text = "mock-answer"
        elapsed = time.time() - start
        return GenerationResult(
            text=text,
            latency_seconds=elapsed,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(text.split()),
        )


class MLXGenerator:
    """Real generator backend. Run this on your Mac, not in a sandbox."""

    def __init__(self, model_name: str = "mlx-community/Qwen2.5-7B-Instruct-4bit"):
        try:
            from mlx_lm import load, generate
        except ImportError as e:
            raise ImportError(
                "mlx-lm is required for MLXGenerator. Install with:\n"
                "  pip install mlx-lm\n"
                "This backend only runs on Apple Silicon (your M4 MacBook Air)."
            ) from e
        self._generate_fn = generate
        self.model, self.tokenizer = load(model_name)

    def generate(self, prompt: str, max_tokens: int = 256) -> GenerationResult:
        start = time.time()
        text = self._generate_fn(
            self.model, self.tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False
        )
        elapsed = time.time() - start
        return GenerationResult(
            text=text,
            latency_seconds=elapsed,
            prompt_tokens=len(prompt.split()),  # rough proxy; swap for tokenizer counts later
            completion_tokens=len(text.split()),
        )
