"""Spark job 2 — Documentation Gap Detector.

Finds doc_ids and error_codes where the verifier agent has repeatedly
returned low confidence or fallen back — a proxy for "the source docs are
thin or missing here," not just "the model had a bad day on one query."

Output feeds directly back into the live system: `priority_flags.json`
is read at request time by `voltagent/insights/feedback_loop.py`, which the
verifier agent consults to apply a stricter confidence threshold on exactly
these topics. This is the "self-improving RAG system" loop — a batch job's
output changes live agent behavior, not just a dashboard number.

Run:
    spark-submit voltagent/insights/spark_jobs/documentation_gap_detector.py \
        --input observability/parquet --output-flags observability/priority_flags.json
"""
from __future__ import annotations

import argparse
import json
import time

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from voltagent.config import settings


def build_spark_session() -> SparkSession:
    return SparkSession.builder.appName(settings.spark_app_name).getOrCreate()


def detect_documentation_gaps(
    spark: SparkSession,
    input_path: str,
    confidence_threshold: float | None = None,
    min_occurrences: int | None = None,
):
    confidence_threshold = confidence_threshold or settings.documentation_gap_confidence_threshold
    min_occurrences = min_occurrences or settings.documentation_gap_min_occurrences

    df = spark.read.parquet(input_path)

    low_confidence = df.filter(
        (F.col("confidence") < confidence_threshold) | (F.col("fallback") == True)  # noqa: E712
    )

    # Explode the citations list (array of {chunk_id, doc_title, page_number})
    # so gaps are attributed to actual source documents, not just error codes.
    with_docs = low_confidence.withColumn("citation", F.explode_outer("citations"))

    gap_by_doc = (
        with_docs.groupBy(F.col("citation.doc_title").alias("doc_title"))
        .agg(F.count("query_id").alias("low_confidence_count"))
        .filter(F.col("low_confidence_count") >= min_occurrences)
        .orderBy(F.desc("low_confidence_count"))
    )

    gap_by_error_code = (
        low_confidence.filter(F.col("error_code_mentioned").isNotNull())
        .groupBy("error_code_mentioned")
        .agg(F.count("query_id").alias("low_confidence_count"))
        .filter(F.col("low_confidence_count") >= min_occurrences)
        .orderBy(F.desc("low_confidence_count"))
    )

    return gap_by_doc, gap_by_error_code


def write_priority_flags(gap_by_doc, gap_by_error_code, output_path: str) -> None:
    flagged_docs = [row["doc_title"] for row in gap_by_doc.collect()]
    flagged_codes = [row["error_code_mentioned"] for row in gap_by_error_code.collect()]

    payload = {
        "generated_at": time.time(),
        "flagged_doc_ids": flagged_docs,
        "flagged_error_codes": flagged_codes,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect documentation gaps from low-confidence answers.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-flags", default=None, help="Defaults to settings.priority_flags_path")
    parser.add_argument("--confidence-threshold", type=float, default=None)
    parser.add_argument("--min-occurrences", type=int, default=None)
    args = parser.parse_args()

    spark = build_spark_session()
    gap_by_doc, gap_by_error_code = detect_documentation_gaps(
        spark, args.input, args.confidence_threshold, args.min_occurrences
    )

    gap_by_doc.show(20, truncate=False)
    gap_by_error_code.show(20, truncate=False)

    write_priority_flags(gap_by_doc, gap_by_error_code, args.output_flags or settings.priority_flags_path)
    spark.stop()


if __name__ == "__main__":
    main()
