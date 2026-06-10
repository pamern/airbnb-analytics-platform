{% macro clean_money(expression) -%}
    try_cast(
        nullif(regexp_replace(cast({{ expression }} as varchar), '[^0-9.-]', '', 'g'), '')
        as double
    )
{%- endmacro %}

{% macro clean_percent(expression) -%}
    try_cast(
        nullif(regexp_replace(cast({{ expression }} as varchar), '[^0-9.-]', '', 'g'), '')
        as double
    ) / 100.0
{%- endmacro %}

{% macro clean_boolean(expression) -%}
    case
        when lower(trim(cast({{ expression }} as varchar))) in ('t', 'true', '1', 'yes', 'y') then true
        when lower(trim(cast({{ expression }} as varchar))) in ('f', 'false', '0', 'no', 'n') then false
        else null
    end
{%- endmacro %}

{% macro clean_text(expression) -%}
    nullif(trim(cast({{ expression }} as varchar)), '')
{%- endmacro %}

{% macro source_column(relation, column_name, alias='src', default=none) -%}
    {%- if execute -%}
        {%- set columns = adapter.get_columns_in_relation(relation) -%}
        {%- set ns = namespace(found_name=none) -%}
        {%- for column in columns -%}
            {%- if column.name | lower == column_name | lower -%}
                {%- set ns.found_name = column.name -%}
            {%- endif -%}
        {%- endfor -%}

        {%- if ns.found_name is not none -%}
            {{ return(alias ~ "." ~ adapter.quote(ns.found_name)) }}
        {%- elif default is not none -%}
            {{ return(default) }}
        {%- else -%}
            {{ exceptions.raise_compiler_error(
                "Required source column '" ~ column_name ~ "' not found in relation " ~ relation
            ) }}
        {%- endif -%}
    {%- else -%}
        {{ return(alias ~ "." ~ adapter.quote(column_name)) }}
    {%- endif -%}
{%- endmacro %}
