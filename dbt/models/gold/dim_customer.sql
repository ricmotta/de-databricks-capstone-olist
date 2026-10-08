-- One row per customer_id (Olist issues a new customer_id per order;
-- customer_unique_id identifies the person).
select
    customer_id,
    customer_unique_id,
    customer_city,
    customer_state,
    customer_zip_code_prefix
from {{ ref('silver_customers') }}
