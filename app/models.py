"""Pydantic data models — the shared contract across the pipeline.

These are the structures the orchestrator produces and the bot / web-card
consume. The card (`Card`) is the ключевая фича described in §4 of the TZ:
not a verdict, but an explainable breakdown.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Lang(str, Enum):
    KK = "kk"  # Kazakh
    RU = "ru"  # Russian


class MessageClass(str, Enum):
    """§2.1 step 1 — high-level classification of the incoming message."""

    FACT = "fact"  # contains checkable factual claims
    OPINION = "opinion"  # opinion / forecast — not checked
    MANIPULATION = "manipulation"  # only rhetorical manipulation, no facts
    MIXED = "mixed"  # facts + opinion + manipulation


class ClaimKind(str, Enum):
    CHECKABLE = "checkable"  # atomic, verifiable statement
    OPINION = "opinion"  # value judgement / prediction — not checked


class Verdict(str, Enum):
    REFUTED = "refuted"  # ❌ found refuted in a fact-check source
    SUPPORTED = "supported"  # ✅ found supported
    NOT_FOUND = "not_found"  # ⚠️ no data in bases
    NOT_CHECKABLE = "not_checkable"  # 💭 opinion / not a factual claim


VERDICT_EMOJI = {
    Verdict.REFUTED: "❌",
    Verdict.SUPPORTED: "✅",
    Verdict.NOT_FOUND: "⚠️",
    Verdict.NOT_CHECKABLE: "💭",
}


class Evidence(BaseModel):
    """A single supporting/refuting item from a tool."""

    source: str  # "Factcheck.kz", "Google Fact Check", ...
    title: str = ""
    url: str = ""
    rating: str = ""  # publisher's textual rating, e.g. "Ложь"
    similarity: Optional[float] = None  # for local vector matches


class ClaimResult(BaseModel):
    text: str
    kind: ClaimKind
    verdict: Verdict
    confidence: float = 0.0  # §5 confidence formula output, 0..1
    evidence: list[Evidence] = Field(default_factory=list)
    note: str = ""  # short human-readable note (in message language)


class Manipulation(BaseModel):
    """A detected rhetorical technique with its span in the source text."""

    technique: str  # canonical key, e.g. "fear_appeal"
    label: str  # localized label shown to the user
    span_text: str  # the exact phrase highlighted
    start: int  # char offset in the source text
    end: int
    explanation: str = ""


class Card(BaseModel):
    """The breakdown card — §4 of the TZ."""

    id: str = ""
    lang: Lang
    source_text: str
    message_class: MessageClass
    claims: list[ClaimResult] = Field(default_factory=list)
    manipulations: list[Manipulation] = Field(default_factory=list)
    reply_suggestion: str = ""  # «Как можно ответить»
    used_llm: bool = False  # real Fable 5 loop vs deterministic mock
    tools_called: list[str] = Field(default_factory=list)

    @property
    def url(self) -> str:
        return f"/r/{self.id}"
