-- Orders with business-friendly names. Incremental: each run merges only
-- rows whose updated_at is newer than what Silver already holds.
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge'
) }}

select
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp                    as purchased_at,
    order_approved_at                           as approved_at,
    order_delivered_carrier_date                as shipped_at,
    order_delivered_customer_date               as delivered_at,
    cast(order_estimated_delivery_date as date) as promised_date,
    updated_at
from {{ source('bronze', 'orders') }}
{% if is_incremental() %}
where updated_at > (select coalesce(max(updated_at), timestamp'1900-01-01') from {{ this }})
{% endif %}
-- Defensive dedupe: keep the latest version per key.
qualify row_number() over (partition by order_id order by updated_at desc) = 1
