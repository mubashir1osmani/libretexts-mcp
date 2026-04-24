"""Thin client for the LibreTexts MindTouch (DekiAPI) endpoints.

Each library is its own MindTouch instance at `{library}.libretexts.org`.
The API is reached at `/@api/deki/...` and returns JSON when the query
string includes `dream.out.format=json`.
"""

from __future__ import annotations

import re
import time
from urllib.parse import quote

import httpx
from markdownify import markdownify

_UA = "Mozilla/5.0 (libretexts-mcp)"
_TOKEN_RE = re.compile(r'apiToken":"([^"]+)"')
_token_cache: dict[str, tuple[str, float]] = {}
_TOKEN_TTL = 600.0  # seconds


async def _get_token(client: httpx.AsyncClient, host: str) -> str:
    cached = _token_cache.get(host)
    now = time.monotonic()
    if cached and now - cached[1] < _TOKEN_TTL:
        return cached[0]
    r = await client.get(f"https://{host}/", headers={"User-Agent": _UA})
    r.raise_for_status()
    m = _TOKEN_RE.search(r.text)
    if not m:
        raise LibreTextsError(f"Could not harvest apiToken from {host}")
    tok = m.group(1)
    _token_cache[host] = (tok, now)
    return tok


def _headers(token: str) -> dict[str, str]:
    return {"User-Agent": _UA, "X-Deki-Token": token}

LIBRARIES: dict[str, str] = {
    "phys": "phys.libretexts.org",
    "math": "math.libretexts.org",
    "chem": "chem.libretexts.org",
    "eng": "eng.libretexts.org",
    "bio": "bio.libretexts.org",
    "stats": "stats.libretexts.org",
    "geo": "geo.libretexts.org",
}

DEFAULT_TIMEOUT = 30.0


class LibreTextsError(RuntimeError):
    pass



def _host(library: str) -> str:
    if library not in LIBRARIES:
        raise LibreTextsError(
            f"Unknown library {library!r}. Valid: {sorted(LIBRARIES)}"
        )
    return LIBRARIES[library]


def _page_ref(path_or_id: str) -> str:
    """MindTouch page refs: numeric ID as-is, otherwise `=` + URL-encoded path."""
    if path_or_id.isdigit() or path_or_id == "home":
        return path_or_id
    # `=` prefix tells DekiAPI the ref is a path. MindTouch requires
    # double-URL-encoding (so `/` → `%252F`).
    return "=" + quote(quote(path_or_id, safe=""), safe="")


async def _get_json(client: httpx.AsyncClient, host: str, url: str) -> dict:
    token = await _get_token(client, host)
    r = await client.get(
        url,
        params={"dream.out.format": "json"},
        headers=_headers(token),
    )
    r.raise_for_status()
    return r.json()


async def search(library: str, query: str, limit: int = 10) -> list[dict]:
    host = _host(library)
    url = f"https://{host}/@api/deki/site/query"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        token = await _get_token(client, host)
        r = await client.get(
            url,
            params={"q": query, "limit": str(limit), "dream.out.format": "json"},
            headers=_headers(token),
        )
        r.raise_for_status()
        data = r.json()
    results = data.get("result", [])
    if isinstance(results, dict):
        results = [results]
    out = []
    for hit in results[:limit]:
        page = hit.get("page", {}) if isinstance(hit.get("page"), dict) else {}
        title = hit.get("title") or page.get("title") or ""
        content = (hit.get("content") or "").strip()
        out.append({
            "id": hit.get("id") or page.get("@id"),
            "title": title.strip() if isinstance(title, str) else "",
            "path": page.get("path") or hit.get("path"),
            "uri": page.get("uri.ui") or hit.get("uri.ui"),
            "snippet": content[:300],
        })
    return out


async def get_page(library: str, path_or_id: str) -> dict:
    host = _host(library)
    ref = _page_ref(path_or_id)
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        info = await _get_json(client, host, f"https://{host}/@api/deki/pages/{ref}/info")
        contents = await _get_json(
            client, host, f"https://{host}/@api/deki/pages/{ref}/contents"
        )
    body_html = ""
    body = contents.get("body")
    if isinstance(body, list):
        body_html = "".join(b for b in body if isinstance(b, str))
    elif isinstance(body, str):
        body_html = body
    elif isinstance(body, dict):
        body_html = body.get("#text", "")
    markdown = markdownify(body_html, heading_style="ATX") if body_html else ""
    return {
        "id": info.get("@id"),
        "title": (info.get("title") or "").strip(),
        "uri": info.get("uri.ui"),
        "path": info.get("path", {}).get("#text") if isinstance(info.get("path"), dict) else info.get("path"),
        "markdown": markdown.strip(),
    }


async def list_toc(library: str, path_or_id: str = "home") -> dict:
    """Return the subtree (table of contents) under a page.

    `path_or_id="home"` returns the library's top-level bookshelf.
    """
    host = _host(library)
    ref = _page_ref(path_or_id)
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        data = await _get_json(client, host, f"https://{host}/@api/deki/pages/{ref}/tree")

    def walk(node: dict, depth: int = 0) -> list[dict]:
        if not isinstance(node, dict):
            return []
        flat = [{
            "depth": depth,
            "id": node.get("@id"),
            "title": (node.get("title") or "").strip(),
            "path": node.get("path", {}).get("#text") if isinstance(node.get("path"), dict) else node.get("path"),
            "uri": node.get("uri.ui"),
        }]
        subpages = node.get("subpages", {})
        children = subpages.get("page") if isinstance(subpages, dict) else None
        if isinstance(children, dict):
            children = [children]
        for c in children or []:
            flat.extend(walk(c, depth + 1))
        return flat

    root = data.get("page", data)
    nodes = walk(root)
    return {"library": library, "root": nodes[0] if nodes else None, "nodes": nodes}
