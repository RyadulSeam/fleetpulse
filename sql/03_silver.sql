-- SILVER: one row per business entity, rebuilt from events. A VIEW on purpose:
-- late / out-of-order / re-delivered events are handled by aggregation over *all* events of an order,
-- so there is no ordering assumption and no state to repair.
CREATE OR REPLACE VIEW silver.orders AS
SELECT
    order_id,
    max((payload->>'hub_id')::int)                                                   AS hub_id,
    max(payload->>'destination_city')        FILTER (WHERE event_type = 'order_created') AS destination_city,
    max((payload->>'dest_lat')::float8)      FILTER (WHERE event_type = 'order_created') AS dest_lat,
    max((payload->>'dest_lon')::float8)      FILTER (WHERE event_type = 'order_created') AS dest_lon,
    max((payload->>'distance_km')::float8)   FILTER (WHERE event_type = 'order_created') AS distance_km,
    max(payload->>'service_level')           FILTER (WHERE event_type = 'order_created') AS service_level,
    max((payload->>'package_weight_kg')::float8) FILTER (WHERE event_type = 'order_created') AS package_weight_kg,
    max((payload->>'driver_id')::int)        FILTER (WHERE event_type IN ('dispatched','delivered','cancelled')) AS driver_id,
    max((payload->>'vehicle_id')::int)       FILTER (WHERE event_type IN ('dispatched','delivered','cancelled')) AS vehicle_id,
    max((payload->>'hub_processing_time_hours')::float8) FILTER (WHERE event_type = 'dispatched') AS hub_processing_time_hours,
    max((payload->>'delivery_time_hours')::float8)       FILTER (WHERE event_type = 'delivered')  AS delivery_time_hours,
    bool_or((payload->>'is_delayed')::boolean)           FILTER (WHERE event_type = 'delivered')  AS is_delayed,
    max(payload->>'delay_reason')            FILTER (WHERE event_type = 'delivered')              AS delay_reason,
    max(payload->>'cancellation_reason')     FILTER (WHERE event_type = 'cancelled')              AS cancellation_reason,
    max((payload->>'csat_score')::int)       FILTER (WHERE event_type = 'feedback_received')      AS csat_score,
    min(event_time) FILTER (WHERE event_type = 'order_created')      AS created_at,
    min(event_time) FILTER (WHERE event_type = 'hub_received')       AS hub_received_at,
    min(event_time) FILTER (WHERE event_type = 'dispatched')         AS dispatched_at,
    min(event_time) FILTER (WHERE event_type = 'delivered')          AS delivered_at,
    min(event_time) FILTER (WHERE event_type = 'cancelled')          AS cancelled_at,
    min(event_time) FILTER (WHERE event_type = 'feedback_received')  AS feedback_at,
    CASE
        WHEN bool_or(event_type = 'cancelled')  THEN 'cancelled'
        WHEN bool_or(event_type = 'delivered')  THEN 'delivered'
        WHEN bool_or(event_type = 'dispatched') THEN 'in_transit'
        WHEN bool_or(event_type = 'hub_received') THEN 'at_hub'
        ELSE 'created'
    END AS order_status,
    count(*) AS event_count
FROM bronze.order_events
GROUP BY order_id;

CREATE OR REPLACE VIEW silver.vehicle_latest_position AS
SELECT DISTINCT ON (vehicle_id) vehicle_id, hub_id, event_time, lat, lon, speed_kmh, fuel_pct, engine_temp_c, status, current_order_id
FROM bronze.vehicle_telemetry
ORDER BY vehicle_id, event_time DESC;
