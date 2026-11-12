# 0007-redpanda-over-kafka — Redpanda as the local broker

**Status:** accepted

## Context
Need a free Kafka-compatible broker that runs in one container on a laptop.

## Decision
Use Redpanda (Kafka API); clients use confluent-kafka.

## Consequences
Same code runs on Kafka/MSK/Confluent. No ZooKeeper/KRaft setup.
