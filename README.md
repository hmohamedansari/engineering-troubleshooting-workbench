# Engineering Troubleshooting Workbench

The Workbench is the companion application for [AI Explained](https://ai.hmohamedansari.com).

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

The `checkout-regression` scenario begins with a recent deployment and a high checkout error rate. In the browser view, adjust the error-rate threshold or the deployment window and rerun the investigator.

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
