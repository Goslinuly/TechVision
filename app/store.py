"""Ephemeral card store + short shareable ids.

The web card at /r/{id} is what users forward back into the chat (§4 →
organic growth). In-memory for the MVP; swap for Postgres/Redis in prod.
"""
from __future__ import annotations

import secrets

from .models import Card

_cards: dict[str, Card] = {}


def new_id() -> str:
    return secrets.token_hex(2)  # e.g. "a8f3"


def save(card: Card) -> Card:
    if not card.id:
        card.id = new_id()
    _cards[card.id] = card
    return card


def get(card_id: str) -> Card | None:
    return _cards.get(card_id)


def count() -> int:
    return len(_cards)
