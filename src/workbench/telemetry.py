"""Small, inspectable telemetry plumbing for the local production checkpoint."""

from __future__ import annotations

import os
import threading

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import Counter, Gauge, Histogram, generate_latest, start_http_server


INVESTIGATIONS = Counter(
    "workbench_investigations_total",
    "Synthetic investigations completed by the Workbench.",
    ["route", "outcome"],
)
INVESTIGATION_DURATION = Histogram(
    "workbench_investigation_duration_seconds",
    "Duration of a synthetic investigation.",
    ["route"],
)
ACTIVE_INVESTIGATIONS = Gauge(
    "workbench_active_investigations",
    "Synthetic investigations currently represented in the local Workbench.",
)

_metrics_lock = threading.Lock()
_metrics_server_started = False


def start_metrics_server(port: int = 9100) -> None:
    """Expose Prometheus metrics once per Workbench process."""
    global _metrics_server_started
    with _metrics_lock:
        if _metrics_server_started:
            return
        start_http_server(port)
        _metrics_server_started = True


def record_investigation(route: str, duration_seconds: float, outcome: str = "deterministic", active: int = 1) -> None:
    """Record bounded-cardinality Golden Signal-shaped metrics."""
    INVESTIGATIONS.labels(route=route, outcome=outcome).inc()
    INVESTIGATION_DURATION.labels(route=route).observe(duration_seconds)
    ACTIVE_INVESTIGATIONS.set(active)


def metric_snapshot(route: str, duration_seconds: float, active_investigations: int = 1) -> str:
    """Record one local observation and return the same data Prometheus can scrape."""
    record_investigation(route, duration_seconds, active=active_investigations)
    return generate_latest().decode("utf-8")


def trace_decision(incident_id: str) -> tuple[dict[str, str], list[str]]:
    """Create W3C trace context and optionally export spans through OTLP/HTTP."""
    memory_exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    if endpoint:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))

    tracer = provider.get_tracer("engineering-troubleshooting-workbench")
    carrier: dict[str, str] = {}
    with tracer.start_as_current_span("workbench.investigation") as root:
        root.set_attribute("workbench.incident_id", incident_id)
        with tracer.start_as_current_span("workbench.context-selection"):
            pass
        TraceContextTextMapPropagator().inject(carrier)
        remote_context = TraceContextTextMapPropagator().extract(carrier)
        with tracer.start_as_current_span("workbench.policy", context=remote_context):
            pass
    provider.force_flush()
    provider.shutdown()
    return carrier, [span.name for span in memory_exporter.get_finished_spans()]
