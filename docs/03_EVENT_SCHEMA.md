# Event schema (version 1)

## Envelope (all events)
| Field | Type | Meaning |
|---|---|---|
| `event_id` | UUIDv5 string | deterministic from business key ⇒ idempotency key |
| `event_type` | string | see below |
| `schema_version` | int | consumer rejects unknown versions (→ dead-letter) |
| `event_time` | ISO-8601 UTC | when it happened in the business world |
| `produced_at` | ISO-8601 UTC | when the producer sent it (wall clock) ⇒ latency metric |
| `source` | string | `fleetpulse-replay-simulator` |
| `key` | int | `order_id` (orders topic) / `vehicle_id` (telemetry topic) — also the Kafka message key |
| `payload` | object | fields below |

## Order events (topic `fleetpulse.order_events`)
| event_type | payload |
|---|---|
| `order_created` | hub_id, destination_city, dest_lat, dest_lon, distance_km, service_level, package_weight_kg |
| `hub_received` | hub_id |
| `dispatched` | hub_id, driver_id, vehicle_id, hub_processing_time_hours |
| `delivered` | hub_id, driver_id, vehicle_id, delivery_time_hours, is_delayed (bool), delay_reason (nullable) |
| `cancelled` | hub_id, driver_id, vehicle_id, cancellation_reason |
| `feedback_received` | csat_score (int 1-5) |

## Telemetry (topic `fleetpulse.vehicle_telemetry`) — SYNTHETIC
`vehicle_ping`: vehicle_id, hub_id, lat, lon, speed_kmh, fuel_pct, engine_temp_c, status (`en_route`|`idle`), current_order_id (nullable)

## Validation rules (consumer)
Required envelope fields · supported `schema_version` · known `event_type` · integer ids and `csat_score` (a float `4.0` is rejected — regression test) · coordinates in range.

## Delivery semantics and imperfections
At-least-once from the broker, effectively-once in bronze. Deliberately injected: duplicates (0.5 %) and late/out-of-order events (1 %, up to 120 min).
Compatibility rule: adding optional payload fields = same version; removing/renaming/retyping = bump `schema_version`.
