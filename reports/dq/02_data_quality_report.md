# Step 02 – Data quality report

Orders analysed: **27,979** · Rules evaluated: **24**

| ID | Severity | Rule | Affected | % | Decision |
|---|---|---|---:|---:|---|
| R01-orders | error | Primary key `order_id` unique | 0 | 0.0 | none needed |
| R01-drivers | error | Primary key `driver_id` unique | 0 | 0.0 | none needed |
| R01-vehicles | error | Primary key `vehicle_id` unique | 0 | 0.0 | none needed |
| R01-hubs | error | Primary key `hub_id` unique | 0 | 0.0 | none needed |
| R02-hub | error | Orders.hub_name resolves to Hubs | 0 | 0.0 | replaced hub_name with hub_id |
| R02-vehicle | error | Orders.vehicle_code resolves to Vehicles | 0 | 0.0 | replaced vehicle_code with vehicle_id |
| R02-driver | error | Orders.driver_id exists in Drivers | 0 | 0.0 | kept driver_id as FK |
| R03 | error | Orders.Driver Name disagrees with Drivers master for the same Driver ID | 27,979 | 100.0 | Drivers master is authoritative; Orders.driver_name dropped (denormalised copy was unreliable) |
| R04 | warn | Duplicate driver names in Drivers (different IDs) | 4 | 7.27 | names are never used as keys; always join on driver_id |
| R05 | warn | Same vehicle model appears under several vehicle types | 6 | 66.67 | vehicle_type (operational class from Orders) moved to Vehicles dim next to vehicle_model; both kept, conflict documented |
| R05b | info | Vehicles never used in any order | 4 | 8.89 | kept in dim as 'Unassigned' (spare fleet) |
| R06 | info | Drivers/vehicles working for more than one hub | 0 | 0.0 | home_hub_id = modal hub (data shows 1:1) |
| R07a | error | Cancelled orders flagged Is Delayed=True | 252 | 100.0 | is_delayed recomputed: delay only applies to Delivered orders |
| R07b | error | Cancelled orders carrying CSAT=1 placeholder | 252 | 100.0 | csat_score set to NULL for cancelled orders (no survey exists) |
| R08a | warn | Delivery date != order date + floor((processing+delivery hours)/24) | 1,830 | 6.6 | hours are treated as the authoritative duration; Step 03 builds timestamps so dates reconcile wherever feasible |
| R08b | error | Delivery before order | 0 | 0.0 | none needed |
| R09a | warn | Order served by a vehicle before its purchase date | 782 | 2.79 | kept; flagged as `vehicle_before_purchase`. Dim dates treated as registry dates, not in-service dates |
| R09b | warn | Order served by a driver before hire date | 1,193 | 4.26 | kept; flagged as `driver_before_hire` |
| R10 | info | Orders served by vehicles whose *current* status is 'Maintenance' | 7,581 | 27.1 | Vehicle Status is a point-in-time snapshot, not history; never used as a historical filter |
| R11a | error | csat_score outside 1-5 | 0 | 0.0 | none needed |
| R11b | error | non-positive durations | 0 | 0.0 | none needed |
| R11c | error | Missing delivery hours on delivered orders | 0 | 0.0 | none needed |
| R12 | warn | Hub Capacity unit undocumented | 6 | 100.0 | assumed orders/month (ADR-0003). Mean monthly utilisation: hub 1: 122%, hub 2: 75%, hub 3: 77%, hub 4: 78%, hub 5: 75%, hub 6: 76% |
| R13 | info | Delay reasons are near-uniformly distributed | 0 | 0.0 | No action. Expect weak predictive signal; modelling step must report this honestly |

## Details

- **R03** – Every Driver ID carries exactly one name in Orders, but it differs from the master name for all IDs.
- **R04** – Charles Harris, Daniel Martin
- **R05** – Models affected: Chevrolet Express, Ford Transit, Freightliner M2, International DuraStar, Mercedes Sprinter, Ram ProMaster
- **R08a** – within +-1 day: 100.0%
- **R09a** – 7 vehicles involved
- **R13** – chi-square uniformity p=0.668; share range 9.3%-10.5%. Delay rate vs hub: chi-square p=0.199