"""Google Fact Check Tools API — claims.search (REAL integration).

Docs: https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search
Returns published fact-check ratings for a claim, filtered by language.
"""
from __future__ import annotations

import httpx

from ..config import get_settings
from ..models import Evidence, Verdict

_ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

# Publisher textual ratings map crudely onto our verdicts. Real ratings are
# free text per publisher; this covers the common ru/en cases.
_REFUTE_WORDS = (
    "false", "ложь", "фейк", "неправда", "жалған", "misleading",
    "вводит в заблуждение", "pants on fire", "fake",
)
_SUPPORT_WORDS = ("true", "правда", "верно", "correct", "ақиқат", "шын")


def _rating_to_verdict(rating: str) -> Verdict:
    low = rating.lower()
    if any(w in low for w in _REFUTE_WORDS):
        return Verdict.REFUTED
    if any(w in low for w in _SUPPORT_WORDS):
        return Verdict.SUPPORTED
    return Verdict.NOT_FOUND


def search(claim: str, lang: str = "ru") -> dict:
    """Query Google Fact Check. Returns {"verdict", "matches"}. Network / auth
    failures degrade to an empty result rather than crashing the pipeline."""
    settings = get_settings()
    if not settings.google_factcheck_api_key:
        return {"verdict": None, "matches": [], "error": "no_api_key"}

    params = {
        "query": claim,
        "languageCode": lang,
        "key": settings.google_factcheck_api_key,
        "pageSize": 5,
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(_ENDPOINT, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:  # noqa: BLE001
        return {"verdict": None, "matches": [], "error": str(exc)}

    matches: list[Evidence] = []
    best_verdict: Verdict | None = None
    for claim_row in data.get("claims", []):
        for review in claim_row.get("claimReview", []):
            rating = review.get("textualRating", "")
            # Some publishers put the verdict word in the title, not the rating.
            verdict = _rating_to_verdict(
                f"{rating} {review.get('title', '')}"
            )
            matches.append(
                Evidence(
                    source=review.get("publisher", {}).get("name", "Google Fact Check"),
                    title=review.get("title", claim_row.get("text", "")),
                    url=review.get("url", ""),
                    rating=rating,
                )
            )
            if best_verdict is None and verdict != Verdict.NOT_FOUND:
                best_verdict = verdict

    return {
        "verdict": best_verdict.value if best_verdict else None,
        "matches": [m.model_dump() for m in matches[:5]],
    }
