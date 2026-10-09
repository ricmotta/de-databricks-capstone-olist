# Olist Delivery SLA Platform — Databricks Capstone

Databricks Upskill Program capstone. Hybrid batch + streaming data platform on the
Olist Brazilian e-commerce dataset, answering one business question: **which orders
break their promised delivery date, and where is the delay concentrated?**

Owner: Ricardo Motta (solo since Daniel was reassigned). Delivery: 2026-10-09.

## Architecture

```
Lakebase (Postgres, OLTP source)
  └─ src/ingestion/02_extract_lakebase  → incremental Parquet extracts (watermark on updated_at)
       └─ src/pipeline/bronze.py        → Lakeflow Declarative Pipeline (Auto Loader)
            ├─ <table>_history          valid rows, append-only
            ├─ <table>_rejected         quarantine, with _failed_rules
            └─ <table>                  current state (AUTO CDC, SCD1)
                 └─ dbt/                → Silver (incremental) + Gold (star schema)
Zerobus Ingest (streaming)              → order status events (planned)
Databricks App (Streamlit)              → reads Gold aggregate (planned)
Asset Bundle + GitHub Actions           → deploy dev / stg / prd (planned)
```

## Environment facts (do not change without asking)

- Workspace: `https://factored-databricks-training.cloud.databricks.com` (AWS us-west-2)
- Catalog: `de_databricks_bp_wave_5` (shared with other trainees; never touch other schemas)
- Schemas follow `olist_<env>_<layer>`: `landing`, `ref`, `bronze`, `silver`, `gold`, `quarantine`
  - env is `dev`, `stg` or `prd`. No CREATE CATALOG, so environments are schemas, not catalogs.
- Lakebase: project `olist-capstone`, endpoint
  `projects/olist-capstone/branches/production/endpoints/primary`,
  host `ep-noisy-grass-d1gvpml8.database.us-west-2.cloud.databricks.com`,
  database `databricks_postgres`, Postgres schema `olist`
- Auth to Lakebase: short-lived OAuth token from
  `WorkspaceClient().postgres.generate_database_credential(endpoint=...)`, user = current user email
- Serverless compute: generic `jdbc` format can READ but not WRITE. Write to Postgres with
  `format("postgresql")` (options: host, port, database, dbtable, user, password).
- Personal access tokens are disabled. CI/CD authenticates as a service principal via OAuth M2M:
  GitHub secrets `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`.
- System tables: only `system.billing` is readable today (access/query/lakeflow requested).

## Conventions

- All code, comments, notebook text and outputs in **English**.
- Every notebook starts with a markdown cell: title, one-line purpose, "What it does"
  bullets, and a "Good to know" note when relevant. Simple and human, no jargon padding.
- Data quality rules: only add a comment claiming a real anomaly if it was verified in the
  data. Otherwise it is a plain sanity check, no comment.
- Python pipelines use `from pyspark import pipelines as dp`.
- Never put credentials, tokens or secrets in code, notebooks, or commits.

## Git workflow

- `main` is protected by convention: work on `feature/<short-name>` branches.
- One PR per deliverable, merged with **Squash and merge**, branch deleted after merge.
- PR description template:

  ```markdown
  ## Summary
  <One or two sentences: what this adds and why it matters.>

  ## Changes
  - `<path/to/file>`: <what it does>

  ## Validation
  - <How it was checked: counts, query results, a successful run>
  ```

- Code runs in Databricks from the workspace Git folder
  `/Workspace/Users/ricardo.motta@factored.ai/de-databricks-capstone-olist`.
  After pushing, the Git folder must be pulled before running anything there.
  Edit locally only; do not edit the same files in the Databricks Git folder.

## Status

- [x] Lakebase seeded (01_load_lakebase), counts reconciled
- [x] Incremental extract (02_extract_lakebase), CDC verified
- [x] Bronze pipeline with expectations, quarantine and AUTO CDC — reconciled
      (orders 99,433 + 8 rejected; order_items 112,646 + 4; order_payments 103,881 + 5)
- [x] dbt Silver + Gold
- [x] Asset Bundle + GitHub Actions (CI validates on PR; merge deploys stg; prd on manual dispatch)
- [ ] PII masking
- [ ] Zerobus streaming
- [ ] Dashboards (cost, audit, pipeline health)
- [ ] Databricks App
