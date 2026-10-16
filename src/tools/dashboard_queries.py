"""
Spark SQL behind every CSV of the static dashboard (docs/dashboard/data).

Used by export_dashboard_data. {gold}, {silver} and {bronze} are fully qualified
schema names, so the same queries run against dev, stg or prd. The categories
query expects a temp view `category_translation(portuguese, english)`.
"""

STATES = """
states AS (
  SELECT * FROM VALUES
    ('AC','Acre','North'),('AL','Alagoas','Northeast'),('AP','Amapá','North'),('AM','Amazonas','North'),
    ('BA','Bahia','Northeast'),('CE','Ceará','Northeast'),('DF','Distrito Federal','Center-West'),
    ('ES','Espírito Santo','Southeast'),('GO','Goiás','Center-West'),('MA','Maranhão','Northeast'),
    ('MT','Mato Grosso','Center-West'),('MS','Mato Grosso do Sul','Center-West'),('MG','Minas Gerais','Southeast'),
    ('PA','Pará','North'),('PB','Paraíba','Northeast'),('PR','Paraná','South'),('PE','Pernambuco','Northeast'),
    ('PI','Piauí','Northeast'),('RJ','Rio de Janeiro','Southeast'),('RN','Rio Grande do Norte','Northeast'),
    ('RS','Rio Grande do Sul','South'),('RO','Rondônia','North'),('RR','Roraima','North'),
    ('SC','Santa Catarina','South'),('SP','São Paulo','Southeast'),('SE','Sergipe','Northeast'),('TO','Tocantins','North')
    AS t(state, state_name, region)
)"""

# One row per delivered order with everything the dashboard needs.
BASE = """
latest_review AS (
  SELECT order_id, max_by(review_score, review_answer_timestamp) AS review_score
  FROM {bronze}.order_reviews
  GROUP BY order_id
),
items AS (
  SELECT order_id,
         max(shipping_limit_date)          AS shipping_limit,
         min_by(product_id, order_item_id) AS product_id
  FROM {silver}.silver_order_items
  GROUP BY order_id
),
base AS (
  SELECT f.order_id, f.seller_id, f.items_value, f.freight_value,
         f.delivery_days, f.promised_days, f.delay_days, f.is_late,
         date_format(f.promised_date, 'yyyy-MM')       AS promised_month,
         c.customer_state, c.customer_unique_id, s.seller_state,
         r.review_score, p.product_category_name,
         o.purchased_at, o.approved_at, o.shipped_at, f.delivered_at,
         coalesce(o.shipped_at > i.shipping_limit, false) AS seller_missed_handoff
  FROM {gold}.fct_order_delivery f
  JOIN {gold}.dim_customer c         ON c.customer_id = f.customer_id
  LEFT JOIN {gold}.dim_seller s      ON s.seller_id = f.seller_id
  LEFT JOIN {silver}.silver_orders o ON o.order_id = f.order_id
  LEFT JOIN items i                  ON i.order_id = f.order_id
  LEFT JOIN {silver}.silver_products p ON p.product_id = i.product_id
  LEFT JOIN latest_review r          ON r.order_id = f.order_id
)"""

