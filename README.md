# Engineering Troubleshooting Workbench

The Workbench is the companion application for [AI Explained](https://ai.hmohamedansari.com). Start with the [Automation to Agents learning journey](https://ai.hmohamedansari.com/learn/automation-to-agents/) to understand why each checkpoint exists, then return here to run it.

It starts as an ordinary Python incident investigator. You give it a synthetic incident, it collects known evidence, applies explicit rules, and explains the route it selected. The later checkpoints add a bounded local proposal cycle, durable SQLite state, a read-only MCP tool, an A2A Agent Card, OpenTelemetry trace context and Prometheus-format metrics.

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
python3 -m pip install --upgrade pip
python3 -m pip install -e ".[dev]"
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
python3 -m streamlit run app.py
```

Streamlit opens a local URL, normally `http://localhost:8501`. Docker is intentionally not required.

## Learn by changing something small

The `checkout-regression` scenario begins with a recent deployment and an observed checkout error rate of 8.2%. In the browser view, raise **High checkout error rate** from 5% to 9%. The route moves from `possible-deployment-regression` to `normal-observation`. Set it back to 5% and the original route returns.

You are changing a known input, not guessing at a code change. This is the first lesson's point: a visible rule should have a visible consequence.

## Explore the foundation scenarios

The browser view has four deliberately small scenarios. Each one corresponds to a course checkpoint:

- **Checkout regression** — separate evidence from hypotheses, then change a visible threshold and inspect the route.
- **Normal checkout** — see a calm observation recorded without inventing an incident.
- **Delayed metric** — inspect a timeout, one bounded retry, and the successful metric read that becomes evidence.
- **Duplicate alert** — see a second delivery suppressed with an idempotency key instead of starting duplicate work.

The Workbench also exposes only valid next workflow states. A state transition and a disproved hypothesis appear in the event timeline; neither is silently rewritten.

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

## Run the bounded checkpoints

The normal `workbench` command remains the deterministic foundation. The later commands are local and safe by default:

```bash
workbench advanced
workbench production
workbench mcp
workbench a2a
```

- `advanced` uses a deterministic fixture provider by default, shows the selected context, validates the proposal, then stops at human approval. A Groq key is optional and never required for the course.
- `production` prints a W3C `traceparent` carrier, finished OpenTelemetry spans and Prometheus-format request, duration and active-work metrics. A correlation ID can help logs, but it is not a substitute for trace propagation.
- `mcp` lists the one official SDK-registered evidence tool. It is read-only and points only at synthetic scenarios.
- `a2a` prints the official SDK Agent Card for the evidence-review boundary. Run `workbench a2a-server` to serve it locally at `http://127.0.0.1:8011/.well-known/agent-card.json`.

The browser view has matching Foundation, Bounded harness and Production signals tabs.

## Optional: container-shaped learning route

Docker is not required for the learner path. When it is installed, the pinned local observability stack can be checked and started with:

```bash
docker compose config --quiet
docker compose up --build
```

It exposes the Workbench on port 8501, an OpenTelemetry Collector on 4318, Prometheus on 9090 and Grafana on 3000. The hardened `k8s/workbench.yaml` uses the local image name deliberately; it is a learning manifest, not a claim that this repository is ready for a real cluster.

## Optional: OpenCode as a reading companion

[OpenCode](https://opencode.ai/) is an open-source coding agent. It is optional: the Workbench needs neither OpenCode nor a model API key.

If you already use it, ask it to explain `src/workbench/investigator.py` before asking it to change anything. A useful first prompt is: “Show me where the high-error rule is evaluated and explain both possible routes.” Read the answer against the code and tests. The learning goal is not to accept a convincing answer; it is to understand what changed and why.
