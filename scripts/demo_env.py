"""Run a FleetPulse command with isolated Demo configuration."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if len(sys.argv) < 2:
    raise SystemExit(
        "Usage: python scripts/demo_env.py pipeline/05_consume_to_postgres.py [args...]"
    )

env = os.environ.copy()
env["FLEETPULSE_CONFIG"] = "settings.demo.yaml"
env["PG_DB"] = "fleetpulse_demo"

command = [sys.executable, *sys.argv[1:]]
print("Demo config : settings.demo.yaml", flush=True)
print("Demo DB     : fleetpulse_demo", flush=True)
print("Command     :", " ".join(command), flush=True)

subprocess.run(command, cwd=ROOT, env=env, check=True)
