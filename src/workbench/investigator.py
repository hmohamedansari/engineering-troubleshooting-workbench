"""Deterministic incident investigation logic.

This file deliberately contains no model call. The first course milestone is a
baseline that learners can test and explain before we add uncertain components.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workbench.domain import Event, Finding, Hypothesis, InvestigationReport


def _scenario_directory() -> Path:
    """Find the checked-in fixture directory in source and container installs.

    The learning repository keeps scenarios beside ``src`` so learners can open
    and edit them directly.  A regular package installation, however, puts this
    module under site-packages while Docker intentionally keeps the fixtures at
    ``/app/scenarios``.  Resolve the working-copy/container location first and
    retain the source-tree location for local test runs.
    """
    candidates = (
        Path.cwd() / "scenarios",
        Path(__file__).resolve().parents[2] / "scenarios",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not find the Workbench's checked-in scenarios directory.")


SCENARIOS_DIR = _scenario_directory()
SCENARIO_NAMES = {"checkout-regression", "normal-checkout", "delayed-metric", "duplicate-alert"}
ALLOWED_STATE_TRANSITIONS = {
    "new": {"triaged"},
    "triaged": {"investigating", "closed-as-noise"},
    "investigating": {"waiting-for-human", "resolved"},
    "waiting-for-human": {"investigating", "resolved"},
    "resolved": set(),
    "closed-as-noise": set(),
}


def load_scenario(name: str) -> dict[str, Any]:
    """Load a named, synthetic scenario without allowing path traversal."""
    if name not in SCENARIO_NAMES:
        raise ValueError(f"Unknown scenario: {name}")
    path = SCENARIOS_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def allowed_next_states(state: str) -> list[str]:
    """Return the only valid next states for a visible workflow state."""
    if state not in ALLOWED_STATE_TRANSITIONS:
        raise ValueError(f"Unknown incident state: {state}")
    return sorted(ALLOWED_STATE_TRANSITIONS[state])


def transition_state(current_state: str, next_state: str) -> str:
    """Move an incident only through a permitted state transition."""
    if next_state not in allowed_next_states(current_state):
        raise ValueError(f"Cannot move incident from {current_state} to {next_state}")
    return next_state


def collect_findings(scenario: dict[str, Any]) -> list[Finding]:
    """Turn the fixture into evidence that a report can show to a learner."""
    signals = scenario["signals"]
    deployment = scenario["deployment"]
    return [
        Finding("Checkout 5xx rate", f"{signals['checkout_error_rate']:.1%}", "checkout-api metric snapshot"),
        Finding("Latency", f"p95 {signals['checkout_latency_p95_ms']} ms", "checkout-api metric snapshot"),
        Finding("Payment provider error rate", f"{signals['payment_provider_error_rate']:.1%}", "payment-provider health snapshot"),
        Finding("Most recent deployment", f"{deployment['minutes_ago']} minutes ago", "deployment history"),
        Finding("Deployment version", deployment["version"], "deployment history"),
    ]


def collect_hypotheses(scenario: dict[str, Any], outcomes: dict[str, str] | None = None) -> list[Hypothesis]:
    """Keep possible explanations distinct from evidence and selected routes."""
    outcomes = outcomes or {}
    allowed_statuses = {"unproven", "disproved"}
    hypotheses: list[Hypothesis] = []

    for item in scenario["hypotheses"]:
        status = outcomes.get(item["id"], item["status"])
        if status not in allowed_statuses:
            raise ValueError(f"Unsupported hypothesis status: {status}")
        if status == "disproved" and not item["disproof_evidence"]:
            raise ValueError(f"Cannot disprove hypothesis without evidence: {item['id']}")
        hypotheses.append(
            Hypothesis(
                id=item["id"],
                statement=item["statement"],
                status=status,
                next_check=item["next_check"],
                disproof_evidence=item["disproof_evidence"],
            )
        )

    return hypotheses


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


def collect_workflow_events(scenario: dict[str, Any]) -> list[Event]:
    """Record retries and duplicate delivery as visible workflow behaviour."""
    events: list[Event] = []
    workflow = scenario.get("workflow")
    if workflow:
        attempts = workflow["metric_snapshot_attempts"]
        retry_budget = workflow["retry_budget"]
        events.append(Event("workflow.started", "Started metric snapshot workflow"))
        for index, attempt in enumerate(attempts, start=1):
            outcome = attempt["outcome"]
            events.append(Event("metric.snapshot.read", f"Attempt {index}: {outcome} — {attempt['detail']}"))
            if outcome == "timeout" and index <= retry_budget:
                events.append(Event("metric.snapshot.retry-scheduled", f"Retry {index} is within the visible budget of {retry_budget}"))
            if outcome == "success":
                events.append(Event("workflow.completed", "Metric snapshot read successfully"))

    delivery = scenario.get("delivery")
    if delivery and delivery["received_count"] > 1:
        events.append(Event("alert.duplicate-suppressed", f"Ignored {delivery['received_count'] - 1} duplicate delivery using key {delivery['idempotency_key']}"))

    return events


def investigate(
    scenario: dict[str, Any],
    hypothesis_outcomes: dict[str, str] | None = None,
    state_transition: tuple[str, str] | None = None,
) -> InvestigationReport:
    """Investigate a scenario with evidence, rules, state, and an event history."""
    incident = scenario["incident"]
    findings = collect_findings(scenario)
    hypotheses = collect_hypotheses(scenario, hypothesis_outcomes)
    route, route_reason, next_step = choose_route(scenario)

    events = [
        Event("incident.received", f"Received {incident['id']} in state {incident['state']}"),
        Event("evidence.collected", f"Collected {len(findings)} evidence items from local fixtures"),
        Event("hypotheses.recorded", f"Recorded {len(hypotheses)} explanations separately from evidence"),
        Event("route.selected", route),
    ]
    if state_transition:
        events.append(Event("incident.state-transitioned", f"Moved from {state_transition[0]} to {state_transition[1]}"))
    events.extend(collect_workflow_events(scenario))

    for hypothesis in hypotheses:
        if hypothesis.status == "disproved":
            events.append(
                Event(
                    "hypothesis.disproved",
                    f"Kept dead end: {hypothesis.statement} Evidence: {hypothesis.disproof_evidence}",
                )
            )

    return InvestigationReport(
        incident_id=incident["id"],
        state=incident["state"],
        allowed_next_states=allowed_next_states(incident["state"]),
        route=route,
        route_reason=route_reason,
        next_step=next_step,
        findings=findings,
        hypotheses=hypotheses,
        events=events,
    )
