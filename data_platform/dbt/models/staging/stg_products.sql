with source_data as (
    select
        product_id,
        sku,
        product_name,
        category_l1,
        category_l2,
        brand,
        unit_cost,
        list_price,
        created_at,
        updated_at
    from {{ source('globalcart_source', 'dim_product') }}
)

select
    product_id,
    sku,
    product_name,
    lower(category_l1) as category_l1,
    lower(category_l2) as category_l2,
    brand,
    cast(unit_cost as numeric(12,2)) as unit_cost,
    cast(list_price as numeric(12,2)) as list_price,
    created_at as ingested_at,
    updated_at as last_updated_at
from source_data
