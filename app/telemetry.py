"""OpenTelemetry tracing (layer 3 of the audit design). Vendor-neutral: spans
export to any OTLP endpoint via standard OTEL_EXPORTER_OTLP_ENDPOINT env vars,
so G42 pipes traces into their own collector with zero code change. Default
exporter is console-silent (spans still feed the audit store)."""
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from .config import VERSION

_initialized = False


def init_tracing() -> None:
    global _initialized
    if _initialized:
        return
    provider = TracerProvider(resource=Resource.create({
        "service.name": "g42-agent-chassis",
        "service.version": VERSION,
    }))
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        except ImportError:
            pass
    elif os.getenv("OTEL_CONSOLE", "false").lower() == "true":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _initialized = True


def tracer():
    init_tracing()
    return trace.get_tracer("g42-agent-chassis")
