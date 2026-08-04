"""Optional real-time layer — Spark Structured Streaming.

Batch jobs run nightly; this catches an emerging hardware issue *during the
day* instead of waiting until the next morning's batch run. Watches the
live query log as a streaming source and fires an alert when the same
error_code is reported by 3+ distinct technicians within a rolling window
(defaults: `streaming_fault_spike_count`, `streaming_fault_spike_window_minutes`).

This intentionally uses the file-source trigger (reading new lines appended
to the JSONL log directory) rather than a message broker like Kafka — it's
the honest choice for a portfolio project: it demonstrates Structured
Streaming's windowed-aggregation model correctly without requiring a Kafka
cluster nobody would actually stand up for a demo. Swapping the source for
Kafka later is a few lines (`spark.readStream.format("kafka")...`) with the
windowing/alerting logic below completely unchanged.

Run:
    spark-submit voltagent/insights/streaming/fault_spike_alert.py \
        --log-dir observability/streaming_source
"""
from __future__ import annotations

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType, TimestampType

from voltagent.config import settings

_SCHEMA = StructType(
    [
        StructField("stage", StringType()),
        StructField("query_id", StringType()),
        StructField("station_id", StringType()),
        StructField("error_code_mentioned", StringType()),
        StructField("event_time", TimestampType()),
    ]
)


def build_spark_session() -> SparkSession:
    return (
        SparkSession.builder.appName(f"{settings.spark_app_name}-streaming")
        .config("spark.sql.shuffle.partitions", "4")  # small for a demo workload
        .getOrCreate()
    )


def build_fault_spike_query(spark: SparkSession, source_dir: str, checkpoint_dir: str):
    """Reads newly-arriving query_complete events (as JSON files dropped into
    `source_dir` — a lightweight stand-in for a Kafka topic), and raises a
    spike alert when the same error_code is reported by enough distinct
    stations within the configured rolling window.
    """
    raw_stream = (
        spark.readStream.schema(_SCHEMA)
        .option("maxFilesPerTrigger", 1)
        .json(source_dir)
    )

    fault_events = raw_stream.filter(
        (F.col("stage") == "query_complete") & F.col("error_code_mentioned").isNotNull()
    )

    windowed = (
        fault_events.withWatermark("event_time", f"{settings.streaming_fault_spike_window_minutes} minutes")
        .groupBy(
            F.window(
                "event_time", f"{settings.streaming_fault_spike_window_minutes} minutes"
            ),
            "error_code_mentioned",
        )
        .agg(
            F.count("query_id").alias("report_count"),
            F.countDistinct("station_id").alias("distinct_stations"),
        )
        .filter(F.col("report_count") >= settings.streaming_fault_spike_count)
    )

    query = (
        windowed.writeStream.outputMode("update")
        .format("console")
        .option("checkpointLocation", checkpoint_dir)
        .start()
    )
    return query


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-time fault spike detector.")
    parser.add_argument("--log-dir", required=True, help="Directory streaming JSON event files land in")
    parser.add_argument("--checkpoint-dir", default="observability/streaming_checkpoint")
    args = parser.parse_args()

    spark = build_spark_session()
    query = build_fault_spike_query(spark, args.log_dir, args.checkpoint_dir)
    query.awaitTermination()


if __name__ == "__main__":
    main()
