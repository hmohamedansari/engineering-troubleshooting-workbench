"""A small, local A2A identity for the evidence-review boundary.

The agent card is served by the official A2A Python SDK route.  It advertises a
single skill: returning a structured review artifact.  It does not advertise
deployment, notification, or secret access.
"""

from __future__ import annotations

from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.request_handlers.response_helpers import agent_card_to_dict
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from starlette.applications import Starlette


def review_agent_card(base_url: str = "http://127.0.0.1:8011") -> AgentCard:
    return AgentCard(
        name="Workbench Evidence Reviewer",
        description="Reviews whether a proposal cites only the supplied synthetic evidence.",
        version="0.2.0",
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
                description="Returns a structured review artifact. It cannot act on another system.",
                tags=["review", "synthetic", "read-only"],
            )
        ],
    )


def create_review_app() -> Starlette:
    card = review_agent_card()
    return Starlette(routes=create_agent_card_routes(card))


def review_agent_card_document() -> dict:
    return agent_card_to_dict(review_agent_card())
