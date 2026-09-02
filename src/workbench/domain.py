"""Small, explicit data structures for the deterministic foundation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    label: str
    value: str
    source: str


@dataclass(frozen=True)
class Event:
    kind: str
    message: str


@dataclass(frozen=True)
class Hypothesis:
    """An explanation the system is tracking without treating it as a fact."""

    id: str
    statement: str
    status: str
    next_check: str
    disproof_evidence: str


@dataclass(frozen=True)
class InvestigationReport:
    incident_id: str
    state: str
    allowed_next_states: list[str]
    route: str
    route_reason: str
    next_step: str
    findings: list[Finding]
    hypotheses: list[Hypothesis]
    events: list[Event]
