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

{% test less_than_or_equal_or_null(model, column_name, right_column_name) %}
select *
from {{ model }}
where {{ column_name }} is not null
  and {{ right_column_name }} is not null
  and {{ column_name }} > {{ right_column_name }}
{% endtest %}
