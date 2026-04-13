"""
Fake checkout service: FastAPI + OpenTelemetry + async Kafka producer.
Injects synthetic incidents so the ingestion pipeline has realistic traffic to correlate.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ecommerce_simulator")

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC_EVENTS", "ecommerce.events")

_producer: AIOKafkaProducer | None = None


def _setup_tracing() -> None:
    resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "ecommerce-simulator")})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # Console exporter keeps local demos observable without a collector; OTLP is optional.
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _producer
    _setup_tracing()
    _producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP)
    await _producer.start()
    logger.info("Kafka producer started for topic %s", TOPIC)
    yield
    if _producer:
        await _producer.stop()
        _producer = None


app = FastAPI(title="E-Commerce Checkout Simulator", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)
checkout_counter = meter.create_counter("checkout_attempts")
error_counter = meter.create_counter("checkout_errors")


async def emit_event(payload: dict) -> None:
    if not _producer:
        return
    key = payload.get("trace_id", "").encode("utf-8")
    await _producer.send_and_wait(TOPIC, json.dumps(payload).encode("utf-8"), key=key)


@app.post("/checkout")
async def checkout(amount: float, sku: str = "SKU-1"):
    with tracer.start_as_current_span("checkout") as span:
        span.set_attribute("checkout.amount", amount)
        span.set_attribute("checkout.sku", sku)
        trace_id = format(span.get_span_context().trace_id, "032x")

        roll = random.random()
        status = "ok"
        if roll < 0.15:
            status = "payment_timeout"
            error_counter.add(1, {"reason": status})
            await asyncio.sleep(0.05)
            await emit_event(
                {
                    "trace_id": trace_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "log",
                    "level": "error",
                    "message": f"checkout status={status}",
                    "service": "checkout",
                    "sku": sku,
                    "amount": amount,
                }
            )
            await emit_event(
                {
                    "trace_id": trace_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "type": "metric",
                    "name": "checkout_latency_ms",
                    "value": 800,
                    "service": "checkout",
                }
            )
            span.set_attribute("checkout.result", status)
            raise HTTPException(status_code=504, detail="payment provider timeout")
        if roll < 0.25:
            status = "high_latency"
            await asyncio.sleep(1.2)

        checkout_counter.add(1, {"status": status})

        payload = {
            "trace_id": trace_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "log",
            "level": "error" if status != "ok" else "info",
            "message": f"checkout status={status}",
            "service": "checkout",
            "sku": sku,
            "amount": amount,
        }
        await emit_event(payload)
        await emit_event(
            {
                "trace_id": trace_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": "metric",
                "name": "checkout_latency_ms",
                "value": 1500 if status == "high_latency" else 120,
                "service": "checkout",
            }
        )
        span.set_attribute("checkout.result", status)
        return {"trace_id": trace_id, "status": status}


@app.get("/health")
async def health():
    return {"status": "ok"}
