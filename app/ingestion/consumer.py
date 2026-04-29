"""
Async Kafka consumer: normalize payloads, correlate by trace_id in memory, publish correlated batches.
Buffers stay small on purpose so local demos flush quickly without tuning watermarks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingestion.consumer")

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
SRC_TOPIC = os.getenv("KAFKA_TOPIC_EVENTS", "ecommerce.events")
DST_TOPIC = os.getenv("KAFKA_TOPIC_CORRELATED", "incidents.correlated")
FLUSH_AFTER_EVENTS = int(os.getenv("CORRELATION_FLUSH_EVENTS", "2"))


def normalize(raw: dict) -> dict:
    return {
        "trace_id": raw.get("trace_id"),
        "ts": raw.get("ts") or datetime.now(timezone.utc).isoformat(),
        "type": raw.get("type", "unknown"),
        "payload": {k: v for k, v in raw.items() if k not in {"trace_id", "ts", "type"}},
    }


async def run() -> None:
    consumer = AIOKafkaConsumer(
        SRC_TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id="aiops-ingestion",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP)
    await consumer.start()
    await producer.start()
    buffers: dict[str, list[dict]] = defaultdict(list)
    lock = asyncio.Lock()

    logger.info("Consuming %s -> correlating -> %s", SRC_TOPIC, DST_TOPIC)

    try:
        async for msg in consumer:
            try:
                raw = json.loads(msg.value.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.warning("Skipping invalid message at offset %s", msg.offset)
                continue

            tid = raw.get("trace_id")
            if not tid:
                logger.debug("Skipping event without trace_id")
                continue

            event = normalize(raw)
            async with lock:
                buffers[tid].append(event)
                count = len(buffers[tid])

            if count >= FLUSH_AFTER_EVENTS:
                async with lock:
                    batch = buffers.pop(tid, [])
                if not batch:
                    continue
                correlated = {
                    "trace_id": tid,
                    "event_count": len(batch),
                    "events": batch,
                    "correlation_ts": datetime.now(timezone.utc).isoformat(),
                }
                await producer.send_and_wait(
                    DST_TOPIC,
                    json.dumps(correlated).encode("utf-8"),
                    key=tid.encode("utf-8"),
                )
                logger.info("Published correlated batch trace_id=%s events=%s", tid, len(batch))
    finally:
        await consumer.stop()
        await producer.stop()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
