-- What the app and dashboards read: delivery SLA per customer state,
-- per promised delivery date.
select
    f.promised_date,
    c.customer_state,
    count(*)                                              as delivered_orders,
    count_if(f.is_late)                                   as late_orders,
    round(count_if(f.is_late) / count(*), 4)              as late_rate,
    round(avg(f.delay_days) filter (where f.is_late), 1)  as avg_delay_days_when_late
from {{ ref('fct_order_delivery') }} f
join {{ ref('dim_customer') }} c using (customer_id)
group by all
