"""STEP 04 – Real-time event simulator ("replay engine").

Turns the historical, enriched orders into a time-ordered event stream and publishes it at a controllable speed.
This is how real streaming platforms are demonstrated without a live source: the *mechanics* (events, ordering,
duplicates, late arrivals, idempotent consumers, latency monitoring) are identical to production.

Modes
  backfill  everything BEFORE the cutoff, as fast as possible  (loads history, like an initial bulk load)
  live      everything FROM the cutoff, paced by --speed        (e.g. 3600 = 1 simulated hour per real second)
Sinks
  kafka     Redpanda/Kafka topics (production-style)             requires `docker compose up -d`
  jsonl     newline-delimited JSON file in data/stream/          zero-infrastructure dry run / unit tests

Deliberate real-world imperfections (configs/settings.yaml -> stream.chaos): duplicate deliveries and late /
out-of-order events. Consumers MUST handle them; Step 05 and the DQ checks prove that they do.

Examples
  python pipeline/04_replay_stream.py --mode backfill --sink kafka
  python pipeline/04_replay_stream.py --mode live --sink kafka --speed 3600 --live-days 3
  python pipeline/04_replay_stream.py --mode live --sink jsonl --speed 0     # instant dry run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleetpulse.common import get_logger, kafka_bootstrap, load_config, path  # noqa: E402
from fleetpulse.events import build_order_events, build_telemetry, to_envelope  # noqa: E402

log = get_logger("step04")


class JsonlSink:
    def __init__(self, fp: Path):
        fp.parent.mkdir(parents=True, exist_ok=True)
        self.fh, self.fp, self.errors = open(fp, "w", encoding="utf-8"), fp, 0

    def send(self, topic, key, value):
        self.fh.write(json.dumps({"topic": topic, "key": key, "value": value}, separators=(",", ":")) + "\n")

    def close(self):
        self.fh.close()
        log.info("JSONL written: %s", self.fp)


class KafkaSink:
    def __init__(self, topics: list[str]):
        from confluent_kafka import Producer
        from confluent_kafka.admin import AdminClient, NewTopic

        bs = kafka_bootstrap()
        admin = AdminClient({"bootstrap.servers": bs})
        existing = admin.list_topics(timeout=10).topics
        new = [NewTopic(t, num_partitions=3, replication_factor=1) for t in topics if t not in existing]
        for t, f in (admin.create_topics(new) if new else {}).items():
            f.result()
            log.info("created topic %s", t)
        self.p = Producer({"bootstrap.servers": bs, "enable.idempotence": True, "linger.ms": 20, "compression.type": "lz4"})
        self.errors = 0

    def _cb(self, err, _msg):
        if err:
            self.errors += 1
            log.error("delivery failed: %s", err)

    def send(self, topic, key, value):
        while True:
            try:
                self.p.produce(topic, key=str(key), value=json.dumps(value, separators=(",", ":")), on_delivery=self._cb)
                break
            except BufferError:
                self.p.poll(0.5)
        self.p.poll(0)

    def close(self):
        self.p.flush(30)


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["backfill", "live"], required=True)
    ap.add_argument("--sink", choices=["kafka", "jsonl"], default="jsonl")
    ap.add_argument("--speed", type=float, default=3600.0, help="simulated seconds per real second; 0 = no pacing")
    ap.add_argument("--live-days", type=float, default=3.0, help="size of the live window at the end of the data")
    ap.add_argument("--no-chaos", action="store_true")
    ap.add_argument("--no-telemetry", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="stop after N events (debug)")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    proc = path("processed")
    orders = pd.read_csv(proc / "orders_enriched.csv")
    for c in ["created_at", "hub_received_at", "dispatched_at", "delivered_at", "cancelled_at", "feedback_at"]:
        orders[c] = pd.to_datetime(orders[c], utc=True, format="ISO8601")
    vehicles, hubs = pd.read_csv(proc / "dim_vehicle.csv"), pd.read_csv(proc / "dim_hub.csv")

    stream = cfg["stream"]
    ev = build_order_events(orders, stream["schema_version"], stream["source_name"])
    data_end = ev.event_time.max()
    # live window = the last N days of order *creation*, plus the delivery tail that follows them
    cutoff = (orders.created_at.max() - pd.Timedelta(days=a.live_days)).floor("D")
    log.info("events=%s | data range %s -> %s | cutoff %s", f"{len(ev):,}", ev.event_time.min(), data_end, cutoff)

    if a.mode == "backfill":
        ev = ev[ev.event_time < cutoff]
    else:
        ev = ev[ev.event_time >= cutoff]
        if not a.no_telemetry:
            tl = build_telemetry(orders, vehicles, hubs, cutoff, data_end, stream["telemetry"]["ping_minutes"],
                                 stream["telemetry"]["max_radius_km"], cfg["ml"]["seed"], stream["schema_version"], stream["source_name"])
            ev = pd.concat([ev, tl], ignore_index=True)

    # ---- chaos: duplicates + late arrivals (seeded) ----
    ev["emit_time"] = ev.event_time
    if not a.no_chaos and len(ev):
        rng = np.random.default_rng(cfg["enrichment"]["seed"])
        ch = stream["chaos"]
        late = rng.random(len(ev)) < ch["late_rate"]
        ev.loc[late, "emit_time"] += pd.to_timedelta(rng.uniform(1, ch["max_late_minutes"], late.sum()), unit="m")
        dup = ev[rng.random(len(ev)) < ch["duplicate_rate"]].copy()
        dup["emit_time"] += pd.to_timedelta(rng.uniform(0, 30, len(dup)), unit="s")
        log.info("chaos: %s late events, %s duplicate deliveries", int(late.sum()), len(dup))
        ev = pd.concat([ev, dup], ignore_index=True)
    ev = ev.sort_values(["emit_time", "key"]).reset_index(drop=True)
    if a.limit:
        ev = ev.head(a.limit)

    topics = stream["topics"]
    sink = JsonlSink(a.out or path("stream") / f"events_{a.mode}.jsonl") if a.sink == "jsonl" else KafkaSink(list(topics.values()))
    t0_real, t0_sim, sent, last_log = time.monotonic(), (ev.emit_time.iloc[0] if len(ev) else None), 0, time.monotonic()
    for row in ev.itertuples():
        if a.mode == "live" and a.speed > 0:
            due = (row.emit_time - t0_sim).total_seconds() / a.speed
            delay = due - (time.monotonic() - t0_real)
            if delay > 0:
                time.sleep(delay)
        topic = topics["orders"] if row.topic_kind == "orders" else topics["telemetry"]
        sink.send(topic, row.key, to_envelope(row, datetime.now(timezone.utc)))
        sent += 1
        if time.monotonic() - last_log > 5:
            log.info("sent %s/%s | sim clock %s", f"{sent:,}", f"{len(ev):,}", row.emit_time.strftime("%Y-%m-%d %H:%M"))
            last_log = time.monotonic()
    sink.close()
    log.info("DONE: %s events in %.1fs (errors=%s)", f"{sent:,}", time.monotonic() - t0_real, sink.errors)


if __name__ == "__main__":
    main()
