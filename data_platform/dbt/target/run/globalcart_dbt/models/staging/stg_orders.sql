
  create view "globalcart"."globalcart_staging"."stg_orders__dbt_tmp"
    
    
  as (
    with source_data as (
    select
        order_id,
        customer_id,
        geo_id,
        order_ts,
        order_status,
        channel,
        currency,
        gross_amount,
        discount_amount,
        tax_amount,
        net_amount,
        created_at,
        updated_at
    from "globalcart"."globalcart"."fact_orders"
)

select
    order_id,
    customer_id,
    geo_id,
    order_ts,
    lower(order_status) as order_status,
    lower(channel) as channel,
    upper(currency) as currency,
    cast(gross_amount as numeric(14,2)) as gross_amount,
    cast(discount_amount as numeric(14,2)) as discount_amount,
    cast(tax_amount as numeric(14,2)) as tax_amount,
    cast(net_amount as numeric(14,2)) as net_amount,
    created_at as ingested_at,
    updated_at as last_updated_at
from source_data
  );