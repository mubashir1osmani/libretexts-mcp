# libretexts-mcp

MCP server for [LibreTexts](https://libretexts.org) — open textbooks in physics,
math, chemistry, engineering, biology, statistics, and geosciences. Built for
self-study (aerospace track: phys + math + chem + eng).

## Tools

- `search(query, library="phys", limit=10)` — full-text search one library.
- `get_page(library, path_or_id)` — fetch a page as Markdown.
- `list_toc(library, path_or_id="home")` — list a bookshelf or a book's chapters.

## Resources

- `libretexts://shelf/{library}` for each of: `phys`, `math`, `chem`, `eng`,
  `bio`, `stats`, `geo`. Attach to a chat for instant catalog context.

## Install / run

```bash
cd libretexts-mcp-server
uv venv && source .venv/bin/activate
uv pip install -e .
libretexts-mcp   # stdio MCP server
```

### Claude Code config

```json
{
  "mcpServers": {
    "libretexts": {
      "command": "libretexts-mcp"
    }
  }
}
```

## Notes

Uses the MindTouch DekiAPI (`/@api/deki/...?dream.out.format=json`) exposed by
each LibreTexts subdomain. Page refs can be numeric IDs or URL paths
(e.g. `Bookshelves/Classical_Mechanics/Classical_Mechanics_(Tatum)`).
