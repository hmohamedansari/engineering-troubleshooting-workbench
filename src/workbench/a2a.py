"""A bounded A2A evidence-review service using the official Python SDK."""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import httpx

from a2a.client.card_resolver import A2ACardResolver
from a2a.client.client import ClientCallContext
from a2a.client.transports.jsonrpc import JsonRpcTransport
from a2a.helpers.proto_helpers import new_data_part, new_task, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.request_handlers.response_helpers import agent_card_to_dict
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from a2a.types.a2a_pb2 import Message, Role, SendMessageConfiguration, SendMessageRequest, TaskState
from starlette.applications import Starlette

from workbench.investigator import SCENARIO_NAMES, investigate, load_scenario


def review_agent_card(base_url: str = "http://127.0.0.1:8011") -> AgentCard:
    return AgentCard(
        name="Workbench Evidence Reviewer",
        description="Reviews supplied synthetic evidence against one named Workbench scenario. It cannot act on another system.",
        version="0.3.0",
        supported_interfaces=[
            AgentInterface(url=base_url, protocol_binding="JSONRPC", protocol_version="1.0")
        ],
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id="evidence-review",
                name="Evidence review",
                description="Returns a structured synthetic-evidence review artifact. It cannot deploy, notify, or access secrets.",
                tags=["review", "synthetic", "read-only"],
                examples=['{"scenario":"checkout-regression","evidence_sources":["checkout-api metric snapshot"]}'],
            )
        ],
    )


def _review_request(text: str) -> tuple[str, list[str]]:
    """Accept only the small request shape advertised by the Agent Card."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("Request must be one JSON object.") from error
    if not isinstance(payload, dict) or set(payload) != {"scenario", "evidence_sources"}:
        raise ValueError("Request must contain only scenario and evidence_sources.")
    scenario = payload["scenario"]
    evidence_sources = payload["evidence_sources"]
    if scenario not in SCENARIO_NAMES:
        raise ValueError("Scenario is not part of this synthetic Workbench.")
    if not isinstance(evidence_sources, list) or not evidence_sources or not all(isinstance(item, str) for item in evidence_sources):
        raise ValueError("evidence_sources must be a non-empty list of source labels.")
    return scenario, evidence_sources


class EvidenceReviewExecutor(AgentExecutor):
    """Turn a bounded request into a review artifact and then stop."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if not context.task_id or not context.context_id:
            raise RuntimeError("The A2A request did not receive a task and context identifier.")
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        # The SDK consumer must receive the Task before its status updates or
        # artifact events. That makes the lifecycle inspectable by the peer.
        await event_queue.enqueue_event(new_task(context.task_id, context.context_id, TaskState.TASK_STATE_SUBMITTED))
        try:
            scenario_name, submitted_sources = _review_request(context.get_user_input())
            report = investigate(load_scenario(scenario_name))
            allowed_sources = [item.source for item in report.findings]
            unknown_sources = sorted(set(submitted_sources) - set(allowed_sources))
            if unknown_sources:
                raise ValueError(f"Evidence source is not part of {scenario_name}: {', '.join(unknown_sources)}")
        except ValueError as error:
            await updater.reject(updater.new_agent_message([new_text_part(str(error))]))
            return

        await updater.start_work(updater.new_agent_message([new_text_part("Evidence review accepted for a synthetic scenario.")]))
        artifact = {
            "artifact_type": "synthetic-evidence-review",
            "scenario": scenario_name,
            "incident_id": report.incident_id,
            "received_evidence_sources": submitted_sources,
            "available_evidence_sources": allowed_sources,
            "verdict": "accepted",
            "reason": "Every submitted source belongs to the selected synthetic scenario. This result is evidence to review, not authority to act.",
            "next_safe_action": report.next_step,
        }
        await updater.add_artifact(
            [new_data_part(artifact, media_type="application/json")],
            artifact_id="evidence-review",
            name="Synthetic evidence review",
            last_chunk=True,
        )
        await updater.complete(updater.new_agent_message([new_text_part("Evidence review completed. No external action was taken.")]))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        if not context.task_id or not context.context_id:
            raise RuntimeError("The A2A request did not receive a task and context identifier.")
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel(updater.new_agent_message([new_text_part("Evidence review cancelled before any external action.")]))


def create_review_app(base_url: str = "http://127.0.0.1:8011") -> Starlette:
    card = review_agent_card(base_url)
    handler = DefaultRequestHandler(
        agent_executor=EvidenceReviewExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    return Starlette(routes=[
        *create_agent_card_routes(card),
        *create_jsonrpc_routes(handler, rpc_url="/"),
    ])


def review_agent_card_document() -> dict:
    return agent_card_to_dict(review_agent_card())


async def request_evidence_review(base_url: str, scenario: str = "checkout-regression") -> dict:
    """Discover the peer and send one bounded request through the SDK transport."""
    async with httpx.AsyncClient() as http_client:
        card = await A2ACardResolver(http_client, base_url).get_agent_card()
        interface = card.supported_interfaces[0]
        transport = JsonRpcTransport(http_client, card, interface.url)
        request = SendMessageRequest(
            message=Message(
                message_id=str(uuid4()),
                role=Role.ROLE_USER,
                parts=[new_text_part(json.dumps({
                    "scenario": scenario,
                    "evidence_sources": ["checkout-api metric snapshot", "deployment history"],
                }))],
            ),
            configuration=SendMessageConfiguration(return_immediately=False),
        )
        response = await transport.send_message(
            request,
            context=ClientCallContext(service_parameters={"A2A-Version": "1.0"}),
        )
    if not response.HasField("task"):
        raise RuntimeError("The evidence reviewer did not return an A2A task.")
    task = response.task
    return {
        "task_id": task.id,
        "state": task.status.state,
        "artifacts": [
            {"name": artifact.name, "parts": len(artifact.parts)}
            for artifact in task.artifacts
        ],
    }


def run_evidence_review_client(base_url: str, scenario: str = "checkout-regression") -> dict:
    return asyncio.run(request_evidence_review(base_url, scenario))
