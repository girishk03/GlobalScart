with source_data as (
    select
        customer_id,
        customer_created_ts,
        geo_id,
        acquisition_channel,
        created_at,
        updated_at
    from {{ source('globalcart_source', 'dim_customer') }}
)

select
    customer_id,
    customer_created_ts as created_ts,
    geo_id,
    lower(acquisition_channel) as acquisition_channel,
    created_at as ingested_at,
    updated_at as last_updated_at
from source_data