QUERIES = {
"sla_by_state": "WITH " + STATES + "," + BASE + """
SELECT coalesce(b.customer_state, 'ALL')                                  AS state,
       coalesce(st.state_name, 'Brazil')                                  AS state_name,
       coalesce(st.region, 'All')                                         AS region,
       count(*)                                                           AS delivered_orders,
       count_if(is_late)                                                  AS late_orders,
       round(count_if(is_late) / count(*), 4)                             AS late_rate,
       round(avg(CASE WHEN is_late THEN delay_days END), 1)               AS avg_delay_days_when_late,
       round(avg(delivery_days), 1)                                       AS avg_delivery_days,
       round(avg(promised_days), 1)                                       AS avg_promised_days,
       round(avg(CASE WHEN NOT is_late THEN -delay_days END), 1)          AS avg_days_early_on_time,
       round(avg(CASE WHEN NOT is_late THEN review_score END), 2)         AS avg_review_on_time,
       round(avg(CASE WHEN is_late THEN review_score END), 2)             AS avg_review_late,
       round(sum(items_value), 0)                                         AS gmv_brl,
       round(sum(CASE WHEN is_late THEN items_value END), 0)              AS late_gmv_brl,
       round(avg(CASE WHEN is_late THEN CAST(seller_missed_handoff AS INT) END), 4) AS seller_late_share,
       round(avg(freight_value), 2)                                       AS avg_freight_brl
FROM base b
LEFT JOIN states st ON st.state = b.customer_state
GROUP BY GROUPING SETS ((b.customer_state, st.state_name, st.region), ())
""",

"sla_monthly": "WITH " + BASE + """
SELECT coalesce(customer_state, 'ALL')                       AS state,
       promised_month                                       AS month,
       count(*)                                             AS delivered_orders,
       count_if(is_late)                                    AS late_orders,
       round(count_if(is_late) / count(*), 4)               AS late_rate,
       round(avg(CASE WHEN is_late THEN delay_days END), 1) AS avg_delay_days_when_late
FROM base
WHERE promised_month BETWEEN '2017-02' AND '2018-08'
GROUP BY GROUPING SETS ((customer_state, promised_month), (promised_month))
""",

"stage_times": "WITH " + BASE + """,
steps AS (
  SELECT customer_state, is_late, promised_days,
         timestampdiff(SECOND, purchased_at, approved_at) / 86400.0 AS approval,
         timestampdiff(SECOND, approved_at, shipped_at) / 86400.0 AS handoff,
         timestampdiff(SECOND, shipped_at, delivered_at) / 86400.0 AS transit
  FROM base
)
SELECT coalesce(customer_state, 'ALL')                                 AS state,
       CASE WHEN is_late THEN 'Late' ELSE 'On time' END                AS outcome,
       count(*)                                                        AS orders,
       round(avg(CASE WHEN approval < 0 THEN 0 ELSE approval END), 2)  AS approval_days,
       round(avg(CASE WHEN handoff  < 0 THEN 0 ELSE handoff  END), 2)  AS seller_handoff_days,
       round(avg(CASE WHEN transit  < 0 THEN 0 ELSE transit  END), 2)  AS carrier_transit_days,
       round(avg(promised_days), 1)                                    AS promised_days
FROM steps
GROUP BY GROUPING SETS ((customer_state, is_late), (is_late))
""",

# avg_distance_km stays empty: the platform does not ingest the Olist geolocation table.
"routes": "WITH " + BASE + """
SELECT concat(seller_state, ' → ', customer_state)        AS route,
       seller_state, customer_state,
       count(*)                                          AS orders,
       count_if(is_late)                                 AS late_orders,
       round(count_if(is_late) / count(*), 4)            AS late_rate,
       CAST(NULL AS DOUBLE)                              AS avg_distance_km,
       round(avg(delivery_days), 1)                      AS avg_delivery_days
FROM base
GROUP BY seller_state, customer_state
HAVING count(*) >= 100
ORDER BY late_orders DESC
LIMIT 20
""",

"categories": "WITH " + BASE + """
SELECT replace(coalesce(t.english, product_category_name, 'unknown'), '_', ' ') AS category,
       count(*)                                    AS orders,
       count_if(is_late)                           AS late_orders,
       round(avg(delivery_days), 1)                AS avg_delivery_days,
       round(avg(review_score), 2)                 AS avg_review,
       round(count_if(is_late) / count(*), 4)      AS late_rate
FROM base
LEFT JOIN category_translation t ON t.portuguese = base.product_category_name
GROUP BY 1
ORDER BY orders DESC
LIMIT 15
""",

"reviews_by_delay": "WITH " + BASE + """,
bucketed AS (
  SELECT review_score,
         CASE WHEN delay_days <= -15 THEN 1 WHEN delay_days <= -8 THEN 2 WHEN delay_days <= -1 THEN 3
              WHEN delay_days = 0 THEN 4 WHEN delay_days <= 3 THEN 5 WHEN delay_days <= 7 THEN 6
              WHEN delay_days <= 14 THEN 7 ELSE 8 END AS bucket_order
  FROM base
  WHERE review_score IS NOT NULL
)
SELECT bucket_order,
       element_at(array('15+ days early','8–14 days early','1–7 days early','On the day',
                        '1–3 days late','4–7 days late','8–14 days late','15+ days late'), bucket_order) AS delay_bucket,
       count(*)                                    AS orders,
       round(avg(review_score), 2)                 AS avg_review,
       round(avg(CASE WHEN review_score = 1 THEN 1.0 ELSE 0.0 END), 4) AS one_star_share,
       round(avg(CASE WHEN review_score = 5 THEN 1.0 ELSE 0.0 END), 4) AS five_star_share,
       bucket_order >= 5                           AS is_late
FROM bucketed
GROUP BY bucket_order
ORDER BY bucket_order
""",

"delay_distribution": "WITH " + BASE + """
SELECT least(greatest(delay_days, -45), 30) AS delay_days,
       count(*)                             AS orders
FROM base
GROUP BY 1
ORDER BY 1
""",

"repeat_purchase": "WITH " + BASE + """,
first_order AS (
  SELECT customer_unique_id, min_by(is_late, purchased_at) AS first_late
  FROM base
  GROUP BY customer_unique_id
),
orders_per_person AS (
  SELECT c.customer_unique_id, count(DISTINCT o.order_id) AS orders
  FROM {silver}.silver_orders o
  JOIN {gold}.dim_customer c ON c.customer_id = o.customer_id
  GROUP BY c.customer_unique_id
)
SELECT CASE WHEN f.first_late THEN 'Late' ELSE 'On time' END AS first_order,
       count(*)                                              AS customers,
       count_if(p.orders > 1)                                AS repeat_customers,
       round(count_if(p.orders > 1) / count(*), 4)           AS repeat_rate
FROM first_order f
JOIN orders_per_person p USING (customer_unique_id)
GROUP BY 1
ORDER BY 1 DESC
""",

"sellers": "WITH " + BASE + """
SELECT left(seller_id, 8)                                       AS seller,
       seller_state,
       count(*)                                                 AS orders,
       count_if(is_late)                                        AS late_orders,
       round(count_if(is_late) / count(*), 4)                   AS late_rate,
       round(count_if(seller_missed_handoff) / count(*), 4)     AS missed_handoff_rate,
       round(avg(timestampdiff(SECOND, approved_at, shipped_at) / 86400.0), 1) AS avg_handoff_days,
       round(avg(review_score), 2)                              AS avg_review
FROM base
GROUP BY seller_id, seller_state
HAVING count(*) >= 50
ORDER BY late_orders DESC
LIMIT 25
""",
}

# Sort order for the grouped results: the 'ALL' rows first, then states.
ORDER = {
    "sla_by_state": "ORDER BY state = 'ALL' DESC, state",
    "sla_monthly": "ORDER BY state = 'ALL' DESC, state, month",
    "stage_times": "ORDER BY state = 'ALL' DESC, state, outcome DESC",
}

def query(name: str, **schemas) -> str:
    """The final SQL for one dataset, with schemas filled in and grouped results sorted."""
    sql = QUERIES[name].format(**schemas).strip()
    return f"SELECT * FROM (\n{sql}\n) AS q\n{ORDER[name]}" if name in ORDER else sql
