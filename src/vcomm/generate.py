"""Text generators: a local GGUF model through llama-cpp-python, and a stub for CI/tests."""
from __future__ import annotations

import time
from typing import Protocol

from .facts import FactSheet


class Generator(Protocol):
    name: str
    def __call__(self, messages: list[dict], seed: int) -> str: ...


class LlamaCppGenerator:
    """Runs a quantised instruct model on CPU. No network calls, no API key."""

    def __init__(self, model_path: str, n_threads: int = 8, temperature: float = 0.3, max_tokens: int = 320,
                 n_ctx: int = 4096):
        from llama_cpp import Llama  # imported lazily so CI does not need it
        self.name = model_path.rsplit("/", 1)[-1]
        self.llm = Llama(model_path=model_path, n_ctx=n_ctx, n_threads=n_threads, verbose=False, seed=0)
        self.temperature, self.max_tokens = temperature, max_tokens
        self.last_usage: dict = {}

    def __call__(self, messages: list[dict], seed: int) -> str:
        t = time.time()
        r = self.llm.create_chat_completion(messages=messages, temperature=self.temperature, top_p=0.9,
                                            max_tokens=self.max_tokens, seed=seed)
        self.last_usage = dict(r.get("usage", {}), seconds=round(time.time() - t, 2))
        return r["choices"][0]["message"]["content"].strip()


class StubGenerator:
    """Deterministic stand-in for CI. Replays canned drafts in order, then falls back to the template.

    `script` maps a fact-sheet id to a list of drafts (one per attempt). Drafts may contain
    the placeholder {template}, replaced by the deterministic template text.
    """

    def __init__(self, sheets: dict[str, FactSheet], script: dict[str, list[str]] | None = None):
        from .template import template_commentary
        self.name = "stub"
        self.sheets, self.script = sheets, script or {}
        self.calls: dict[str, int] = {}
        self._tmpl = template_commentary
        self.last_usage: dict = {}

    def __call__(self, messages: list[dict], seed: int) -> str:
        body = messages[1]["content"]
        sid = next(k for k, sh in self.sheets.items()
                   if f"Subject: {sh.subject}\nPeriod: {sh.period} compared with {sh.comparison_period}" in body)
        i = self.calls.get(sid, 0)
        self.calls[sid] = i + 1
        drafts = self.script.get(sid, ["{template}"])
        d = drafts[min(i, len(drafts) - 1)]
        return d.replace("{template}", self._tmpl(self.sheets[sid]))
