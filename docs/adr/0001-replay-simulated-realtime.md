# 0001-replay-simulated-realtime — Replay-simulated real-time

**Status:** accepted

## Context
Only historical data (2023-24) exists; there is no live feed, and faking one would be dishonest.

## Decision
Convert history to a time-ordered event stream and publish it through a real broker at adjustable speed; label the project as replay-simulated everywhere.

## Consequences
Authentic streaming mechanics (idempotency, late data, latency) at zero cost; a real source later replaces only the simulator.
