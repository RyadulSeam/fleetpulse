"""STEP 05 – Stream consumer: Kafka/Redpanda (or JSONL) -> PostgreSQL bronze.

Guarantees
  * At-least-once delivery from the broker + idempotent writes (ON CONFLICT DO NOTHING on event_id)
    => effectively-once results, even with duplicates or replays.
  * Offsets are committed ONLY after the database transaction commits (no data loss on crash).
  * Invalid messages go to bronze.dead_letter, never silently dropped and never block the stream.
  * Each batch is logged to bronze.ingest_log (feeds the Pipeline Health dashboard).

Examples
  python pipeline/05_consume_to_postgres.py --source kafka --exit-when-idle 20     # drain a backfill then stop
  python pipeline/05_consume_to_postgres.py --source kafka                          # run continuously (Ctrl-C to stop)
  python pipeline/05_consume_to_postgres.py --source jsonl --file data/stream/events_backfill.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleetpulse.common import ROOT, get_logger, kafka_bootstrap, load_config, pg_connect  # noqa: E402
from fleetpulse.ingest import InvalidEvent, apply_sql, to_order_row, to_telemetry_row, validate, write_orders, write_telemetry  # noqa: E402

log = get_logger("step05")


def messages_jsonl(fp: Path):
    with open(fp, encoding="utf-8") as fh:
        for line in fh:
            m = json.loads(line)
            yield m["topic"], None, None, line.strip() and json.dumps(m["value"])


def messages_kafka(topics: list[str], group: str, idle_exit: float):
    from confluent_kafka import Consumer

    c = Consumer({"bootstrap.servers": kafka_bootstrap(), "group.id": group, "auto.offset.reset": "earliest", "enable.auto.commit": False})
    c.subscribe(topics)
    last = time.monotonic()
    try:
        while True:
            msg = c.poll(1.0)
            if msg is None:
                if idle_exit and time.monotonic() - last > idle_exit:
                    return
                yield None, None, None, None, c      # lets the caller flush time-based batches
                continue
            if msg.error():
                log.error("kafka error: %s", msg.error())
                continue
            last = time.monotonic()
            yield msg.topic(), msg.partition(), msg.offset(), msg.value().decode("utf-8"), c
    finally:
        c.close()


def main() -> None:
    cfg = load_config()
    topics = cfg["stream"]["topics"]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["kafka", "jsonl"], default="kafka")
    ap.add_argument("--file", type=Path)
    ap.add_argument("--group", default="fleetpulse-bronze-writer")
    ap.add_argument("--batch-size", type=int, default=1000)
    ap.add_argument("--flush-seconds", type=float, default=2.0)
    ap.add_argument("--exit-when-idle", type=float, default=0.0, help="stop after N idle seconds (0 = run forever)")
    a = ap.parse_args()

    conn = pg_connect()
    apply_sql(conn, [ROOT / "sql" / "00_schemas.sql", ROOT / "sql" / "01_bronze.sql"])

    ob, tb, dead, consumer = [], [], [], None
    totals = {"recv": 0, "ins": 0, "dead": 0}
    last_flush = time.monotonic()

    def flush():
        nonlocal ob, tb, dead, last_flush
        if not (ob or tb or dead):
            return
        with conn, conn.cursor() as cur:                       # one transaction per batch
            for table, rows, fn in (("order_events", ob, write_orders), ("vehicle_telemetry", tb, write_telemetry)):
                if rows:
                    ins = fn(cur, rows)
                    cur.execute("INSERT INTO bronze.ingest_log (table_name, received, inserted, duplicates) VALUES (%s,%s,%s,%s)",
                                (table, len(rows), ins, len(rows) - ins))
                    totals["ins"] += ins
            for d in dead:
                cur.execute("INSERT INTO bronze.dead_letter (topic, raw, error) VALUES (%s,%s,%s)", d)
        if consumer is not None:
            from confluent_kafka import KafkaError, KafkaException

            try:
                consumer.commit(asynchronous=False)           # commit offsets AFTER the DB commit
            except KafkaException as exc:
                if exc.args[0].code() != KafkaError._NO_OFFSET:   # "nothing to commit" is harmless
                    raise
        totals["dead"] += len(dead)
        ob, tb, dead = [], [], []
        last_flush = time.monotonic()

    src = (messages_jsonl(a.file) if a.source == "jsonl" else messages_kafka(list(topics.values()), a.group, a.exit_when_idle))
    try:
        for item in src:
            if a.source == "kafka":
                topic, part, off, raw, consumer = item
            else:
                topic, part, off, raw = item
            if raw is not None:
                totals["recv"] += 1
                kind = "orders" if topic == topics["orders"] else "telemetry"
                try:
                    ev = validate(json.loads(raw), kind)
                    (ob if kind == "orders" else tb).append(to_order_row(ev, topic, part, off) if kind == "orders" else to_telemetry_row(ev))
                except (json.JSONDecodeError, InvalidEvent, KeyError, TypeError) as exc:
                    dead.append((topic, raw[:2000], str(exc)))
            if len(ob) + len(tb) + len(dead) >= a.batch_size or time.monotonic() - last_flush >= a.flush_seconds:
                flush()
                log.info("received=%s inserted=%s duplicates_dropped=%s dead_letter=%s",
                         f"{totals['recv']:,}", f"{totals['ins']:,}", f"{totals['recv'] - totals['ins'] - totals['dead']:,}", totals["dead"])
    except KeyboardInterrupt:
        log.info("interrupted – flushing last batch")
    finally:
        flush()
        conn.close()
    log.info("FINISHED received=%s inserted=%s duplicates_dropped=%s dead_letter=%s",
             f"{totals['recv']:,}", f"{totals['ins']:,}", f"{totals['recv'] - totals['ins'] - totals['dead']:,}", totals["dead"])


if __name__ == "__main__":
    main()
