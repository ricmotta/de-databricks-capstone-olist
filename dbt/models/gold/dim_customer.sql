-- One row per customer_id (Olist issues a new customer_id per order;
-- customer_unique_id identifies the person).
-- Zip code and city are quasi-identifiers: masked and tagged after each build.
{{ config(
    post_hook=[
        "alter table {{ this }} alter column customer_zip_code_prefix set mask {{ this.database }}.{{ this.schema }}.mask_zip_prefix",
        "alter table {{ this }} alter column customer_city set mask {{ this.database }}.{{ this.schema }}.mask_city",
        "alter table {{ this }} alter column customer_zip_code_prefix set tags ('pii' = 'quasi_identifier')",
        "alter table {{ this }} alter column customer_city set tags ('pii' = 'quasi_identifier')"
    ]
) }}

select
    customer_id,
    customer_unique_id,
    customer_city,
    customer_state,
    customer_zip_code_prefix
from {{ ref('silver_customers') }}
