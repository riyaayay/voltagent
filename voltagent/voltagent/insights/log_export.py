"""Converts the append-only JSONL observability log into partitioned Parquet
— the boundary between the live system (voltagent/logging_utils.py writes
JSONL) and the batch analytics layer (Spark jobs read Parquet from HDFS).

Two log event types get joined here:
  - "query_complete": one row per answered query (station_id, charger_model,
    error_code_mentioned, verified, confidence, etc.)
  - "feedback": technician's resolved/not-resolved report, joined in on
    query_id when present.

Partitioned by (date, station_id) because that's the join/filter pattern
every downstream Spark job uses: "faults at this station over this window."

Writes to `settings.hdfs_uri` if set (via pyarrow's HDFS filesystem), or
falls back to a local partitioned directory tree otherwise — a single-node
local run and a real HDFS cluster produce the identical partition layout,
so `spark_jobs/*.py` don't need to know or care which one they're reading.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from voltagent.config import settings


def _read_jsonl(log_file: str) -> pd.DataFrame:
    rows = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def _join_feedback(df: pd.DataFrame) -> pd.DataFrame:
    completions = df[df["stage"] == "query_complete"].copy()
    feedback = df[df["stage"] == "feedback"][["query_id", "resolved"]].copy()

    if not feedback.empty:
        completions = completions.drop(columns=["resolved"], errors="ignore")
        completions = completions.merge(feedback, on="query_id", how="left")

    return completions


def _add_partition_columns(df: pd.DataFrame) -> pd.DataFrame:
    df["event_date"] = pd.to_datetime(df["ts"], unit="s").dt.strftime("%Y-%m-%d")
    df["station_id"] = df["station_id"].fillna("unknown")
    return df


def export_to_parquet(log_file: str | None = None, output_dir: str | None = None) -> str:
    log_file = log_file or settings.log_file
    output_dir = output_dir or settings.insights_log_dir

    df = _read_jsonl(log_file)
    if df.empty:
        raise ValueError(f"No events found in {log_file} — nothing to export.")

    completions = _join_feedback(df)
    completions = _add_partition_columns(completions)

    target_root = _resolve_output_root(output_dir)
    Path(target_root).mkdir(parents=True, exist_ok=True)

    # Partitioned write: one Parquet file per (event_date, station_id).
    completions.to_parquet(
        target_root,
        partition_cols=["event_date", "station_id"],
        index=False,
    )
    return target_root


def _resolve_output_root(output_dir: str) -> str:
    if settings.hdfs_uri:
        # pyarrow understands hdfs:// URIs directly when writing partitioned
        # datasets; callers running against a real cluster set HDFS_URI and
        # pass a path relative to it via INSIGHTS_LOG_DIR.
        return f"{settings.hdfs_uri.rstrip('/')}/{output_dir.lstrip('/')}"
    return output_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export observability JSONL log to partitioned Parquet.")
    parser.add_argument("--log-file", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    written_to = export_to_parquet(args.log_file, args.output_dir)
    print(f"Exported to: {written_to}")
