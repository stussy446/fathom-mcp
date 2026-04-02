# Fathom MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that connects AI assistants to the [Fathom](https://fathom.video/) meeting recording API. Retrieve meeting summaries, transcripts, and action items directly from your AI tools.

## Available Tools

| Tool                            | Description                                                     |
| ------------------------------- | --------------------------------------------------------------- |
| `fathom_list_meetings`          | List meetings with filters (date range, recorder, team, domain) |
| `fathom_get_meeting_summary`    | Get AI-generated summary for a specific recording               |
| `fathom_get_meeting_transcript` | Get full transcript with speaker names and timestamps           |
| `fathom_get_meeting_details`    | Get summary + action items + optional transcript in one call    |
| `fathom_list_teams`             | List all teams in the Fathom organization                       |

## Prerequisites

- Python 3.10+
- A [Fathom API key](https://fathom.video/customize#api-access-header) (requires a Fathom account)

## Setup

1. **Clone the repo:**

   ```bash
   # Note: This repo will be moved to the withflex org at a later time
   git clone https://github.com/stussy446/fathom-mcp.git
   cd fathom-mcp
   ```

2. **Create a virtual environment and install dependencies:**

   ```bash
   python -m venv .venv
   .venv/bin/pip install -e .
   ```

3. **Get your Fathom API key** from [Fathom Settings > API](https://fathom.video/customize#api-access-header).

## Adding to Claude Code

Add the following to your `~/.claude.json` file under the top-level `mcpServers` key:

```json
"mcpServers": {
  "fathom": {
    "command": "/path/to/fathom-mcp/.venv/bin/python",
    "args": ["server.py"],
    "cwd": "/path/to/fathom-mcp",
    "env": {
      "FATHOM_API_KEY": "your_api_key_here"
    }
  }
}
```

Replace `/path/to/fathom-mcp` with the actual path where you cloned the repo.

## Adding to Claude Desktop

Add the following to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
"mcpServers": {
  "fathom": {
    "command": "/path/to/fathom-mcp/.venv/bin/python",
    "args": ["/path/to/fathom-mcp/server.py"],
    "env": {
      "FATHOM_API_KEY": "your_api_key_here"
    }
  }
}
```

> **Note:** Claude Desktop does not support the `cwd` field, so use the full path to `server.py` in the `args`.

## Usage

Once configured, just ask your AI assistant naturally:

- "Show me my recent meetings"
- "Get the summary for recording 12345"
- "What were the action items from my last call?"
- "List my Fathom teams"

## API Reference

All requests go to `https://api.fathom.ai/external/v1` with `X-Api-Key` header authentication. Rate limit is 60 requests per 60 seconds.
