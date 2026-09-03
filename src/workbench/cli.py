"""Terminal entry point for deterministic and bounded Workbench checkpoints."""

from __future__ import annotations

import argparse
import json

from workbench.advanced import FixtureProposalProvider, GroqProposalProvider, persist_report, run_bounded_investigation
from workbench.investigator import investigate, load_scenario
from workbench.mcp_server import create_server
from workbench.a2a import review_agent_card_document, run_evidence_review_client
from workbench.telemetry import metric_snapshot, trace_decision


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local Engineering Troubleshooting Workbench checkpoint.")
    parser.add_argument("checkpoint", nargs="?", choices=["foundation", "advanced", "production", "mcp", "a2a", "a2a-server", "a2a-review"], default="foundation")
    parser.add_argument("--scenario", default="checkout-regression")
    parser.add_argument("--provider", choices=["fixture", "groq"], default="fixture", help="Proposal writer for the bounded advanced checkpoint. The default is local and deterministic.")
    parser.add_argument("--a2a-url", default="http://127.0.0.1:8011", help="Local A2A evidence-review server URL.")
    args = parser.parse_args()

    if args.checkpoint == "advanced":
        provider = FixtureProposalProvider() if args.provider == "fixture" else GroqProposalProvider()
        try:
            run = run_bounded_investigation(load_scenario(args.scenario), provider=provider)
        except RuntimeError as error:
            parser.exit(2, f"Workbench stopped safely: {error}\n")
        print(f"Provider: {run.proposal.provider}")
        print(f"Context budget: {run.context.character_budget} characters")
        print(f"Proposal: {run.proposal.summary}")
        print(f"Policy: {run.policy.outcome} — {run.policy.reason}")
        print(f"Stop: {run.stop_reason}")
        return
    if args.checkpoint == "production":
        report = investigate(load_scenario(args.scenario))
        carrier, spans = trace_decision(report.incident_id)
        print("W3C trace carrier:")
        print(carrier)
        print("Finished spans:")
        for span in spans:
            print(f"- {span}")
        print(metric_snapshot(report.route, duration_seconds=0.05))
        return
    if args.checkpoint == "mcp":
        server = create_server()
        print("Registered read-only MCP tools:")
        for tool in server._tool_manager.list_tools():  # SDK registry inspection for this local learning command.
            print(f"- {tool.name}: {tool.description}")
        return
    if args.checkpoint == "a2a":
        print(json.dumps(review_agent_card_document(), indent=2, sort_keys=True))
        return
    if args.checkpoint == "a2a-server":
        import uvicorn
        from workbench.a2a import create_review_app

        uvicorn.run(create_review_app(), host="127.0.0.1", port=8011)
        return
    if args.checkpoint == "a2a-review":
        print(json.dumps(run_evidence_review_client(args.a2a_url, args.scenario), indent=2, sort_keys=True))
        return

    report = investigate(load_scenario(args.scenario))
    persist_report(report)
    print(f"Incident: {report.incident_id}")
    print(f"State: {report.state}")
    print()
    print("Evidence")
    for finding in report.findings:
        print(f"- {finding.label}: {finding.value} ({finding.source})")
    print()
    print("Hypotheses")
    for hypothesis in report.hypotheses:
        print(f"- [{hypothesis.status}] {hypothesis.statement}")
        print(f"  Next check: {hypothesis.next_check}")
    print()
    print(f"Route: {report.route}")
    print(f"Why: {report.route_reason}")
    print(f"Next safe action: {report.next_step}")


if __name__ == "__main__":
    main()
