"""Parser for Factcheck.kz → local corpus (§6 №3).

Factcheck.kz runs a Next.js frontend (no WP REST / __NEXT_DATA__), but article
pages reliably expose Open Graph metadata (og:title / og:description) and the
verdict label appears in the rendered HTML. This module:

  1. enumerates article URLs (sitemap, else homepage links);
  2. per article, extracts claim (og:title), summary (og:description), and a
     best-effort verdict by scanning for rating labels;
  3. emits entries in the same schema as data/factcheck_kz_sample.json.

Best-effort by design: verdict labels vary by category, so `parse_article`
returns verdict=None when no label is found (such articles are monitoring
pieces, not verdict-bearing fact-checks). Be polite — a delay and a real
User-Agent are built in; keep `limit` small.
"""
from __future__ import annotations

import re
import time

import httpx

from ..services.lang import detect_lang

BASE = "https://factcheck.kz"
_UA = {"User-Agent": "AqiqatCorpusBuilder/0.1 (hackathon; +https://factcheck.kz)"}

# Rating cue (case-insensitive) -> (verdict, human-readable rating label).
_LABELS: list[tuple[str, str, str]] = [
    ("фейк", "refuted", "Фейк"),
    ("ложь", "refuted", "Ложь"),
    ("жалған", "refuted", "Жалған"),
    ("манипуляц", "refuted", "Манипуляция"),
    ("искажение", "refuted", "Искажение"),
    ("не соответствует", "refuted", "Не соответствует"),
    ("полуправда", "not_found", "Полуправда"),
    ("вырвано из контекста", "not_found", "Вырвано из контекста"),
    ("правда", "supported", "Правда"),
    ("ақиқат", "supported", "Ақиқат"),
]

# Rating-prefixed titles ("ЛОЖЬ | ...") — strip the prefix for a clean claim.
_PREFIX = re.compile(
    r"^\s*(ложь|правда|полуправда|фейк|манипуляция|жалған|ақиқат|искажение)\s*[|｜:]\s*",
    re.IGNORECASE,
)


def _get(url: str) -> str:
    r = httpx.get(url, timeout=10.0, headers=_UA, follow_redirects=True)
    r.raise_for_status()
    return r.text


def list_article_urls(limit: int = 30) -> list[str]:
    """Collect article URLs from the sitemap, falling back to homepage links."""
    urls: list[str] = []
    try:
        sm = _get(f"{BASE}/sitemap.xml")
        urls = re.findall(r"<loc>(https://factcheck\.kz/articles/[^<]+)</loc>", sm)
    except httpx.HTTPError:
        pass
    if not urls:
        html = _get(f"{BASE}/")
        slugs = sorted(set(re.findall(r'/articles/([a-z0-9\-]+)', html)))
        urls = [f"{BASE}/articles/{s}" for s in slugs]
    # de-dup, keep order
    seen: set[str] = set()
    ordered = [u for u in urls if not (u in seen or seen.add(u))]
    return ordered[:limit]


def _meta(html: str, key: str) -> str:
    m = re.search(
        rf'<meta[^>]+(?:property|name)="{re.escape(key)}"[^>]+content="([^"]*)"',
        html,
    )
    return m.group(1).strip() if m else ""


def _extract_verdict(html: str) -> tuple[str, str] | None:
    """Return (verdict, human-readable rating label), or None."""
    low = html.lower()
    for cue, verdict, label in _LABELS:
        if cue in low:
            return verdict, label
    return None


def parse_article(url: str) -> dict | None:
    """Return a corpus entry, or None if the page has no verdict / no title."""
    try:
        html = _get(url)
    except httpx.HTTPError:
        return None
    title = _meta(html, "og:title") or _meta(html, "title")
    if not title:
        return None
    found = _extract_verdict(html)
    if found is None:
        return None  # monitoring piece, not a verdict-bearing fact-check
    verdict, rating = found
    claim = _PREFIX.sub("", title).strip()  # drop "ЛОЖЬ | " prefix if present
    summary = _meta(html, "og:description") or _meta(html, "description")
    return {
        "id": url.rstrip("/").rsplit("/", 1)[-1][:60],
        "lang": detect_lang(claim).value,
        "claim": claim,
        "verdict": verdict,
        "rating": rating,
        "title": claim,
        "url": url,
        "summary": summary,
    }


def build_corpus(limit: int = 30, delay: float = 0.5) -> list[dict]:
    entries: list[dict] = []
    for url in list_article_urls(limit):
        entry = parse_article(url)
        if entry:
            entries.append(entry)
        time.sleep(delay)  # be polite to the source
    return entries
