"""Pinned local-only MLX adapter. Import/construction never imports MLX or loads weights."""
import copy
import importlib
from pathlib import Path
import random
import re
import time

from src.experiments.semantic_v3_preparation import file_sha
from src.pipelines.generator import GenerationResult


def validate_snapshot(runtime):
    snapshot = Path(runtime.get('snapshot_path', ''))
    provenance = runtime['model_provenance']
    identity = provenance.get('model_identity')
    if (not snapshot.is_absolute() or snapshot.resolve() != snapshot or not snapshot.is_dir()
            or snapshot.parent.name != 'snapshots' or not re.fullmatch('[0-9a-f]{40}', snapshot.name)
            or not isinstance(identity, str) or snapshot.parent.parent.name != 'models--' + identity.replace('/', '--')
            or provenance.get('revision') != snapshot.name):
        raise ValueError('Canonical pinned local model snapshot required')
    refs = runtime.get('model_files', [])
    expected = {}
    for ref in refs:
        path = Path(ref['path'])
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('Absolute model inventory paths required')
        try:
            name = path.relative_to(snapshot).as_posix()
        except ValueError as exc:
            raise ValueError('Model inventory outside snapshot') from exc
        if name in expected:
            raise ValueError('Duplicate model inventory entry')
        expected[name] = ref['sha256']
    actual = {p.relative_to(snapshot).as_posix(): file_sha(p)
              for p in snapshot.rglob('*') if p.is_file()}
    if (not {'config.json', 'tokenizer.json', 'tokenizer_config.json'} <= expected.keys()
            or not any(k.endswith('.safetensors') for k in expected)
            or actual != expected or provenance.get('model_files_sha256') != expected):
        raise ValueError('Complete model/tokenizer inventory or provenance mismatch')
    if provenance.get('decoding') != {'sampler': 'explicit greedy', 'temperature': 0.0}:
        raise ValueError('Explicit greedy decoding required')
    return snapshot


class LazyMLXAdapter:
    def __init__(self, runtime):
        self.runtime = copy.deepcopy(runtime)
        self.model_provenance = copy.deepcopy(runtime['model_provenance'])
        self.model = self.tokenizer = self.core = self.generate_fn = self.sampler = None
        self.seed = None

    def set_runtime_seed(self, seed):
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError('Explicit uint32 backend seed required')
        self.seed = seed

    def _load(self):
        # Recheck bytes at the actual loading boundary; never resolve a remote name.
        snapshot = validate_snapshot(self.runtime)
        self.core = importlib.import_module('mlx.core')
        lm = importlib.import_module('mlx_lm')
        sampling = importlib.import_module('mlx_lm.sample_utils')
        self.model, self.tokenizer = lm.load(str(snapshot), lazy=True,
            tokenizer_config={'local_files_only':True,'trust_remote_code':False})
        self.generate_fn = lm.generate
        self.sampler = sampling.make_sampler(temp=0.0)

    def prepare(self):
        """Load only after journal admission; never generate or sample."""
        if self.model is None:
            self._load()

    def generate(self, prompt, max_tokens=150):
        if self.seed is None or max_tokens != 150 or not isinstance(prompt, str):
            raise ValueError('Seed, exact token budget and text prompt required')
        if self.model is None:
            self._load()
        # Reset immediately before each actual call, including after lazy loading.
        random.seed(self.seed)
        import numpy as np
        np.random.seed(self.seed)
        self.core.random.seed(self.seed)
        formatted = self.tokenizer.apply_chat_template(
            [{'role': 'user', 'content': prompt}], tokenize=False, add_generation_prompt=True)
        started = time.perf_counter()
        text = self.generate_fn(self.model, self.tokenizer, prompt=formatted,
                                max_tokens=150, sampler=self.sampler, verbose=False)
        elapsed = time.perf_counter() - started
        if not isinstance(text, str):
            raise TypeError('MLX returned non-text output')
        return GenerationResult(text, elapsed, len(self.tokenizer.encode(formatted)),
                                len(self.tokenizer.encode(text, add_special_tokens=False)), formatted)
