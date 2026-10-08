-- Use the configured schema name as-is. dbt's default would prefix it with
-- the target schema (e.g. olist_dev_silver_olist_dev_silver).
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
