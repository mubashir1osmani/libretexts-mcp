"""LibreTexts MCP server.

Exposes search / page / TOC tools plus per-library bookshelf resources so
Claude can tutor from primary-source open textbooks (phys, math, chem, eng,
bio, stats, geo).
"""

from __future__ import annotations

import json
import os
from typing import Literal

from mcp.server.fastmcp import FastMCP

from . import client as lt

_HOST = os.getenv("LIBRETEXTS_MCP_HOST", "0.0.0.0")
_PORT = int(os.getenv("LIBRETEXTS_MCP_PORT", "8765"))

mcp = FastMCP("libretexts", host=_HOST, port=_PORT)

Library = Literal["phys", "math", "chem", "eng", "bio", "stats", "geo"]


@mcp.tool()
async def search(query: str, library: Library = "phys", limit: int = 10) -> str:
    """Search a LibreTexts library. Returns title + path + uri for each hit.

    Args:
        query: free-text search (e.g. "orbital mechanics", "Navier-Stokes").
        library: one of phys, math, chem, eng, bio, stats, geo.
        limit: max hits (default 10).
    """
    hits = await lt.search(library, query, limit=limit)
    return json.dumps(hits, indent=2)


@mcp.tool()
async def get_page(library: Library, path_or_id: str) -> str:
    """Fetch a page's full content as Markdown.

    Args:
        library: one of phys, math, chem, eng, bio, stats, geo.
        path_or_id: either a numeric MindTouch page id, or the URL path
            (e.g. "Bookshelves/Classical_Mechanics/...").
    """
    page = await lt.get_page(library, path_or_id)
    return json.dumps(page, indent=2)


@mcp.tool()
async def list_toc(library: Library, path_or_id: str = "home") -> str:
    """List the table of contents (subtree) under a page.

    Use `path_or_id="home"` to get the library's top-level bookshelf,
    or pass a book path to get its chapters.
    """
    toc = await lt.list_toc(library, path_or_id)
    return json.dumps(toc, indent=2)


# ---------- Resources ----------
# One resource per library bookshelf. Claude can attach these to get
# a ready-made catalog without a tool call.

def _shelf_resource(library: str, label: str):
    @mcp.resource(f"libretexts://shelf/{library}", name=f"{label} bookshelf")
    async def _res() -> str:
        toc = await lt.list_toc(library, "home")
        return json.dumps(toc, indent=2)
    _res.__name__ = f"shelf_{library}"
    return _res


_shelf_resource("phys", "Physics")
_shelf_resource("math", "Mathematics")
_shelf_resource("chem", "Chemistry")
_shelf_resource("eng", "Engineering")
_shelf_resource("bio", "Biology")
_shelf_resource("stats", "Statistics")
_shelf_resource("geo", "Geosciences")


# ---------- Prompts ----------

@mcp.prompt()
def problem_set(topic: str, library: Library = "phys", n: int = 5) -> str:
    """Pull practice problems on a topic and quiz me one at a time."""
    return (
        f"Use the `search` tool on library={library} for exercise/problem pages "
        f"about '{topic}' (try queries like '{topic} exercises', '{topic} problems'). "
        f"Pick {n} problems of increasing difficulty from the results — fetch each "
        "with `get_page` to read the actual statement. Then quiz me one at a time:\n"
        "  1. Present the problem, no solution.\n"
        "  2. Wait for my answer.\n"
        "  3. Grade it, show the correct approach, and flag the concept I'm weak on.\n"
        "  4. Move on only when I say 'next'."
    )


@mcp.prompt()
def explain_like_prereqs(path_or_id: str, library: Library = "phys") -> str:
    """Explain a page bottom-up after checking which prereqs I actually know."""
    return (
        f"Fetch {library}/{path_or_id} with `get_page`. Before explaining the content:\n"
        "  1. List the prerequisite concepts the page assumes (math + physics).\n"
        "  2. Ask me which ones I'm shaky on — wait for my answer.\n"
        "  3. Then teach the page bottom-up, filling the gaps I flagged first.\n"
        "Use concrete aerospace examples (aircraft, orbits, propulsion) wherever the "
        "page is abstract."
    )


@mcp.prompt()
def study_session(book_path: str, library: Library = "phys", minutes: int = 30) -> str:
    """Run a focused study session on one book/chapter."""
    return (
        f"We're doing a {minutes}-minute study session on {library}/{book_path}.\n"
        "  1. Use `list_toc` to see the chapters.\n"
        "  2. Ask me where I left off / what I want to cover today.\n"
        "  3. Pull that section with `get_page`.\n"
        "  4. Teach it actively: explain a chunk, ask me a check-question, correct, "
        "move on. Stop roughly at the time budget and summarize what I should review."
    )


def main() -> None:
    transport = os.getenv("LIBRETEXTS_MCP_TRANSPORT", "streamable-http")
    if transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport=transport)  # "streamable-http" or "sse"


if __name__ == "__main__":
    main()
