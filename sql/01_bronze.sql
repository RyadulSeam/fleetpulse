-- BRONZE: append-only landing tables. event_id (deterministic UUIDv5) is the idempotency key.
CREATE TABLE IF NOT EXISTS bronze.order_events (
    event_id        uuid        PRIMARY KEY,
    event_type      text        NOT NULL,
    schema_version  int         NOT NULL,
    event_time      timestamptz NOT NULL,
    produced_at     timestamptz NOT NULL,
    ingested_at     timestamptz NOT NULL DEFAULT now(),
    order_id        bigint      NOT NULL,
    payload         jsonb       NOT NULL,
    kafka_topic     text,
    kafka_partition int,
    kafka_offset    bigint
);
CREATE INDEX IF NOT EXISTS ix_order_events_order  ON bronze.order_events (order_id);
CREATE INDEX IF NOT EXISTS ix_order_events_time   ON bronze.order_events (event_time);
CREATE INDEX IF NOT EXISTS ix_order_events_type   ON bronze.order_events (event_type);

CREATE TABLE IF NOT EXISTS bronze.vehicle_telemetry (
    event_id        uuid        PRIMARY KEY,
    event_time      timestamptz NOT NULL,
    produced_at     timestamptz NOT NULL,
    ingested_at     timestamptz NOT NULL DEFAULT now(),
    vehicle_id      int         NOT NULL,
    hub_id          int,
    lat             double precision,
    lon             double precision,
    speed_kmh       double precision,
    fuel_pct        double precision,
    engine_temp_c   double precision,
    status          text,
    current_order_id bigint
);
CREATE INDEX IF NOT EXISTS ix_telemetry_vehicle_time ON bronze.vehicle_telemetry (vehicle_id, event_time DESC);

-- Messages that failed validation are kept (never dropped silently) for inspection and replay.
CREATE TABLE IF NOT EXISTS bronze.dead_letter (
    id          bigserial PRIMARY KEY,
    received_at timestamptz NOT NULL DEFAULT now(),
    topic       text,
    raw         text,
    error       text
);

-- One row per consumer batch: feeds the Pipeline Health dashboard (throughput, duplicates dropped).
CREATE TABLE IF NOT EXISTS bronze.ingest_log (
    id          bigserial PRIMARY KEY,
    batch_at    timestamptz NOT NULL DEFAULT now(),
    table_name  text NOT NULL,
    received    int  NOT NULL,
    inserted    int  NOT NULL,
    duplicates  int  NOT NULL
);
