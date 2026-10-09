-- Column mask functions used by Gold. Created (or refreshed) at the start of
-- every dbt run, in the Gold schema of the current environment.
-- Only members of olist_pii_readers see raw values; everyone else gets a
-- masked version that keeps the column useful for aggregation.
-- One macro per function: Databricks runs one SQL statement per hook.

{% macro create_mask_zip_prefix() %}
    create or replace function {{ target.catalog }}.olist_{{ var('env', 'dev') }}_gold.mask_zip_prefix(zip string)
    returns string
    comment 'Keeps the first 2 digits (region) unless the reader is in olist_pii_readers'
    return case
        when is_account_group_member('olist_pii_readers') then zip
        else concat(left(zip, 2), '***')
    end
{% endmacro %}

{% macro create_mask_city() %}
    create or replace function {{ target.catalog }}.olist_{{ var('env', 'dev') }}_gold.mask_city(city string)
    returns string
    comment 'Hides the city unless the reader is in olist_pii_readers'
    return case
        when is_account_group_member('olist_pii_readers') then city
        else 'REDACTED'
    end
{% endmacro %}
