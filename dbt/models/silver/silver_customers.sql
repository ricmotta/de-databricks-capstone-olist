-- Conformed customers: standard casing and zero-padded zip codes.
{{ config(materialized='table') }}

select
    customer_id,
    customer_unique_id,
    lpad(customer_zip_code_prefix, 5, '0') as customer_zip_code_prefix,
    initcap(trim(customer_city))           as customer_city,
    upper(trim(customer_state))            as customer_state,
    updated_at
from {{ source('bronze', 'customers') }}
