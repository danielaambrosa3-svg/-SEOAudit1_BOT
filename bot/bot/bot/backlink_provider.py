import time
import logging
from dataclasses import dataclass, field

import requests

from bot import config

logger = logging.getLogger(__name__)

_LIST_KEYS = ["backlinks", "links", "data", "results", "items"]
_NESTED_LIST_KEYS = ["backlinks", "links", "items", "results"]
_TOTAL_KEYS = ["total_backlinks", "totalBacklinks", "backlinks_count", "total", "count"]
_REF_DOMAINS_KEYS = ["referring_domains", "referringDomains", "ref_domains", "domains_count"]
_SOURCE_URL_KEYS = ["source_url", "url_from", "referring_page", "source", "url"]
_TARGET_URL_KEYS = ["target_url", "url_to", "target", "destination"]
_ANCHOR_KEYS = ["anchor", "anchor_text", "anchorText"]
_DOFOLLOW_KEYS = ["dofollow", "is_dofollow", "follow"]


class BacklinkProviderError(Exception):
    pass


class BacklinkProviderNotConfigured(BacklinkProviderError):
    pass


@dataclass
class BacklinkSummary:
    domain: str
    total_backlinks: int | None
    referring_domains: int | None
    sample_links: list[dict] = field(default_factory=list)
    raw: dict | None = None


class _Cache:
    def __init__(self):
        self._store: dict[str, tuple[float, BacklinkSummary]] = {}

    def get(self, key: str) -> BacklinkSummary | None:
        entry = self._store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: BacklinkSummary):
        self._store[key] = (time.time() + config.CACHE_TTL_SECONDS, value)


_cache = _Cache()


def _first_present(d: dict, keys: list[str]):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _find_list(payload: dict) -> list:
    for key in _LIST_KEYS:
        val = payload.get(key)
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            for nested_key in _NESTED_LIST_KEYS:
                nested = val.get(nested_key)
                if isinstance(nested, list):
                    return nested
    return []


def _normalize_link(entry: dict) -> dict:
    return {
        "source": _first_present(entry, _SOURCE_URL_KEYS) or "unknown source",
        "target": _first_present(entry, _TARGET_URL_KEYS) or "",
        "anchor": _first_present(entry, _ANCHOR_KEYS) or "",
        "dofollow": _first_present(entry, _DOFOLLOW_KEYS),
    }


def fetch_backlinks(domain: str) -> BacklinkSummary:
    domain = domain.strip().lower()
    cached = _cache.get(domain)
    if cached:
        return cached

    if not (config.RAPIDAPI_KEY and config.RAPIDAPI_HOST and config.RAPIDAPI_ENDPOINT):
        raise BacklinkProviderNotConfigured(
            "Backlink API isn't configured yet. Set RAPIDAPI_KEY, RAPIDAPI_HOST, "
            "and RAPIDAPI_ENDPOINT (see .env.example)."
        )

    headers = {
        "x-rapidapi-key": config.RAPIDAPI_KEY,
        "x-rapidapi-host": config.RAPIDAPI_HOST,
    }
    params = {config.RAPIDAPI_DOMAIN_PARAM: domain}

    try:
        resp = requests.get(
            config.RAPIDAPI_ENDPOINT, headers=headers, params=params, timeout=20
        )
    except requests.RequestException as exc:
        raise BacklinkProviderError(f"Network error contacting backlink API: {exc}") from exc

    if resp.status_code == 429:
        raise BacklinkProviderError(
            "The backlink API's free-tier quota is used up for now. Try again later."
        )
    if not resp.ok:
        raise BacklinkProviderError(
            f"Backlink API returned an error (HTTP {resp.status_code})."
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise BacklinkProviderError("Backlink API returned a non-JSON response.") from exc

    if not isinstance(payload, dict):
        raise BacklinkProviderError("Unexpected response shape from backlink API.")

    total = _first_present(payload, _TOTAL_KEYS)
    ref_domains = _first_present(payload, _REF_DOMAINS_KEYS)
    raw_list = _find_list(payload)
    links = [_normalize_link(e) for e in raw_list if isinstance(e, dict)][:10]

    if total is None:
        total = len(raw_list) or None

    summary = BacklinkSummary(
        domain=domain,
        total_backlinks=total,
        referring_domains=ref_domains,
        sample_links=links,
        raw=payload if not links else None,
    )
    _cache.set(domain, summary)
    return summary
