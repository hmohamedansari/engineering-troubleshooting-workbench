"""Terminal entry point for the deterministic foundation."""

from __future__ import annotations

from workbench.investigator import investigate, load_scenario


def main() -> None:
    report = investigate(load_scenario("checkout-regression"))
    print(f"Incident: {report.incident_id}")
    print(f"State: {report.state}")
    print()
    print("Evidence")
    for finding in report.findings:
        print(f"- {finding.label}: {finding.value} ({finding.source})")
    print()
    print(f"Route: {report.route}")
    print(f"Why: {report.route_reason}")
    print(f"Next safe action: {report.next_step}")


if __name__ == "__main__":
    main()
