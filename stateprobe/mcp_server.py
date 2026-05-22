from __future__ import annotations

from typing import Any

from stateprobe.skill import analyze_attention, preview_attention


TOOL_DESCRIPTION = """
Analyze whether an agent response is aligned with the user's stated requirements.

Use this when a user has explicit requirements, priorities, or do-not constraints,
and you need to make the agent's task-level attention visible. The tool returns a
StateProbe Attention HUD with user intent map, agent attention map, attention
gaps, output trajectory, control levers, and interrupt level.

This is text-to-text task attention only. It does not inspect model internals,
hidden states, logits, or neural attention.
""".strip()

PREVIEW_TOOL_DESCRIPTION = """
Preview where an agent is about to focus before it writes the answer.

Use this before a substantial response when the user has explicit requirements,
priorities, or do-not constraints. The tool compares the user's context with the
agent's planned focus and returns an Opening Attention Preview: user intent map,
planned attention map, missing-before-start gaps, risk level, should_continue,
opening patch, and control levers.

For creative generation prompts, it also returns a boundary contract:
must_show, can_imply, must_not_show, literalization_risks, and boundary_questions.
Use boundary_questions to ask the user whether ambiguous elements should be
directly shown, implied, or blurred before generating images/videos.

It also returns context_contamination_risks when planned_focus appears to be
following older context instead of the user's latest pivot.

This is for timely loss prevention at the top of the output. It is task-level
text-to-text attention only, not neural attention.
""".strip()


def overlay_attention(
    context: str,
    output: str,
) -> dict[str, Any]:
    """Return a JSON-serializable Attention HUD for an agent response."""
    if not isinstance(context, str) or not context.strip():
        raise ValueError("context must be a non-empty string")
    if not isinstance(output, str) or not output.strip():
        raise ValueError("output must be a non-empty string")

    hud = analyze_attention(context.strip(), output.strip())
    return hud.to_dict()


def preview_attention_tool(
    context: str,
    planned_focus: str,
) -> dict[str, Any]:
    """Return a JSON-serializable Opening Attention Preview."""
    if not isinstance(context, str) or not context.strip():
        raise ValueError("context must be a non-empty string")
    if not isinstance(planned_focus, str) or not planned_focus.strip():
        raise ValueError("planned_focus must be a non-empty string")

    preview = preview_attention(context.strip(), planned_focus.strip())
    return preview.to_dict()


def create_mcp_server():
    """Create the FastMCP server.

    The import is intentionally lazy so normal StateProbe installs and unit tests
    do not require the optional `mcp` dependency.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "StateProbe MCP server requires the optional MCP dependency. "
            "Install with: pip install -e \".[mcp]\""
        ) from exc

    mcp = FastMCP("StateProbe Attention HUD")

    @mcp.tool(description=TOOL_DESCRIPTION)
    def stateprobe_overlay_attention(
        context: str,
        output: str,
    ) -> dict[str, Any]:
        """Analyze agent response alignment against user requirements."""
        return overlay_attention(context=context, output=output)

    @mcp.tool(description=PREVIEW_TOOL_DESCRIPTION)
    def stateprobe_preview_attention(
        context: str,
        planned_focus: str,
    ) -> dict[str, Any]:
        """Preview planned attention before writing the answer."""
        return preview_attention_tool(
            context=context,
            planned_focus=planned_focus,
        )

    return mcp


def main() -> None:
    """Run the StateProbe MCP server over stdio."""
    create_mcp_server().run()


if __name__ == "__main__":
    main()
