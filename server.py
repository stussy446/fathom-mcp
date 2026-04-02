#!/usr/bin/env python3
"""
Fathom MCP Server

Provides tools to interact with the Fathom AI meeting recording API.
Retrieve meeting summaries, transcripts, and action items to feed into
project management tools like Linear.
"""

import os
from typing import Optional, List

import httpx
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = "https://api.fathom.ai/external/v1"

mcp = FastMCP("fathom_mcp")

_http_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    """Return a shared httpx client, creating one if needed."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _auth_headers() -> dict:
    """Return authentication headers for Fathom API requests."""
    return {"X-Api-Key": os.environ.get("FATHOM_API_KEY", "")}


async def _api_request(
    endpoint: str,
    method: str = "GET",
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
) -> dict:
    """Make an authenticated request to the Fathom API."""
    client = await _get_client()
    response = await client.request(
        method,
        f"{API_BASE_URL}/{endpoint.lstrip('/')}",
        headers=_auth_headers(),
        params=params,
        json=json_body,
    )
    response.raise_for_status()
    return response.json()


def _handle_error(e: Exception) -> str:
    """Return a human-readable, actionable error message."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 401:
            return "Error: Unauthorized — check that your FATHOM_API_KEY is valid."
        if status == 404:
            return "Error: Recording not found. Double-check the recording_id."
        if status == 429:
            return "Error: Rate limit exceeded (60 req / 60 s). Wait a moment and retry."
        try:
            body = e.response.json()
            detail = body.get("message", body.get("detail", ""))
        except ValueError:
            detail = e.response.text[:200]
        return f"Error: Fathom API returned {status}. {detail}"
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Please try again."
    return f"Error: {type(e).__name__}: {e}"


