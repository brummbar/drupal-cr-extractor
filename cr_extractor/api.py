"""Client for the drupal.org REST API (api-d7) change-record listing."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterator

API_BASE = "https://www.drupal.org/api-d7/node.json"
DRUPAL_CORE_PROJECT_NID = "3060"
USER_AGENT = "drupal-cr-extractor/1.0 (+local change-record mirror)"
PAGE_SIZE = 50
RETRIES = 3
PAGE_DELAY_SECONDS = 0.5


class ApiError(RuntimeError):
    """Raised when the API cannot be reached after retries."""


def listing_url(page: int, page_size: int = PAGE_SIZE) -> str:
    params = {
        "type": "changenotice",
        "field_project": DRUPAL_CORE_PROJECT_NID,
        "limit": str(page_size),
        "sort": "changed",
        "direction": "DESC",
        "page": str(page),
    }
    return f"{API_BASE}?{urllib.parse.urlencode(params)}"


def get_json(url: str) -> dict:
    """GET a JSON document with simple retry/backoff on transient failures."""
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code not in (429, 500, 502, 503, 504):
                raise ApiError(f"HTTP {error.code} for {url}") from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
        wait = 2 ** attempt
        print(f"  request failed ({last_error}); retrying in {wait}s", file=sys.stderr)
        time.sleep(wait)
    raise ApiError(f"giving up on {url}: {last_error}")


def iter_pages(start_page: int = 0, page_size: int = PAGE_SIZE) -> Iterator[tuple[int, list[dict], bool]]:
    """Yield (page_number, records, has_next) for each listing page, newest change first.

    Only the first URL is built locally; subsequent pages follow the `next` link the API
    returns, so the server owns the paging shape.
    """
    page = start_page
    url: str | None = listing_url(page, page_size)
    while url:
        payload = get_json(url)
        records = payload.get("list", [])
        next_url = payload.get("next") or None
        yield page, records, bool(next_url)
        url = next_url
        page += 1
        if url:
            time.sleep(PAGE_DELAY_SECONDS)
