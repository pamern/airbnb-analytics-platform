{% test positive_or_null(model, column_name) %}
select *
from {{ model }}
where {{ column_name }} < 0
{% endtest %}

{% test between_or_null(model, column_name, min_value, max_value) %}
select *
from {{ model }}
where {{ column_name }} is not null
  and ({{ column_name }} < {{ min_value }} or {{ column_name }} > {{ max_value }})
{% endtest %}

{% test unique_combination_of_columns(model, combination_of_columns) %}
select
    {{ combination_of_columns | join(', ') }},
    count(*) as row_count
from {{ model }}
group by {{ combination_of_columns | join(', ') }}
having count(*) > 1
{% endtest %}

{% test greater_than(model, column_name, value) %}
select *
from {{ model }}
where {{ column_name }} is not null
  and {{ column_name }} <= {{ value }}
{% endtest %}

{% test non_negative(model, column_name) %}
select *
from {{ model }}
where {{ column_name }} is not null
  and {{ column_name }} < 0
{% endtest %}

{% test not_empty(model) %}
select *
from (
    select count(*) as row_count
    from {{ model }}
) as row_counts
where row_count = 0
{% endtest %}

{% test less_than_or_equal_or_null(model, column_name, right_column_name) %}
select *
from {{ model }}
where {{ column_name }} is not null
  and {{ right_column_name }} is not null
  and {{ column_name }} > {{ right_column_name }}
{% endtest %}

{% test location_member_exists(model, city, neighbourhood) %}
select 1
where not exists (
    select 1
    from {{ model }}
    where city = '{{ city }}'
      and neighbourhood = '{{ neighbourhood }}'
)
{% endtest %}

{% test row_count_matches(model, compare_model) %}
with left_counts as (
    select count(*) as row_count
    from {{ model }}
),

right_counts as (
    select count(*) as row_count
    from {{ compare_model }}
)

select
    left_counts.row_count as model_row_count,
    right_counts.row_count as compare_row_count
from left_counts
cross join right_counts
where left_counts.row_count != right_counts.row_count
{% endtest %}

{% test unknown_location_ratio_below(model, max_ratio=none) %}
{% set threshold = max_ratio if max_ratio is not none else env_var('GOLD_UNKNOWN_LOCATION_MAX_RATIO', '0.01') %}

with location_usage as (
    select
        count(*) as total_rows,
        sum(case when location.neighbourhood = 'UNKNOWN' then 1 else 0 end) as unknown_rows
    from {{ model }} as fact
    inner join {{ ref('dim_location') }} as location
        on fact.location_key = location.location_key
),

violations as (
    select
        total_rows,
        unknown_rows,
        coalesce(unknown_rows * 1.0 / nullif(total_rows, 0), 0.0) as unknown_ratio,
        cast({{ threshold }} as double) as max_allowed_ratio
    from location_usage
)

select *
from violations
where unknown_ratio > max_allowed_ratio
{% endtest %}
