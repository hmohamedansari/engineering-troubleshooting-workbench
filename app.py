"""Local Streamlit view for the deterministic Workbench foundation."""

from __future__ import annotations

import streamlit as st

from workbench.advanced import metric_snapshot, run_bounded_investigation, trace_decision
from workbench.investigator import investigate, load_scenario, transition_state


st.set_page_config(page_title="Engineering Troubleshooting Workbench", page_icon="🧭", layout="wide")

st.title("Engineering Troubleshooting Workbench")
st.caption("Foundation checkpoint: deterministic investigation, local scenarios, no model required.")

scenario_name = st.selectbox(
    "Choose a synthetic incident",
    options=["checkout-regression", "normal-checkout", "delayed-metric", "duplicate-alert"],
    format_func=lambda value: value.replace("-", " ").title(),
)
scenario = load_scenario(scenario_name)

outcome_key = f"hypothesis-outcomes-{scenario_name}"
if outcome_key not in st.session_state:
    st.session_state[outcome_key] = {item["id"]: item["status"] for item in scenario["hypotheses"]}

state_key = f"incident-state-{scenario_name}"
if state_key not in st.session_state:
    st.session_state[state_key] = scenario["incident"]["state"]
transition_key = f"last-transition-{scenario_name}"
scenario["incident"]["state"] = st.session_state[state_key]

st.sidebar.header("Change the rules")
error_threshold = st.sidebar.slider(
    "High checkout error rate",
    min_value=0.01,
    max_value=0.20,
    value=float(scenario["rules"]["high_error_rate"]),
    step=0.01,
    format="%.0f%%",
    key=f"error-threshold-{scenario_name}",
)
recent_deployment_minutes = st.sidebar.slider(
    "Recent deployment window (minutes)",
    min_value=5,
    max_value=180,
    value=int(scenario["rules"]["recent_deployment_minutes"]),
    step=5,
    key=f"deployment-window-{scenario_name}",
)

scenario["rules"]["high_error_rate"] = error_threshold
scenario["rules"]["recent_deployment_minutes"] = recent_deployment_minutes
report = investigate(
    scenario,
    st.session_state[outcome_key],
    st.session_state.get(transition_key),
)

left, right = st.columns([1.1, 0.9])

with left:
    st.subheader("What the system observed")
    for finding in report.findings:
        st.markdown(f"**{finding.label}**  ")
        st.caption(f"{finding.value} · source: {finding.source}")

    st.subheader("The route")
    st.info(report.route_reason)
    st.markdown(f"**Selected route:** `{report.route}`")
    st.markdown(f"**Next safe action:** {report.next_step}")

    st.subheader("What we still need to test")
    st.caption("These are hypotheses, not observations. A route can use evidence without turning an explanation into a fact.")
    for hypothesis in report.hypotheses:
        with st.container(border=True):
            st.markdown(f"**{hypothesis.statement}**")
            if hypothesis.status == "disproved":
                st.success(f"Disproved — {hypothesis.disproof_evidence}")
            else:
                st.caption(f"Next check: {hypothesis.next_check}")
                if hypothesis.disproof_evidence and st.button("Record as disproved", key=f"disprove-{scenario_name}-{hypothesis.id}"):
                    st.session_state[outcome_key][hypothesis.id] = "disproved"
                    st.rerun()
                elif not hypothesis.disproof_evidence:
                    st.caption("No evidence has tested this explanation yet, so it stays unproven.")

with right:
    st.subheader("Investigation state")
    st.metric("Current state", report.state.replace("-", " ").title())
    st.caption("State is the durable record of where this investigation is in its lifecycle. It tells the next step what has already happened and what may happen next.")
    st.caption("A deterministic route can still say “ask a human” when the evidence does not support a safe conclusion.")
    if report.allowed_next_states:
        next_state = st.selectbox(
            "Move to a valid next state",
            options=report.allowed_next_states,
            format_func=lambda value: value.replace("-", " ").title(),
            key=f"next-state-{scenario_name}-{report.state}",
        )
        if st.button("Record state transition", key=f"transition-{scenario_name}-{report.state}"):
            previous_state = report.state
            st.session_state[state_key] = transition_state(previous_state, next_state)
            st.session_state[transition_key] = (previous_state, next_state)
            st.rerun()
    else:
        st.caption("This is a terminal state. Start a new synthetic incident to continue work.")

    st.subheader("Event timeline")
    for event in report.events:
        st.markdown(f"`{event.kind}` — {event.message}")

st.divider()
foundation_tab, advanced_tab, production_tab = st.tabs(["Foundation", "Bounded harness", "Production signals"])

with foundation_tab:
    st.subheader("What this checkpoint proves")
    st.write(
        "The Workbench can collect evidence, keep explanations separate from facts, apply visible rules, respect workflow state and explain its route. "
        "The next journey puts a model inside this shape; it does not replace the shape."
    )

with advanced_tab:
    st.subheader("One bounded proposal cycle")
    run = run_bounded_investigation(scenario)
    st.caption("The default provider is a local deterministic fixture. A configured model is optional and never receives authority.")
    st.code(run.context.rendered, language="text")
    st.write(f"**Proposal:** {run.proposal.summary}")
    st.write(f"**Policy:** `{run.policy.outcome}` — {run.policy.reason}")
    st.info(run.stop_reason)

with production_tab:
    st.subheader("Trace context and Golden Signal-shaped metrics")
    carrier, spans = trace_decision(report.incident_id)
    st.caption("The carrier uses the W3C `traceparent` header. A correlation ID may still help logs, but it is not a substitute for trace propagation.")
    st.code(str(carrier), language="text")
    st.write("**Finished spans:** " + ", ".join(spans))
    st.code(metric_snapshot(report.route, duration_seconds=0.05), language="text")
