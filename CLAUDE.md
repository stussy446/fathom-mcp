# Fathom MCP Server

MCP server that provides tools to interact with the Fathom AI meeting recording API. Retrieve meeting summaries, transcripts, and action items.

## Architecture

Single-file server (`server.py`) using FastMCP with async httpx for API calls. All tools are read-only against the Fathom API.

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -e .
```

The server requires a `FATHOM_API_KEY` environment variable.

## Running

```bash
FATHOM_API_KEY=your_key .venv/bin/python server.py
```

## Tools

- `fathom_list_meetings` — List meetings with optional filters (date range, recorder, team, domain)
- `fathom_get_meeting_summary` — Get AI-generated summary for a recording
- `fathom_get_meeting_transcript` — Get full transcript with speaker names and timestamps
- `fathom_get_meeting_details` — Combined summary + action items + optional transcript
- `fathom_list_teams` — List teams in the Fathom organization

## API

All requests go to `https://api.fathom.ai/external/v1` with `X-Api-Key` header authentication. Rate limit is 60 requests per 60 seconds.

## Dependencies

- `mcp[cli]` — MCP server framework
- `httpx` — Async HTTP client
- `pydantic` — Input validation
