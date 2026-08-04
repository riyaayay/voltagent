"""Spark job 3 — Charger Model Correlation.

Groups faults by charger hardware/firmware model to separate systemic
issues (a specific model throwing the same error across many stations —
a hardware/firmware problem worth escalating to the manufacturer) from
one-off faults (a single station, single occurrence — likely a local
install/environment issue, not worth a hardware bulletin).

The distinguishing metric is *station spread*: a fault seen at 1 station
20 times is a local problem; a fault seen at 20 stations 1 time each,
concentrated on one charger_model, is a hardware signal.

Run:
    spark-submit voltagent/insights/spark_jobs/charger_model_correlation.py \
        --input observability/parquet --output observability/insights/model_correlation
"""
from __future__ import annotations

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from voltagent.config import settings


def build_spark_session() -> SparkSession:
    return SparkSession.builder.appName(settings.spark_app_name).getOrCreate()


def correlate_faults_with_charger_model(spark: SparkSession, input_path: str):
    df = spark.read.parquet(input_path)
    df = df.filter(F.col("error_code_mentioned").isNotNull() & F.col("charger_model").isNotNull())

    by_model_and_code = (
        df.groupBy("charger_model", "error_code_mentioned")
        .agg(
            F.count("query_id").alias("occurrence_count"),
            F.countDistinct("station_id").alias("distinct_stations"),
        )
    )

    # Systemic = the same fault appears at multiple distinct stations for
    # the same hardware model — a single busy station repeating a fault
    # does NOT count as systemic, however high its raw occurrence_count is.
    classified = by_model_and_code.withColumn(
        "classification",
        F.when(F.col("distinct_stations") >= 3, F.lit("systemic_hardware_signal"))
        .when(F.col("distinct_stations") == 1, F.lit("local_isolated_issue"))
        .otherwise(F.lit("watch")),
    )

    return classified.orderBy(F.desc("distinct_stations"), F.desc("occurrence_count"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Correlate recurring faults with charger hardware/firmware model.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    spark = build_spark_session()
    result = correlate_faults_with_charger_model(spark, args.input)
    result.write.mode("overwrite").parquet(args.output)

    print("\nSystemic hardware signals (fault seen at 3+ distinct stations, same model):")
    result.filter(F.col("classification") == "systemic_hardware_signal").show(20, truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
