# 0006-honest-ml-verdict — Pre-registered verdict rule for models

**Status:** accepted

## Context
Near-uniform data makes spurious 'good' models easy to produce by leakage or tuning on the test set.

## Decision
Fix the success rule (AUC lower bound > 0.55) in config, time-ordered split, test used once, bootstrap CIs, model card; API exposes reliability.

## Consequences
Failure is reported as a finding; consumers cannot mistake a weak model for a good one.
