"""STEP 01 – Ingest raw CSVs: normalise encoding to UTF-8 and profile them.

Why: the supplied files are UTF-16 (BOM 0xFF 0xFE). Most tools (pandas default, Postgres COPY, Git diffs)
expect UTF-8, so encoding is normalised once, at the edge, and every later step reads UTF-8.

Input : data/raw/*.csv                     (as received, untouched)
Output: data/interim/*.csv                 (UTF-8, byte-for-byte same content)
        reports/dq/01_raw_profile.json     (machine-readable profile)
        reports/dq/01_raw_profile.md       (human-readable profile)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fleetpulse.common import get_logger, path  # noqa: E402

log = get_logger("step01")
FILES = ["Orders", "Drivers", "Hubs", "Vehicles"]


def detect_encoding(fp: Path) -> str:
    head = fp.read_bytes()[:4]
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    if head.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    return "utf-8"


def read_any(fp: Path) -> pd.DataFrame:
    enc = detect_encoding(fp)
    return pd.read_csv(fp, encoding=enc, sep=None, engine="python"), enc


def profile(df: pd.DataFrame) -> dict:
    return {
        "rows": int(len(df)),
        "columns": {
            c: {
                "dtype": str(df[c].dtype),
                "nulls": int(df[c].isna().sum()),
                "distinct": int(df[c].nunique(dropna=True)),
                "sample": [str(x) for x in df[c].dropna().unique()[:3]],
            }
            for c in df.columns
        },
        "duplicate_rows": int(df.duplicated().sum()),
    }


def main() -> None:
    raw, out, rep = path("raw"), path("interim"), path("reports_dq")
    result = {}
    for name in FILES:
        src = raw / f"{name}.csv"
        df, enc = read_any(src)
        df.columns = [c.strip() for c in df.columns]
        df.to_csv(out / f"{name}.csv", index=False, encoding="utf-8")
        result[name] = {"source_encoding": enc, **profile(df)}
        log.info("%s: %s rows, encoding=%s -> UTF-8", name, len(df), enc)

    (rep / "01_raw_profile.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = ["# Step 01 – Raw data profile", ""]
    for name, p in result.items():
        lines += [f"## {name}  ({p['rows']:,} rows, source encoding `{p['source_encoding']}`)", "",
                  "| column | dtype | nulls | distinct | sample |", "|---|---|---|---|---|"]
        for c, m in p["columns"].items():
            lines.append(f"| {c} | {m['dtype']} | {m['nulls']:,} | {m['distinct']:,} | {', '.join(m['sample'])} |")
        lines += ["", f"Duplicate full rows: **{p['duplicate_rows']}**", ""]
    (rep / "01_raw_profile.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Profile written to reports/dq/01_raw_profile.md")


if __name__ == "__main__":
    main()
