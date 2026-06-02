"""Build BizFinder preview URLs from a bare hostname.

Two patterns documented in .env.example:
    preview_id    -> {base}/preview?id=<host>          (the "Call us" button flow)
    preview_query -> {base}/?preview=<url-encoded host> (the "Talk to us" flow)
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

UrlPattern = Literal["preview_id", "preview_query"]


def build_preview_url(
    base_url: str,
    site: str,
    *,
    pattern: UrlPattern = "preview_id",
) -> str:
    base = base_url.rstrip("/")
    host = site.strip().lstrip("/")
    if pattern == "preview_id":
        return f"{base}/preview?id={host}"
    if pattern == "preview_query":
        return f"{base}/?preview={quote(host, safe='')}"
    raise ValueError(f"Unknown URL pattern: {pattern!r}")
