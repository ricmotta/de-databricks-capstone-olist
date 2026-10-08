-- Products with the source typos fixed and missing categories labelled.
{{ config(materialized='table') }}

select
    product_id,
    coalesce(product_category_name, 'unknown') as product_category_name,
    product_name_lenght                        as product_name_length,
    product_description_lenght                 as product_description_length,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm,
    updated_at
from {{ source('bronze', 'products') }}
