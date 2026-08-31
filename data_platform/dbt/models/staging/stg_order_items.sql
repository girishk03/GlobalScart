with source_data as (
    select
        order_item_id,
        order_id,
        product_id,
        qty,
        unit_list_price,
        unit_sell_price,
        unit_cost,
        line_discount,
        line_tax,
        line_net_revenue,
        created_at,
        updated_at
    from {{ source('globalcart_source', 'fact_order_items') }}
)

select
    order_item_id,
    order_id,
    product_id,
    qty,
    cast(unit_list_price as numeric(12,2)) as unit_list_price,
    cast(unit_sell_price as numeric(12,2)) as unit_sell_price,
    cast(unit_cost as numeric(12,2)) as unit_cost,
    cast(line_discount as numeric(14,2)) as line_discount,
    cast(line_tax as numeric(14,2)) as line_tax,
    cast(line_net_revenue as numeric(14,2)) as line_net_revenue,
    created_at as ingested_at,
    updated_at as last_updated_at
from source_data
