# 0005-rule-based-fleet-risk — Rule-based fleet risk score, not ML

**Status:** accepted

## Context
45 vehicles and cumulative breakdown counts cannot support a trustworthy model.

## Decision
Transparent weighted percentile score in SQL (gold.fleet_health).

## Consequences
Explainable, auditable; labelled a heuristic.
