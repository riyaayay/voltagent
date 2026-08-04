"""Spark job 1 — Fault Recurrence Miner.

Finds error codes that recur at the same station within a rolling window
(default 7 days, `settings.fault_recurrence_window_days`). This is real
pattern mining, not a row count: a fault mentioned once is noise; the same
fault mentioned by multiple technicians at the same station within a week
is a signal that the underlying hardware issue wasn't actually fixed.

Run:
    spark-submit voltagent/insights/spark_jobs/fault_recurrence_miner.py \
        --input observability/parquet --output observability/insights/fault_recurrence
"""
from __future__ import annotations

import argparse

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

from voltagent.config import settings


def build_spark_session() -> SparkSession:
    return SparkSession.builder.appName(settings.spark_app_name).getOrCreate()


def mine_fault_recurrence(spark: SparkSession, input_path: str, window_days: int | None = None):
    window_days = window_days or settings.fault_recurrence_window_days

    df = spark.read.parquet(input_path)
    df = df.filter(F.col("error_code_mentioned").isNotNull())
    df = df.withColumn("event_ts", F.to_timestamp(F.from_unixtime("ts")))

    # For each (station_id, error_code) occurrence, count how many other
    # occurrences of the SAME fault at the SAME station fall within the
    # trailing `window_days` — a window function over a time-ranged frame,
    # not a naive groupBy count, so a fault reported twice a year apart
    # doesn't look the same as one reported three times in a week.
    station_fault_window = (
        Window.partitionBy("station_id", "error_code_mentioned")
        .orderBy(F.col("event_ts").cast("long"))
        .rangeBetween(-window_days * 86400, 0)
    )

    scored = df.withColumn(
        "recurrence_count_in_window", F.count("query_id").over(station_fault_window)
    )

    recurring = (
        scored.filter(F.col("recurrence_count_in_window") >= 2)
        .groupBy("station_id", "error_code_mentioned", "charger_model")
        .agg(
            F.max("recurrence_count_in_window").alias("max_recurrence_count"),
            F.min("event_ts").alias("first_seen"),
            F.max("event_ts").alias("last_seen"),
            F.avg("confidence").alias("avg_verifier_confidence"),
        )
        .orderBy(F.desc("max_recurrence_count"))
    )

    return recurring


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine recurring fault patterns per station.")
    parser.add_argument("--input", required=True, help="Path to partitioned Parquet log (local or hdfs://...)")
    parser.add_argument("--output", required=True, help="Where to write the result Parquet/CSV")
    parser.add_argument("--window-days", type=int, default=None)
    args = parser.parse_args()

    spark = build_spark_session()
    result = mine_fault_recurrence(spark, args.input, args.window_days)
    result.write.mode("overwrite").parquet(args.output)
    result.show(20, truncate=False)
    spark.stop()


if __name__ == "__main__":
    main()