def _format_meeting_markdown(meeting: dict, include_summary: bool = False, include_transcript: bool = False) -> str:
    """Format a single meeting object as Markdown."""
    lines: list[str] = []
    title = meeting.get("title") or meeting.get("meeting_title") or "Untitled Meeting"
    rec_id = meeting.get("recording_id", "N/A")
    lines.append(f"## {title}")
    lines.append(f"**Recording ID**: {rec_id}")
    if meeting.get("url"):
        lines.append(f"**URL**: {meeting['url']}")
    if meeting.get("share_url"):
        lines.append(f"**Share URL**: {meeting['share_url']}")
    if meeting.get("created_at"):
        lines.append(f"**Created**: {meeting['created_at']}")
    if meeting.get("recording_start_time"):
        lines.append(f"**Recording start**: {meeting['recording_start_time']}")
    if meeting.get("recording_end_time"):
        lines.append(f"**Recording end**: {meeting['recording_end_time']}")

    recorded_by = meeting.get("recorded_by")
    if recorded_by:
        name = recorded_by.get("display_name") or recorded_by.get("email", "Unknown")
        lines.append(f"**Recorded by**: {name}")

    invitees = meeting.get("calendar_invitees") or []
    if invitees:
        names = [inv.get("display_name") or inv.get("email", "?") for inv in invitees]
        lines.append(f"**Invitees**: {', '.join(names)}")

    # Action items
    action_items = meeting.get("action_items") or []
    if action_items:
        lines.append("")
        lines.append("### Action Items")
        for item in action_items:
            text = item if isinstance(item, str) else item.get("text", str(item))
            lines.append(f"- {text}")

    # Summary
    summary = meeting.get("default_summary")
    if include_summary and summary:
        lines.append("")
        lines.append("### Summary")
        md = summary.get("markdown_formatted") or summary.get("text", "")
        if md:
            lines.append(md)

    # Transcript
    transcript = meeting.get("transcript")
    if include_transcript and transcript:
        lines.append("")
        lines.append("### Transcript")
        for entry in transcript:
            speaker = entry.get("speaker", {})
            name = speaker.get("display_name", "Unknown")
            ts = entry.get("timestamp", "")
            text = entry.get("text", "")
            lines.append(f"**[{ts}] {name}**: {text}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class ListMeetingsInput(BaseModel):
    """Input for listing Fathom meetings."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    created_after: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp — only return meetings created after this time (e.g. '2025-01-01T00:00:00Z').",
    )
    created_before: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp — only return meetings created before this time.",
    )
    recorded_by: Optional[List[str]] = Field(
        default=None,
        description="Filter by recorder email addresses (e.g. ['alice@acme.com']).",
    )
    teams: Optional[List[str]] = Field(
        default=None,
        description="Filter by team names (e.g. ['Sales', 'CS']).",
    )
    domains: Optional[List[str]] = Field(
        default=None,
        description="Filter by calendar-invitee company domains (e.g. ['acme.com']).",
    )
    domains_type: Optional[str] = Field(
        default=None,
        description="Domain filter type: 'all', 'only_internal', or 'one_or_more_external'.",
    )
    include_summary: bool = Field(
        default=False,
        description="Include the default summary for each meeting.",
    )
    include_transcript: bool = Field(
        default=False,
        description="Include the full transcript for each meeting.",
    )
    include_action_items: bool = Field(
        default=False,
        description="Include action items for each meeting.",
    )
    cursor: Optional[str] = Field(
        default=None,
        description="Pagination cursor from a previous response.",
    )


class GetRecordingInput(BaseModel):
    """Input for fetching a specific recording's summary or transcript."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recording_id: int = Field(..., description="The numeric recording ID from Fathom (returned in meeting listings).")


class GetMeetingDetailsInput(BaseModel):
    """Input for the combined meeting-details workflow tool."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recording_id: int = Field(..., description="The numeric recording ID from Fathom.")
    include_transcript: bool = Field(
        default=True,
        description="Whether to include the full transcript.",
    )


class PaginationInput(BaseModel):
    """Input for paginated list endpoints."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    cursor: Optional[str] = Field(default=None, description="Pagination cursor from a previous response.")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="fathom_list_meetings",
    annotations={
        "title": "List Fathom Meetings",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fathom_list_meetings(params: ListMeetingsInput) -> str:
    """List meetings recorded in Fathom, with optional filters.

    Use this tool to browse recent customer calls, search by date range,
    recorder email, team, or invitee domain. Returns meeting metadata and
    optionally summaries, transcripts, and action items.

    Args:
        params (ListMeetingsInput): Validated filter parameters.

    Returns:
        str: Markdown-formatted list of meetings with metadata.
    """
    try:
        query: dict = {}
        if params.created_after:
            query["created_after"] = params.created_after
        if params.created_before:
            query["created_before"] = params.created_before
        if params.recorded_by:
            query["recorded_by[]"] = params.recorded_by
        if params.teams:
            query["teams[]"] = params.teams
        if params.domains:
            query["calendar_invitees_domains[]"] = params.domains
        if params.domains_type:
            query["calendar_invitees_domains_type"] = params.domains_type
        if params.include_summary:
            query["include_summary"] = "true"
        if params.include_transcript:
            query["include_transcript"] = "true"
        if params.include_action_items:
            query["include_action_items"] = "true"
        if params.cursor:
            query["cursor"] = params.cursor

        data = await _api_request("meetings", params=query)
        items = data.get("items", [])

        if not items:
            return "No meetings found matching the given filters."

        lines = [f"# Fathom Meetings ({len(items)} results)\n"]
        for m in items:
            lines.append(_format_meeting_markdown(m, include_summary=params.include_summary, include_transcript=params.include_transcript))
            lines.append("")

        next_cursor = data.get("next_cursor")
        if next_cursor:
            lines.append(f"---\n**More results available.** Use cursor: `{next_cursor}`")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="fathom_get_meeting_summary",
    annotations={
        "title": "Get Meeting Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fathom_get_meeting_summary(params: GetRecordingInput) -> str:
    """Retrieve the AI-generated summary for a specific Fathom recording.

    Use this to get a concise summary of a customer call that can be
    added as a note to a Linear project or issue.

    Args:
        params (GetRecordingInput): Contains the recording_id.

    Returns:
        str: Markdown-formatted meeting summary.
    """
    try:
        data = await _api_request(f"recordings/{params.recording_id}/summary")
        summary = data.get("summary", {})
        md = summary.get("markdown_formatted") or summary.get("text", "")
        template = summary.get("template_name", "")

        if not md:
            return f"No summary available for recording {params.recording_id}."

        lines = [f"# Meeting Summary (Recording {params.recording_id})"]
        if template:
            lines.append(f"**Template**: {template}")
        lines.append("")
        lines.append(md)
        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="fathom_get_meeting_transcript",
    annotations={
        "title": "Get Meeting Transcript",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fathom_get_meeting_transcript(params: GetRecordingInput) -> str:
    """Retrieve the full transcript for a specific Fathom recording.

    Use this when you need the complete conversation text, e.g. to
    extract specific details or quotes for Linear notes.

    Args:
        params (GetRecordingInput): Contains the recording_id.

    Returns:
        str: Markdown-formatted transcript with speaker names and timestamps.
    """
    try:
        data = await _api_request(f"recordings/{params.recording_id}/transcript")
        transcript = data.get("transcript", [])

        if not transcript:
            return f"No transcript available for recording {params.recording_id}."

        lines = [f"# Meeting Transcript (Recording {params.recording_id})\n"]
        for entry in transcript:
            speaker = entry.get("speaker", {})
            name = speaker.get("display_name", "Unknown")
            email = speaker.get("matched_calendar_invitee_email")
            ts = entry.get("timestamp", "")
            text = entry.get("text", "")
            speaker_label = f"{name} ({email})" if email else name
            lines.append(f"**[{ts}] {speaker_label}**: {text}")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="fathom_get_meeting_details",
    annotations={
        "title": "Get Full Meeting Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fathom_get_meeting_details(params: GetMeetingDetailsInput) -> str:
    """Get comprehensive meeting details: summary, action items, and optionally transcript.

    This is the primary workflow tool for preparing Linear project notes after
    a customer call. It combines the summary and transcript into a single
    structured output ready to paste into a project update.

    Args:
        params (GetMeetingDetailsInput): Contains recording_id and transcript flag.

    Returns:
        str: Markdown document with summary, action items, and optional transcript.
    """
    try:
        # Fetch summary and transcript directly by recording ID
        summary_data = await _api_request(f"recordings/{params.recording_id}/summary")
        meeting = {
            "recording_id": params.recording_id,
            "default_summary": summary_data.get("summary"),
        }
        if params.include_transcript:
            transcript_data = await _api_request(f"recordings/{params.recording_id}/transcript")
            meeting["transcript"] = transcript_data.get("transcript")

        lines = [f"# Meeting Details (Recording {params.recording_id})\n"]

        # Summary section
        summary = meeting.get("default_summary")
        if summary:
            md = summary.get("markdown_formatted") or summary.get("text", "")
            if md:
                lines.append("## Summary\n")
                lines.append(md)
                lines.append("")

        # Action items
        action_items = meeting.get("action_items") or []
        if action_items:
            lines.append("## Action Items\n")
            for item in action_items:
                text = item if isinstance(item, str) else item.get("text", str(item))
                lines.append(f"- {text}")
            lines.append("")

        # Transcript
        if params.include_transcript:
            transcript = meeting.get("transcript") or []
            if transcript:
                lines.append("## Transcript\n")
                for entry in transcript:
                    speaker = entry.get("speaker", {})
                    name = speaker.get("display_name", "Unknown")
                    ts = entry.get("timestamp", "")
                    text = entry.get("text", "")
                    lines.append(f"**[{ts}] {name}**: {text}")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="fathom_list_teams",
    annotations={
        "title": "List Fathom Teams",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fathom_list_teams(params: PaginationInput) -> str:
    """List all teams in your Fathom organization.

    Useful for discovering team names to use as filters when listing meetings.

    Args:
        params (PaginationInput): Optional pagination cursor.

    Returns:
        str: Markdown-formatted list of teams.
    """
    try:
        query: dict = {}
        if params.cursor:
            query["cursor"] = params.cursor

        data = await _api_request("teams", params=query)
        items = data.get("items", [])

        if not items:
            return "No teams found."

        lines = ["# Fathom Teams\n"]
        for team in items:
            name = team.get("name", "Unnamed")
            created = team.get("created_at", "")
            lines.append(f"- **{name}** (created {created})")

        next_cursor = data.get("next_cursor")
        if next_cursor:
            lines.append(f"\n---\n**More results available.** Use cursor: `{next_cursor}`")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
