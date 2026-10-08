-- Order items, incremental on the composite key.
{{ config(
    materialized='incremental',
    unique_key=['order_id', 'order_item_id'],
    incremental_strategy='merge'
) }}

select
    order_id,
    order_item_id,
    product_id,
    seller_id,
    shipping_limit_date,
    price,
    freight_value,
    updated_at
from {{ source('bronze', 'order_items') }}
{% if is_incremental() %}
where updated_at > (select coalesce(max(updated_at), timestamp'1900-01-01') from {{ this }})
{% endif %}
qualify row_number() over (partition by order_id, order_item_id order by updated_at desc) = 1
