"""A real MCP server with one intentionally read-only Workbench tool."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from workbench.investigator import investigate, load_scenario


def create_server() -> MCPServer:
    server = MCPServer(
        "engineering-troubleshooting-workbench",
        description="Read-only synthetic incident evidence. No production tools are exposed.",
        instructions="Use this server only to inspect the named synthetic incident. It cannot change state.",
        version="0.2.0",
    )

    @server.tool(
        name="read_incident_evidence",
        description="Return the deterministic evidence and route for one synthetic scenario. This tool is read-only.",
        structured_output=True,
    )
    def read_incident_evidence(scenario_name: str) -> dict[str, object]:
        report = investigate(load_scenario(scenario_name))
        return {
            "incident_id": report.incident_id,
            "route": report.route,
            "findings": [
                {"label": item.label, "value": item.value, "source": item.source}
                for item in report.findings
            ],
        }

    return server
