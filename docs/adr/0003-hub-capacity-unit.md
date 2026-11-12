# 0003-hub-capacity-unit — Hub capacity interpreted as orders per month

**Status:** accepted

## Context
Source gives Hub Capacity (150-380) without a unit. Monthly orders / capacity = 75-78% for five hubs and 122% for Dallas; daily or weekly readings give implausible 3-30%.

## Decision
Assume orders per month; store as hub_capacity_orders_per_month; flag as an assumption in every report.

## Consequences
Utilisation KPI is usable but conditional. Confirm the unit with the client before presenting Dallas as over capacity.
