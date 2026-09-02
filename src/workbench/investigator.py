"""Deterministic incident investigation logic.

This file deliberately contains no model call. The first course milestone is a
baseline that learners can test and explain before we add uncertain components.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workbench.domain import Event, Finding, InvestigationReport


SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "scenarios"


def load_scenario(name: str) -> dict[str, Any]:
    """Load a named, synthetic scenario without allowing path traversal."""
    if name not in {"checkout-regression", "normal-checkout"}:
        raise ValueError(f"Unknown scenario: {name}")
    path = SCENARIOS_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def collect_findings(scenario: dict[str, Any]) -> list[Finding]:
    """Turn the fixture into evidence that a report can show to a learner."""
    signals = scenario["signals"]
    deployment = scenario["deployment"]
    return [
        Finding("Checkout 5xx rate", f"{signals['checkout_error_rate']:.1%}", "checkout-api metric snapshot"),
        Finding("Latency", f"p95 {signals['checkout_latency_p95_ms']} ms", "checkout-api metric snapshot"),
        Finding("Most recent deployment", f"{deployment['minutes_ago']} minutes ago", "deployment history"),
        Finding("Deployment version", deployment["version"], "deployment history"),
    ]


def choose_route(scenario: dict[str, Any]) -> tuple[str, str, str]:
    """Apply a small rule set and return route, reason, and next safe action."""
    signals = scenario["signals"]
    deployment = scenario["deployment"]
    rules = scenario["rules"]

    high_errors = signals["checkout_error_rate"] >= rules["high_error_rate"]
    recent_deployment = deployment["minutes_ago"] <= rules["recent_deployment_minutes"]

    if high_errors and recent_deployment:
        return (
            "possible-deployment-regression",
            "Checkout errors are above the configured threshold and a deployment happened inside the configured review window.",
            "Ask an engineer to compare validation and error logs before and after the deployment.",
        )
    if high_errors:
        return (
            "checkout-service-degradation",
            "Checkout errors are above the configured threshold, but no recent deployment matches the review window.",
            "Follow the checkout degradation runbook and inspect dependency health.",
        )
    return (
        "normal-observation",
        "Checkout errors are below the configured threshold.",
        "Record the observation and continue normal monitoring.",
    )


def investigate(scenario: dict[str, Any]) -> InvestigationReport:
    """Investigate a scenario with evidence, rules, state, and an event history."""
    incident = scenario["incident"]
    findings = collect_findings(scenario)
    route, route_reason, next_step = choose_route(scenario)

    events = [
        Event("incident.received", f"Received {incident['id']} in state {incident['state']}"),
        Event("evidence.collected", f"Collected {len(findings)} evidence items from local fixtures"),
        Event("route.selected", route),
    ]

    return InvestigationReport(
        incident_id=incident["id"],
        state=incident["state"],
        route=route,
        route_reason=route_reason,
        next_step=next_step,
        findings=findings,
        events=events,
    )
