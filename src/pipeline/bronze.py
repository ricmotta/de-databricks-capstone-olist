"""
Bronze layer: Lakebase extracts -> validated Bronze tables.

Picks up the Parquet files written by 02_extract_lakebase and, for each
of the 7 Olist tables, builds:
- <table>_history   every valid change ever extracted (append-only)
- <table>_rejected  rows that failed a data quality rule, with the rule names
- <table>           current state per key, kept up to date with AUTO CDC

Bad rows never stop the pipeline: they are dropped from Bronze by
expectations and kept in quarantine for inspection.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

CATALOG = spark.conf.get("catalog", "de_databricks_bp_wave_5")
ENV     = spark.conf.get("env", "dev")

SOURCE_ROOT = f"/Volumes/{CATALOG}/olist_{ENV}_landing/lakebase_extracts"
BRONZE      = f"{CATALOG}.olist_{ENV}_bronze"
QUARANTINE  = f"{CATALOG}.olist_{ENV}_quarantine"

# Primary keys and data quality rules per table.
# Rules marked "profiling" target real anomalies found in the Olist data.
TABLES = {
    "customers": {
        "keys": ["customer_id"],
        "rules": {
            "customer_id_not_null": "customer_id IS NOT NULL",
            "unique_id_not_null":   "customer_unique_id IS NOT NULL",
            "state_is_valid":       "customer_state RLIKE '^[A-Z]{2}$'",
        },
    },
    "sellers": {
        "keys": ["seller_id"],
        "rules": {
            "seller_id_not_null": "seller_id IS NOT NULL",
            "state_is_valid":     "seller_state RLIKE '^[A-Z]{2}$'",
        },
    },
    "products": {
        "keys": ["product_id"],
        "rules": {
            "product_id_not_null": "product_id IS NOT NULL",
            "weight_not_negative": "product_weight_g IS NULL OR product_weight_g >= 0",
        },
    },
    "orders": {
        "keys": ["order_id"],
        "rules": {
            "order_id_not_null":    "order_id IS NOT NULL",
            "customer_id_not_null": "customer_id IS NOT NULL",
            "status_is_valid": (
                "order_status IN ('created','approved','invoiced','processing',"
                "'shipped','delivered','canceled','unavailable')"
            ),
            "promise_after_purchase": (
                "order_estimated_delivery_date >= date_trunc('DAY', order_purchase_timestamp)"
            ),
            # profiling: some orders are 'delivered' with no delivery date
            "delivered_has_date": (
                "order_status <> 'delivered' OR order_delivered_customer_date IS NOT NULL"
            ),
            "delivery_after_purchase": (
                "order_delivered_customer_date IS NULL "
                "OR order_delivered_customer_date >= order_purchase_timestamp"
            ),
        },
    },
    "order_items": {
        "keys": ["order_id", "order_item_id"],
        "rules": {
            "price_not_negative":   "price >= 0",
            "freight_not_negative": "freight_value >= 0",
            # profiling: a few shipping limits fall in 2020, after the dataset ends
            "shipping_limit_in_range": "shipping_limit_date < '2019-01-01'",
        },
    },
    "order_payments": {
        "keys": ["order_id", "payment_sequential"],
        "rules": {
            "value_not_negative": "payment_value >= 0",
            # profiling: 'not_defined' payment types and zero installments exist
            "payment_type_known": (
                "payment_type IN ('credit_card','boleto','voucher','debit_card')"
            ),
            "installments_positive": "payment_installments >= 1",
        },
    },
    "order_reviews": {
        "keys": ["review_id", "order_id"],
        "rules": {
            "score_in_range": "review_score BETWEEN 1 AND 5",
        },
    },
}


def raw_stream(table: str):
    """Incrementally read every Parquet extract of one table with Auto Loader."""
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .load(f"{SOURCE_ROOT}/{table}/")
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_ingested_at", F.current_timestamp())
    )


def build_table(table: str, cfg: dict):
    # A NULL rule result counts as a failure, so every rule is null-safe.
    rules = {name: f"coalesce(({expr}), false)" for name, expr in cfg["rules"].items()}
    all_valid = " AND ".join(f"({expr})" for expr in rules.values())

    @dp.table(
        name=f"{BRONZE}.{table}_history",
        comment=f"Every valid {table} change extracted from Lakebase (append-only).",
    )
    @dp.expect_all_or_drop(rules)
    def history():
        return raw_stream(table)

    @dp.table(
        name=f"{QUARANTINE}.{table}_rejected",
        comment=f"{table} rows that failed at least one data quality rule.",
    )
    def rejected():
        failed_rules = F.filter(
            F.array(*[F.when(~F.expr(expr), F.lit(name)) for name, expr in rules.items()]),
            lambda rule: rule.isNotNull(),
        )
        return (
            raw_stream(table)
            .where(f"NOT ({all_valid})")
            .withColumn("_failed_rules", failed_rules)
        )

    dp.create_streaming_table(
        name=f"{BRONZE}.{table}",
        comment=f"Current state of each {table} record (AUTO CDC, SCD type 1).",
    )
    dp.create_auto_cdc_flow(
        target=f"{BRONZE}.{table}",
        source=f"{BRONZE}.{table}_history",
        keys=cfg["keys"],
        sequence_by="updated_at",
        stored_as_scd_type="1",
    )


for table_name, table_cfg in TABLES.items():
    build_table(table_name, table_cfg)