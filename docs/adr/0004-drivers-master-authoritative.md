# 0004-drivers-master-authoritative — Master tables are authoritative; denormalised names dropped

**Status:** accepted

## Context
Orders.Driver Name disagrees with Drivers master for 100% of rows; vehicle types conflict with models.

## Decision
Keep only foreign keys in orders; take names/attributes from dimensions; document conflicts (R03, R05).

## Consequences
Consistent joins. If the Orders names were in fact correct, driver names in dashboards would be wrong — confirm with the data owner.
