"""LLM backends behind one interface the orchestrator calls.

Two methods, provider-agnostic:
  * ``complete_json`` — cheap structured call (classification / claim extraction).
  * ``run_tool_loop`` — the custom agentic tool-use loop that IS the orchestrator
    (§2.1: not a wrapper). The model chooses which tools to call; we execute them
    and feed results back, until it emits the final card JSON.

Providers:
  * ``groq``      — free tier, Llama 3.3 70B, OpenAI-compatible tool calling.
  * ``anthropic`` — Fable 5 orchestrator + Haiku substeps (thinking always on;
    no temperature/budget_tokens; refusal fallback to Opus 4.8).
  * ``mock``      — no key configured; the orchestrator takes its deterministic
    path instead (still calls the real Google / local / rhetoric tools).

The provider is chosen by ``settings.active_provider``.
"""
from __future__ import annotations

import json
from typing import Callable

import httpx

from ..config import get_settings

# Tool dispatch signature: (tool_name, tool_input) -> result string.
Dispatch = Callable[[str, dict], str]


# ---- Groq (OpenAI-compatible) ---------------------------------------------
class _GroqBackend:
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def _post(self, body: dict) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=45.0) as client:
            r = client.post(self.URL, headers=headers, json=body)
            r.raise_for_status()
            return r.json()

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": system
                    + "\nВерни строго один JSON-объект по схеме:\n"
                    + json.dumps(schema, ensure_ascii=False),
                },
                {"role": "user", "content": user},
            ],
        }
        data = self._post(body)
        return json.loads(data["choices"][0]["message"]["content"])

    def run_tool_loop(
        self,
        system: str,
        user: str,
        tools: list[dict],
        dispatch: Dispatch,
        max_turns: int = 8,
    ) -> str:
        # Anthropic tool schema -> OpenAI function schema.
        oa_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        for _ in range(max_turns):
            data = self._post(
                {
                    "model": self.model,
                    "temperature": 0.2,
                    "max_tokens": 4000,
                    "messages": messages,
                    "tools": oa_tools,
                    "tool_choice": "auto",
                }
            )
            msg = data["choices"][0]["message"]
            messages.append(msg)
            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                return msg.get("content") or "{}"
            for tc in tool_calls:
                try:
                    args = json.loads(tc["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                out = dispatch(tc["function"]["name"], args)
                messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": out}
                )
        return "{}"


# ---- Anthropic (Fable 5 / Haiku) ------------------------------------------
_FALLBACK_BETA = "server-side-fallback-2026-06-01"
_FALLBACK_MODEL = "claude-opus-4-8"


class _AnthropicBackend:
    def __init__(self, api_key: str, orchestrator_model: str, substep_model: str):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self.orchestrator_model = orchestrator_model
        self.substep_model = substep_model

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        resp = self._client.messages.create(
            model=self.substep_model,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        return json.loads(text)

    def run_tool_loop(
        self,
        system: str,
        user: str,
        tools: list[dict],
        dispatch: Dispatch,
        max_turns: int = 8,
    ) -> str:
        messages: list[dict] = [{"role": "user", "content": user}]
        for _ in range(max_turns):
            resp = self._client.beta.messages.create(
                model=self.orchestrator_model,
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
                return "".join(b.text for b in resp.content if b.type == "text")
            results = []
            for tu in tool_uses:
                out = dispatch(tu.name, dict(tu.input))
                results.append(
                    {"type": "tool_result", "tool_use_id": tu.id, "content": out}
                )
            messages.append({"role": "user", "content": results})
        return "{}"


# ---- Facade ----------------------------------------------------------------
class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.provider = self.settings.active_provider
        self._backend = None
        if self.provider == "groq":
            self._backend = _GroqBackend(
                self.settings.groq_api_key, self.settings.groq_model
            )
        elif self.provider == "anthropic":
            self._backend = _AnthropicBackend(
                self.settings.anthropic_api_key,
                self.settings.orchestrator_model,
                self.settings.substep_model,
            )

    @property
    def available(self) -> bool:
        return self._backend is not None

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        assert self._backend is not None
        return self._backend.complete_json(system, user, schema)

    def run_tool_loop(
        self, system: str, user: str, tools: list[dict], dispatch: Dispatch
    ) -> str:
        assert self._backend is not None
        return self._backend.run_tool_loop(system, user, tools, dispatch)


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def reset_llm() -> None:
    """For tests / config reloads."""
    global _client
    _client = None
