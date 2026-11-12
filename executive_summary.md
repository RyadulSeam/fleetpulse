# Executive summary — Logistics Operations Intelligence (FleetPulse)

*Audience: Operations leadership. Technical detail: see `conclusion_summary.md`.*

## What was delivered
A working analytics platform for a 6-hub Texas delivery network (27,979 orders, 55 drivers, 45 vehicles, 2023–2024): an automated data pipeline,
a quality-checked data warehouse, a live operations dashboard, a 14-day demand forecast and a fleet-risk view. The platform is demonstrated on
replayed history as if it were arriving live; connecting it to your real order system replaces one component.

## What the data tells us
1. **Reliability is stable, not improving: 79.6 % of deliveries arrive on time** (79.9 % in 2023, 79.3 % in 2024). One in five deliveries is late.
2. **Late deliveries are expensive for customers.** Customer satisfaction drops from **4.50 to 3.02** when an order is late. Late orders take about 23 hours longer.
3. **Dallas Main Hub is the capacity pressure point.** It processed about **122 % of its stated capacity** on average (114–135 % in every quarter); the other five hubs run at 75–78 %.
   *Confirm with us what the capacity figure measures; we interpreted it as orders per month.*
4. **Delays are systemic, not local.** On-time rates are nearly identical across hubs (78.7 %–81.2 %) and drivers (75 %–83 % for drivers with 100+ deliveries), and the ten delay causes
   (vehicle breakdown, road construction, sorting errors, …) each account for 9–10 % of delays. There is no single hub, driver or cause to fix; improvement must come from the end-to-end process.
5. **Demand is forecastable in the short term**, with a modest accuracy gain over a simple weekly pattern (typical error ~31 % at single-hub daily level, because daily volumes are small).
6. **8 of 45 vehicles are high-risk** on a transparent score combining breakdowns per year, age and maintenance alerts.

## What we cannot tell you (yet)
We tested whether a delay can be predicted when an order is dispatched. **It cannot, with the data currently captured** — the available information (hub, driver, vehicle, route, weather, calendar) does not distinguish late from on-time orders. We therefore do *not* recommend automated delay scoring today.

## Recommendations
| # | Action | Why |
|---|---|---|
| 1 | Validate Dallas capacity and plan relief (overflow routing, extra shifts, or a satellite hub) | consistently above capacity |
| 2 | Attack delays as a process problem: end-to-end handoffs between hub processing and last mile | no localised cause exists |
| 3 | Capture richer operational data: scan events at each stop, GPS dwell time, promised delivery windows, real parcel attributes | needed to make delay prediction possible |
| 4 | Fix master-data conflicts (driver names, vehicle types, vehicle/driver dates) | reports currently rely on documented workarounds |
| 5 | Use the 14-day forecast for shift planning; review vehicles in the High-risk tier for preventive maintenance | actionable now |

## Data quality and trust
Warehouse totals reconcile 100 % with the source files. 24 source-data issues were found and each is documented with the decision taken. Anything not from your data (destinations, parcel weights, vehicle telemetry for the live demo) is labelled as simulated.
