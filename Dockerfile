FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV LIBRETEXTS_MCP_HOST=0.0.0.0 \
    LIBRETEXTS_MCP_PORT=8000 \
    LIBRETEXTS_MCP_TRANSPORT=streamable-http

EXPOSE 8000

CMD ["libretexts-mcp"]
