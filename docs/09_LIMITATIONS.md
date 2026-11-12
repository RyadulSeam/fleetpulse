# Limitations (read before presenting this project)

1. **Not a live source.** It is a replay simulation of 2023-24 history. Say so.
2. **Synthetic elements:** time-of-day of events, destinations/distances, parcel weight, service level, vehicle telemetry. Independent of delays by design.
3. **Weather** is real only if Open-Meteo was reachable in step 03 (`weather_source`). The reference numbers in this repo's docs were produced with the flagged fallback; re-running with internet regenerates `reports/` (conclusions unchanged in nature, figures may shift slightly).
4. **Delay prediction is not achievable** with this data (AUC ≈ 0.5). Demand forecast gain is modest and noise-limited.
5. **Hub capacity unit is inferred**, not documented by the source. Dallas "over capacity" depends on that assumption.
6. **Source inconsistencies** (names, vehicle types, dates) were resolved by documented rules, not by knowing the truth.
7. **Scale:** ~140 k events. The architecture scales; the demo does not need it to.
8. **Kafka path:** developed to run against Redpanda via Docker; the offline CI exercises the identical validation/insert code through the JSONL source.
