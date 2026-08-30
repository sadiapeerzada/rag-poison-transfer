"""Generator interface.

Three backends:
- MLXGenerator: real 4-bit quantized model via mlx-lm (Section L of the
  foundation doc). Requires `pip install mlx-lm` and a model download,
  so it only runs on Apple Silicon -- your Mac, not Kaggle.
- TransformersGenerator: real model via `transformers` + `bitsandbytes`
  4-bit quantization, for CUDA GPUs (Kaggle T4/P100). Won't run on
  Apple Silicon -- use MLXGenerator there instead.
- MockGenerator: deterministic stub used for smoke-testing the pipeline
  wiring (retrieval -> prompt -> "generation" -> scoring) without
  needing any model weights. Never use this for real results -- it does
  not do real language generation.

All three implement the same .generate(prompt) -> GenerationResult
contract so the rest of the pipeline never needs to know which one is
active.
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
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(text.split()),
        )


class TransformersGenerator:
    """Real generator backend for CUDA GPUs (Kaggle). 4-bit quantized
    via bitsandbytes, same general approach as a standard Kaggle
    RAG-baseline setup. Requires a CUDA GPU -- won't run on Apple
    Silicon (use MLXGenerator there instead).
    """

    def __init__(self, model_name: str = "Qwen/Qwen2.5-7B-Instruct", load_in_4bit: bool = True):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        except ImportError as e:
            raise ImportError(
                "transformers, accelerate, and bitsandbytes are required. Install with:\n"
                "  pip install transformers accelerate bitsandbytes\n"
                "This backend requires a CUDA GPU (e.g. Kaggle's T4/P100), not Apple Silicon."
            ) from e

        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        quant_config = None
        if load_in_4bit:
            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
            )

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=quant_config,
            device_map="auto",
        )

    def generate(self, prompt: str, max_tokens: int = 256) -> GenerationResult:
        start = time.time()
        messages = [{"role": "user", "content": prompt}]
        # return_dict=True is explicit here because apply_chat_template's
        # return type (raw tensor vs. dict-like BatchEncoding) has changed
        # across transformers versions -- this makes the extraction below
        # version-independent instead of guessing based on whichever
        # version happens to be installed.
        encoded = self.tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
        )
        input_ids = encoded["input_ids"].to(self.model.device)
        attention_mask = encoded.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.model.device)

        with self._torch.no_grad():
            output_ids = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_tokens,
                do_sample=False,
            )

        completion_ids = output_ids[0][input_ids.shape[-1]:]
        text = self.tokenizer.decode(completion_ids, skip_special_tokens=True)
        elapsed = time.time() - start

        return GenerationResult(
            text=text,
            latency_seconds=elapsed,
            prompt_tokens=int(input_ids.shape[-1]),
            completion_tokens=int(completion_ids.shape[-1]),
        )
