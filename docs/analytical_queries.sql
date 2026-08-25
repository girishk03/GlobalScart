-- ============================================================================
-- GlobalScart Analytical Queries
-- ============================================================================
-- These queries showcase the analytical capabilities of the BigQuery
-- DWH warehouse (globalcart_analytics dataset) and the business value
-- provided by the end-to-end data pipeline.
-- ============================================================================

-- 1. Monthly Revenue by Country
-- Purpose: Track geographical sales performance and monthly trends.
SELECT
    g.country,
    s.order_year,
    s.order_month,
    ROUND(SUM(s.calculated_net_revenue), 2) AS total_revenue,
    COUNT(DISTINCT s.order_id) AS total_orders
FROM `elite-matter-452317-g8.globalcart_analytics.fact_sales` s
JOIN `elite-matter-452317-g8.globalcart_analytics.dim_geo` g ON s.geo_id = g.geo_id
GROUP BY 1, 2, 3
ORDER BY s.order_year DESC, s.order_month DESC, total_revenue DESC;


-- 2. Customer Lifetime Value (CLV)
-- Purpose: Identify high-value customers and calculate their purchase behavior.
SELECT
    s.customer_id,
    c.acquisition_channel,
    MIN(s.order_date) AS first_purchase_date,
    MAX(s.order_date) AS last_purchase_date,
    COUNT(DISTINCT s.order_id) AS purchase_frequency,
    ROUND(SUM(s.calculated_net_revenue), 2) AS lifetime_value,
    ROUND(AVG(s.calculated_net_revenue), 2) AS average_order_value
FROM `elite-matter-452317-g8.globalcart_analytics.fact_sales` s
JOIN `elite-matter-452317-g8.globalcart_analytics.dim_customer` c ON s.customer_id = c.customer_id
GROUP BY 1, 2
ORDER BY lifetime_value DESC
LIMIT 10;


-- 3. Product Profitability & Margins
-- Purpose: Calculate item margins and profitability to identify key margin-drivers.
SELECT
    p.product_id,
    p.product_name,
    p.category_l1,
    p.category_l2,
    p.brand,
    SUM(s.qty) AS units_sold,
    ROUND(SUM(s.gross_item_amount), 2) AS gross_revenue,
    ROUND(SUM(s.calculated_net_revenue), 2) AS net_revenue,
    ROUND(SUM(s.qty * s.unit_cost), 2) AS total_cost,
    ROUND(SUM(s.calculated_net_revenue) - SUM(s.qty * s.unit_cost), 2) AS net_profit,
    ROUND(
        (SUM(s.calculated_net_revenue) - SUM(s.qty * s.unit_cost)) / NULLIF(SUM(s.calculated_net_revenue), 0) * 100, 
        2
    ) AS profit_margin_percent
FROM `elite-matter-452317-g8.globalcart_analytics.fact_sales` s
JOIN `elite-matter-452317-g8.globalcart_analytics.dim_product` p ON s.product_id = p.product_id
GROUP BY 1, 2, 3, 4, 5
ORDER BY net_profit DESC
LIMIT 15;


-- 4. Conversion Funnel (unpaid orders to completed checkouts)
-- Purpose: Measure drop-offs at different stages of the checkout process.
-- Note: This references transactional tables directly to identify bottlenecks.
WITH funnel_stages AS (
    SELECT 
        o.order_id,
        o.order_status,
        -- Stage 1: Checkout Created (all orders in PostgreSQL source start as checkout session)
        1 AS created_stage,
        -- Stage 2: Order Placed/Created (payment initiated)
        CASE WHEN o.order_status IN ('ORDER_CREATED', 'PLACED', 'PAID', 'SHIPPED', 'DELIVERED') THEN 1 ELSE 0 END AS placed_stage,
        -- Stage 3: Payment Completed (PAID, SHIPPED, DELIVERED)
        CASE WHEN o.order_status IN ('PAID', 'SHIPPED', 'DELIVERED') THEN 1 ELSE 0 END AS paid_stage,
        -- Stage 4: Order Delivered
        CASE WHEN o.order_status = 'DELIVERED' THEN 1 ELSE 0 END AS delivered_stage
    FROM globalcart.fact_orders o
)
SELECT
    SUM(created_stage) AS checkouts_created,
    SUM(placed_stage) AS orders_placed,
    SUM(paid_stage) AS payments_completed,
    SUM(delivered_stage) AS orders_delivered,
    ROUND(SUM(placed_stage) / SUM(created_stage) * 100, 2) AS checkout_to_order_percent,
    ROUND(SUM(paid_stage) / SUM(placed_stage) * 100, 2) AS order_to_payment_percent
FROM funnel_stages;


-- 5. Delivery SLA Performance
-- Purpose: Identify logistics performance, delays, and SLA breach rates.
-- Note: Queries PG transactional shipments table.
SELECT
    s.carrier,
    s.shipping_mode,
    COUNT(s.shipment_id) AS total_shipments,
    ROUND(AVG(DATE_PART('day', s.delivery_ts - s.shipment_ts)), 2) AS avg_delivery_days,
    SUM(CASE WHEN s.delivery_ts > s.estimated_delivery_ts THEN 1 ELSE 0 END) AS sla_breaches,
    ROUND(
        SUM(CASE WHEN s.delivery_ts > s.estimated_delivery_ts THEN 1 ELSE 0 END) / COUNT(s.shipment_id) * 100, 
        2
    ) AS sla_breach_rate_percent
FROM globalcart.fact_shipments s
WHERE s.delivery_ts IS NOT NULL
GROUP BY 1, 2
ORDER BY sla_breach_rate_percent DESC;


-- 6. Product Category Return Rates
-- Purpose: Monitor returns across brands/categories to isolate quality problems.
-- Note: Evaluates fact_orders returns.
SELECT
    p.category_l1,
    p.category_l2,
    p.brand,
    COUNT(DISTINCT s.order_id) AS total_orders,
    SUM(CASE WHEN s.order_status = 'RETURNED' THEN 1 ELSE 0 END) AS returned_orders,
    ROUND(
        SUM(CASE WHEN s.order_status = 'RETURNED' THEN 1 ELSE 0 END) / COUNT(DISTINCT s.order_id) * 100, 
        2
    ) AS return_rate_percent
FROM `elite-matter-452317-g8.globalcart_analytics.fact_sales` s
JOIN `elite-matter-452317-g8.globalcart_analytics.dim_product` p ON s.product_id = p.product_id
GROUP BY 1, 2, 3
ORDER BY return_rate_percent DESC
LIMIT 10;
