# Engineering Troubleshooting Workbench

The Workbench is the companion application for [AI Explained](https://ai.hmohamedansari.com). Start with the [Automation to Agents learning journey](https://ai.hmohamedansari.com/learn/automation-to-agents/) to understand why each checkpoint exists, then return here to run it.

It starts as an ordinary Python incident investigator. You give it a synthetic incident, it collects known evidence, applies explicit rules, and explains the route it selected. Later lessons will add a model, context, retrieval, tools and a bounded control loop.

There is no production infrastructure here. No Kubernetes cluster, cloud account or real customer data is required.

## What you need

- Python 3.10 or newer
- A terminal
- A browser for the local Streamlit view

The deterministic foundation does **not** need a model API key.

## Set it up

Clone the repository, then create a virtual environment in the project folder.

### macOS and Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run it

The terminal view is the simplest place to start:

```bash
workbench
```

To inspect the same investigation in a local browser:

```bash
python -m streamlit run app.py
```

Streamlit opens a local URL, normally `http://localhost:8501`. Docker is intentionally not required.

## Learn by changing something small

The `checkout-regression` scenario begins with a recent deployment and an observed checkout error rate of 8.2%. In the browser view, raise **High checkout error rate** from 5% to 9%. The route moves from `possible-deployment-regression` to `normal-observation`. Set it back to 5% and the original route returns.

You are changing a known input, not guessing at a code change. This is the first lesson's point: a visible rule should have a visible consequence.

Then ask yourself:

- What evidence changed?
- Which rule changed the route?
- What remains a hypothesis rather than a fact?
- What would make this system ask a human to decide?

## Test it

```bash
pytest
```

The tests protect the rules before we add a model. That matters: later capabilities should make the Workbench more useful without making its behaviour impossible to explain.

## Optional: OpenCode as a reading companion

[OpenCode](https://opencode.ai/) is an open-source coding agent. It is optional: the Workbench needs neither OpenCode nor a model API key.

If you already use it, ask it to explain `src/workbench/investigator.py` before asking it to change anything. A useful first prompt is: “Show me where the high-error rule is evaluated and explain both possible routes.” Read the answer against the code and tests. The learning goal is not to accept a convincing answer; it is to understand what changed and why.
