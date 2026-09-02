"""Local Streamlit view for the deterministic Workbench foundation."""

from __future__ import annotations

import streamlit as st

from workbench.investigator import investigate, load_scenario


st.set_page_config(page_title="Engineering Troubleshooting Workbench", page_icon="🧭", layout="wide")

st.title("Engineering Troubleshooting Workbench")
st.caption("Foundation checkpoint: deterministic investigation, local scenarios, no model required.")

scenario_name = st.selectbox(
    "Choose a synthetic incident",
    options=["checkout-regression", "normal-checkout"],
    format_func=lambda value: value.replace("-", " ").title(),
)
scenario = load_scenario(scenario_name)

st.sidebar.header("Change the rules")
error_threshold = st.sidebar.slider(
    "High checkout error rate",
    min_value=0.01,
    max_value=0.20,
    value=float(scenario["rules"]["high_error_rate"]),
    step=0.01,
    format="%.0f%%",
)
recent_deployment_minutes = st.sidebar.slider(
    "Recent deployment window (minutes)",
    min_value=5,
    max_value=180,
    value=int(scenario["rules"]["recent_deployment_minutes"]),
    step=5,
)

scenario["rules"]["high_error_rate"] = error_threshold
scenario["rules"]["recent_deployment_minutes"] = recent_deployment_minutes
report = investigate(scenario)

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

with right:
    st.subheader("Investigation state")
    st.metric("Current state", report.state.replace("-", " ").title())
    st.caption("State is the durable record of where this investigation is in its lifecycle. It tells the next step what has already happened and what may happen next.")
    st.caption("A deterministic route can still say “ask a human” when the evidence does not support a safe conclusion.")

    st.subheader("Event timeline")
    for event in report.events:
        st.markdown(f"`{event.kind}` — {event.message}")

st.divider()
st.subheader("What this checkpoint proves")
st.write(
    "The Workbench can collect evidence, apply visible rules, respect workflow state and explain its route. "
    "The next journey will put a model inside this shape; it will not replace the shape."
)
