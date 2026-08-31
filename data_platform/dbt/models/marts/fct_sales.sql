with orders as (
    select * from {{ ref('stg_orders') }}
),

order_items as (
    select * from {{ ref('stg_order_items') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

products as (
    select * from {{ ref('stg_products') }}
)

select
    oi.order_item_id,
    o.order_id,
    o.customer_id,
    o.geo_id,
    oi.product_id,
    o.order_ts,
    cast(o.order_ts as date) as order_date,
    o.order_status,
    o.channel,
    o.currency,
    oi.qty,
    oi.unit_list_price,
    oi.unit_sell_price,
    oi.unit_cost,
    oi.line_discount,
    oi.line_tax,
    oi.line_net_revenue,
    (oi.unit_sell_price - oi.unit_cost) * oi.qty as line_gross_profit,
    cast(oi.ingested_at as timestamp) as loaded_at
from order_items oi
join orders o on oi.order_id = o.order_id
join customers c on o.customer_id = c.customer_id
join products p on oi.product_id = p.product_id
