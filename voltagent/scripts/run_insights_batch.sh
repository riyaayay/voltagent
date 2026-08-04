#!/usr/bin/env bash
# Nightly Insights batch pipeline: export logs -> run the three Spark jobs.
# Intended to be cron'd (e.g. 2am daily) once there's a real query volume
# to mine. Each spark-submit uses local[*] by default — point --master at a
# real cluster for anything beyond a laptop/demo run.
set -euo pipefail

INPUT_DIR="${INSIGHTS_LOG_DIR:-observability/parquet}"
FLAGS_OUT="${PRIORITY_FLAGS_PATH:-observability/priority_flags.json}"
SPARK_MASTER="${SPARK_MASTER:-local[*]}"

echo "[1/4] Exporting JSONL observability log to partitioned Parquet ..."
python -m voltagent.insights.log_export --output-dir "$INPUT_DIR"

echo "[2/4] Fault Recurrence Miner ..."
spark-submit --master "$SPARK_MASTER" voltagent/insights/spark_jobs/fault_recurrence_miner.py \
  --input "$INPUT_DIR" --output observability/insights/fault_recurrence

echo "[3/4] Documentation Gap Detector (writes priority_flags.json read by the verifier agent) ..."
spark-submit --master "$SPARK_MASTER" voltagent/insights/spark_jobs/documentation_gap_detector.py \
  --input "$INPUT_DIR" --output-flags "$FLAGS_OUT"

echo "[4/4] Charger Model Correlation ..."
spark-submit --master "$SPARK_MASTER" voltagent/insights/spark_jobs/charger_model_correlation.py \
  --input "$INPUT_DIR" --output observability/insights/model_correlation

echo "Insights batch run complete. Updated priority flags: $FLAGS_OUT"
