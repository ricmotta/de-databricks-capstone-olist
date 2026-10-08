-- Grain: one row per delivered order.
-- An order can include items from several sellers; seller_id is the seller
-- of the first item, which is enough for delivery analysis.
with items as (
    select
        order_id,
        count(*)                         as items_count,
        sum(price)                       as items_value,
        sum(freight_value)               as freight_value,
        min_by(seller_id, order_item_id) as seller_id
    from {{ ref('silver_order_items') }}
    group by order_id
)

select
    o.order_id,
    o.customer_id,
    i.seller_id,
    cast(date_format(o.purchased_at, 'yyyyMMdd') as int)                 as purchase_date_key,
    cast(date_format(o.promised_date, 'yyyyMMdd') as int)                as promised_date_key,
    o.purchased_at,
    o.delivered_at,
    o.promised_date,
    i.items_count,
    i.items_value,
    i.freight_value,
    datediff(cast(o.delivered_at as date), cast(o.purchased_at as date)) as delivery_days,
    datediff(o.promised_date, cast(o.purchased_at as date))              as promised_days,
    datediff(cast(o.delivered_at as date), o.promised_date)              as delay_days,
    cast(o.delivered_at as date) > o.promised_date                       as is_late
from {{ ref('silver_orders') }} o
left join items i using (order_id)
where o.order_status = 'delivered'
  and o.delivered_at is not null
