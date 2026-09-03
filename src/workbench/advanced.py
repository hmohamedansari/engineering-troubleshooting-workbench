"""Bounded, local extensions to the deterministic Workbench.

The model never receives authority here.  It may turn already-selected evidence
into a proposal.  Ordinary code owns context selection, policy, state, tools,
and the stop condition.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from workbench.domain import InvestigationReport
from workbench.investigator import investigate
from workbench.telemetry import metric_snapshot, trace_decision


@dataclass(frozen=True)
class ContextItem:
    source: str
    content: str
    reason: str


@dataclass(frozen=True)
class ContextPacket:
    task: str
    items: list[ContextItem]
    character_budget: int
    excluded_sources: list[str]

    @property
    def rendered(self) -> str:
        evidence = "\n".join(f"- [{item.source}] {item.content}" for item in self.items)
        return f"Task: {self.task}\nEvidence:\n{evidence}"


@dataclass(frozen=True)
class ModelProposal:
    summary: str
    next_question: str
    cited_sources: list[str]
    provider: str


@dataclass(frozen=True)
class ToolProposal:
    name: str
    arguments: dict[str, str]
    reason: str


@dataclass(frozen=True)
class PolicyDecision:
    outcome: str
    reason: str
    requires_human_approval: bool


@dataclass(frozen=True)
class BoundedRun:
    context: ContextPacket
    proposal: ModelProposal
    tool_proposal: ToolProposal
    policy: PolicyDecision
    stop_reason: str


class ProposalProvider(Protocol):
    """A small seam: providers return proposals, never executable authority."""

    name: str

    def propose(self, context: ContextPacket) -> ModelProposal: ...


class FixtureProposalProvider:
    """The default provider: deterministic, local, keyless and testable."""

    name = "local-fixture"

    def propose(self, context: ContextPacket) -> ModelProposal:
        sources = [item.source for item in context.items]
        return ModelProposal(
            summary="Checkout errors are elevated after a recent deployment; validate the deployment path before assigning cause.",
            next_question="Which validation or error-log change differs before and after the deployment?",
            cited_sources=sources,
            provider=self.name,
        )


class GroqProposalProvider:
    """An opt-in proposal writer using Groq's OpenAI-compatible API."""

    name = "groq"

    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    default_model = "openai/gpt-oss-20b"

    def __init__(self, api_key: str | None = None, model: str | None = None, opener=urllib.request.urlopen) -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL") or self.default_model
        self._opener = opener

    def propose(self, context: ContextPacket) -> ModelProposal:
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is not configured; use the local fixture provider instead.")

        schema = {
            "name": "workbench_proposal",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "next_question": {"type": "string"},
                    "cited_sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["summary", "next_question", "cited_sources"],
                "additionalProperties": False,
            },
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Write one grounded incident-summary proposal. Use only the evidence source labels supplied. Do not propose actions.",
                },
                {"role": "user", "content": context.rendered},
            ],
            "response_format": {"type": "json_schema", "json_schema": schema},
            "temperature": 0,
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener(request, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as error:
            raise RuntimeError("Groq could not produce a proposal; no decision or tool action was taken.") from error

        try:
            content = body["choices"][0]["message"]["content"]
            proposal = json.loads(content)
            if (
                not isinstance(proposal, dict)
                or not isinstance(proposal.get("summary"), str)
                or not isinstance(proposal.get("next_question"), str)
                or not isinstance(proposal.get("cited_sources"), list)
                or not all(isinstance(source, str) for source in proposal["cited_sources"])
            ):
                raise ValueError("The response did not match the proposal schema.")
            return ModelProposal(
                summary=proposal["summary"],
                next_question=proposal["next_question"],
                cited_sources=list(proposal["cited_sources"]),
                provider=self.name,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Groq returned an unusable proposal; no decision or tool action was taken.") from error


def build_context(report: InvestigationReport, character_budget: int = 900) -> ContextPacket:
    """Select evidence deliberately and record what did not enter the model input."""
    candidates = [
        ContextItem(item.source, f"{item.label}: {item.value}", "supports the next investigation question")
        for item in report.findings
    ]
    selected: list[ContextItem] = []
    used = len("Investigate a synthetic checkout incident without changing production state.")
    excluded: list[str] = []
    for item in candidates:
        size = len(item.content) + len(item.source) + 8
        if used + size <= character_budget:
            selected.append(item)
            used += size
        else:
            excluded.append(item.source)
    return ContextPacket(
        task="Investigate a synthetic checkout incident without changing production state.",
        items=selected,
        character_budget=character_budget,
        excluded_sources=excluded,
    )


def validate_proposal(proposal: ModelProposal, context: ContextPacket) -> PolicyDecision:
    allowed = {item.source for item in context.items}
    if not proposal.summary.strip() or not proposal.next_question.strip():
        return PolicyDecision("deny", "A proposal needs a summary and a next question.", False)
    if not set(proposal.cited_sources).issubset(allowed):
        return PolicyDecision("deny", "The proposal cites evidence that was not in the approved context.", False)
    return PolicyDecision("allow", "The proposal is grounded in the approved local context.", False)


def evaluate_tool_proposal(proposal: ToolProposal) -> PolicyDecision:
    """Keep real effects out of the default path; humans own consequential action."""
    if proposal.name == "read_incident_evidence":
        return PolicyDecision("allow", "The read-only evidence tool is within this checkpoint's boundary.", False)
    if proposal.name in {"open_ticket", "change_deployment", "notify_on_call"}:
        return PolicyDecision("needs-human", "This action can affect people or systems and needs explicit human approval.", True)
    return PolicyDecision("deny", "This tool is not in the Workbench allow-list.", False)


def run_bounded_investigation(
    scenario: dict,
    provider: ProposalProvider | None = None,
    character_budget: int = 900,
) -> BoundedRun:
    """Run exactly one proposal cycle, validate it, then stop at a safe boundary."""
    report = investigate(scenario)
    context = build_context(report, character_budget=character_budget)
    proposal = (provider or FixtureProposalProvider()).propose(context)
    validation = validate_proposal(proposal, context)
    tool_proposal = ToolProposal(
        name="open_ticket",
        arguments={"incident_id": report.incident_id},
        reason="A human may choose to create follow-up work after reviewing the evidence.",
    )
    policy = evaluate_tool_proposal(tool_proposal) if validation.outcome == "allow" else validation
    return BoundedRun(
        context=context,
        proposal=proposal,
        tool_proposal=tool_proposal,
        policy=policy,
        stop_reason="One proposal cycle completed. The proposed external action awaits a human; no loop continues.",
    )


class InvestigationStore:
    """Durable state is explicit SQLite data, not hidden conversation memory."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS runs (incident_id TEXT PRIMARY KEY, state TEXT NOT NULL, payload TEXT NOT NULL)"
        )

    def save(self, report: InvestigationReport) -> None:
        payload = json.dumps(asdict(report), sort_keys=True)
        self.connection.execute(
            "INSERT OR REPLACE INTO runs (incident_id, state, payload) VALUES (?, ?, ?)",
            (report.incident_id, report.state, payload),
        )
        self.connection.commit()

    def load(self, incident_id: str) -> dict | None:
        row = self.connection.execute("SELECT payload FROM runs WHERE incident_id = ?", (incident_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def close(self) -> None:
        self.connection.close()


def default_state_path() -> Path:
    """Return the explicit writable location for synthetic durable state."""
    directory = Path(os.getenv("WORKBENCH_STATE_DIR", ".workbench-data"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "workbench.sqlite3"


def persist_report(report: InvestigationReport) -> Path:
    """Persist one synthetic report so durable state is visible and inspectable."""
    path = default_state_path()
    store = InvestigationStore(path)
    try:
        store.save(report)
    finally:
        store.close()
    return path


def redact_for_telemetry(value: str) -> str:
    """Remove common secret-like values before a value reaches telemetry."""
    value = re.sub(r"(?i)(api[_-]?key|token|password)\s*[=:]\s*\S+", r"\1=[REDACTED]", value)
    return re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "[REDACTED_EMAIL]", value)


def reject_untrusted_instruction(value: str) -> PolicyDecision:
    signals = ("ignore previous", "system prompt", "exfiltrate", "disable policy")
    if any(signal in value.lower() for signal in signals):
        return PolicyDecision("deny", "Untrusted input cannot change tool policy or instructions.", False)
    return PolicyDecision("allow", "Treat the content as data, not an instruction.", False)
