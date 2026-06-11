"""Model layer: a single OpenAI-compatible chat-completions client.

This is the literal mechanism behind sovereign-LLM portability: G42's Compass
API (JAIS, Llama 3, gpt-oss-20B/120B, Azure OpenAI GPT-4 family) exposes the
same chat-completions surface, so pointing LLM_BASE_URL at a Compass endpoint
and setting LLM_MODEL is the entire migration.
"""
import time
from openai import OpenAI

from .config import ModelConfig

# Rough $/1M-token prices for cost telemetry; override per deployment.
PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "default": (0.50, 2.00),
}


class LLMClient:
    def __init__(self, cfg: ModelConfig | None = None):
        self.cfg = cfg or ModelConfig()
        self._client = OpenAI(base_url=self.cfg.base_url, api_key=self.cfg.api_key)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """One chat-completions call. Returns the assistant message plus
        usage/latency metadata for the governance and telemetry layers."""
        t0 = time.perf_counter()
        resp = self._client.chat.completions.create(
            model=self.cfg.model,
            messages=messages,
            tools=tools or None,
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        msg = resp.choices[0].message
        usage = resp.usage
        in_tok = usage.prompt_tokens if usage else 0
        out_tok = usage.completion_tokens if usage else 0
        p_in, p_out = PRICES.get(self.cfg.model, PRICES["default"])
        cost_usd = (in_tok * p_in + out_tok * p_out) / 1_000_000
        return {
            "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}
                for tc in (msg.tool_calls or [])
            ],
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
        }
