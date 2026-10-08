-- Calendar covering the full Olist period.
with days as (
    select explode(sequence(date'2016-09-01', date'2018-12-31', interval 1 day)) as date_day
)
select
    cast(date_format(date_day, 'yyyyMMdd') as int) as date_key,
    date_day,
    year(date_day)                                 as year,
    month(date_day)                                as month,
    date_format(date_day, 'MMM')                   as month_name,
    date_format(date_day, 'EEEE')                  as day_name,
    dayofweek(date_day) in (1, 7)                  as is_weekend
from days
