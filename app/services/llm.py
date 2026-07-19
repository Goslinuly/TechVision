"""Anthropic client wrapper.

Exposes exactly the two shapes the orchestrator needs:

  * ``complete_json`` — a cheap, single-shot structured call for claim
    extraction / classification. Routed to Haiku 4.5 (§3: «не жечь Fable 5»).
  * ``run_tool_loop`` — the custom agentic tool-use loop that IS the
    orchestrator (§2.1: not a wrapper). Routed to Fable 5, which decides which
    tools to call per claim, then emits the final card as JSON.

When ``ANTHROPIC_API_KEY`` is unset, ``available`` is False and the orchestrator
takes its deterministic path instead — the app stays runnable offline.

Fable 5 specifics honored here (per the current API):
  * thinking is always on — we never pass a ``thinking`` param;
  * ``temperature`` / ``budget_tokens`` are not sent (they 400 on Fable 5);
  * server-side refusal fallback to Opus 4.8 is enabled by default.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from ..config import get_settings

# Tool dispatch signature: (tool_name, tool_input) -> result string.
Dispatch = Callable[[str, dict], str]

_FALLBACK_BETA = "server-side-fallback-2026-06-01"
_FALLBACK_MODEL = "claude-opus-4-8"


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        if self.settings.llm_enabled:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)

    @property
    def available(self) -> bool:
        return self._client is not None

    # -- cheap structured substep (Haiku) ------------------------------------
    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        """One structured call, guaranteed-JSON output. Used for classification
        and atomic-claim extraction."""
        assert self._client is not None
        resp = self._client.messages.create(
            model=self.settings.substep_model,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "format": {"type": "json_schema", "schema": schema}
            },
        )
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        return json.loads(text)

    # -- agentic tool-use loop (Fable 5) -------------------------------------
    def run_tool_loop(
        self,
        system: str,
        user: str,
        tools: list[dict],
        dispatch: Dispatch,
        max_turns: int = 8,
    ) -> str:
        """Drive the custom agentic cycle. Returns the model's final text
        (expected to be the card JSON). This is a hand-written loop — the model
        chooses tools, we execute them and feed results back — which is the
        anti-«пустая обёртка» core of §2.1."""
        assert self._client is not None
        messages: list[dict] = [{"role": "user", "content": user}]

        for _ in range(max_turns):
            resp = self._client.beta.messages.create(
                model=self.settings.orchestrator_model,
                max_tokens=8000,
                system=system,
                tools=tools,
                messages=messages,
                output_config={"effort": "high"},
                betas=[_FALLBACK_BETA],
                fallbacks=[{"model": _FALLBACK_MODEL}],
            )

            if resp.stop_reason == "refusal":
                return "{}"

            messages.append({"role": "assistant", "content": resp.content})

            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            if not tool_uses:
                # Done — return concatenated final text.
                return "".join(b.text for b in resp.content if b.type == "text")

            results = []
            for tu in tool_uses:
                out = dispatch(tu.name, dict(tu.input))
                results.append(
                    {"type": "tool_result", "tool_use_id": tu.id, "content": out}
                )
            messages.append({"role": "user", "content": results})

        # Ran out of turns — ask for the final card explicitly.
        return "".join(
            b.text
            for b in messages[-1].get("content", [])
            if isinstance(b, dict) and b.get("type") == "text"
        ) or "{}"


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
