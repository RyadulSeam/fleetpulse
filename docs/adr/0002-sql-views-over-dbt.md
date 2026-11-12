# 0002-sql-views-over-dbt — SQL views instead of dbt (for now)

**Status:** accepted

## Context
Silver/gold logic is ~10 views over 140 k events; dbt adds tooling for little gain here.

## Decision
Keep versioned SQL files executed by step 06; views make late/duplicate events self-healing.

## Consequences
Fewer moving parts. Migration to dbt (tests, docs, lineage) is straightforward and listed in the roadmap.
