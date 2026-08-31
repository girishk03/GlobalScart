-- ============================================================================
-- SQL Server DDL Schema for GlobalScart OLTP database
-- ============================================================================
-- Designed for mcr.microsoft.com/mssql/server:2022-latest container.
-- ============================================================================

-- Create database if not exists
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'globalcart')
BEGIN
    CREATE DATABASE globalcart;
END;
GO

USE globalcart;
GO

-- Create schema globalcart if not exists
IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = N'globalcart')
BEGIN
    EXEC sys.sp_executesql N'CREATE SCHEMA globalcart;';
END;
GO

-- 1. dim_geo
IF OBJECT_ID('globalcart.dim_geo', 'U') IS NULL
BEGIN
    CREATE TABLE globalcart.dim_geo (
        geo_id BIGINT PRIMARY KEY,
        country VARCHAR(60) NOT NULL,
        region VARCHAR(60) NOT NULL,
        city VARCHAR(80) NOT NULL,
        currency VARCHAR(10) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
        updated_at DATETIME2 NOT NULL DEFAULT GETDATE()
    );
END;
GO

-- 2. dim_customer
IF OBJECT_ID('globalcart.dim_customer', 'U') IS NULL
BEGIN
    CREATE TABLE globalcart.dim_customer (
        customer_id BIGINT PRIMARY KEY,
        customer_created_ts DATETIME2 NOT NULL,
        geo_id BIGINT NOT NULL,
        acquisition_channel VARCHAR(50) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
        updated_at DATETIME2 NOT NULL DEFAULT GETDATE(),
        CONSTRAINT FK_customer_geo FOREIGN KEY (geo_id) REFERENCES globalcart.dim_geo(geo_id)
    );
END;
GO

-- 3. dim_product
IF OBJECT_ID('globalcart.dim_product', 'U') IS NULL
BEGIN
    CREATE TABLE globalcart.dim_product (
        product_id BIGINT PRIMARY KEY,
        sku VARCHAR(50) NOT NULL,
        product_name VARCHAR(200) NOT NULL,
        category_l1 VARCHAR(50) NOT NULL,
        category_l2 VARCHAR(50) NOT NULL,
        brand VARCHAR(80) NOT NULL,
        unit_cost NUMERIC(12,2) NOT NULL,
        list_price NUMERIC(12,2) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
        updated_at DATETIME2 NOT NULL DEFAULT GETDATE()
    );
END;
GO

-- 4. dim_date
IF OBJECT_ID('globalcart.dim_date', 'U') IS NULL
BEGIN
    CREATE TABLE globalcart.dim_date (
        date_id INT PRIMARY KEY,
        date_value DATE NOT NULL UNIQUE,
        year INT NOT NULL,
        quarter INT NOT NULL,
        month INT NOT NULL,
        month_name VARCHAR(15) NOT NULL,
        week_of_year INT NOT NULL,
        day_of_month INT NOT NULL,
        day_of_week INT NOT NULL,
        day_name VARCHAR(15) NOT NULL,
        is_weekend BIT NOT NULL
    );
END;
GO

-- 5. fact_orders
IF OBJECT_ID('globalcart.fact_orders', 'U') IS NULL
BEGIN
    CREATE TABLE globalcart.fact_orders (
        order_id BIGINT PRIMARY KEY,
        customer_id BIGINT NOT NULL,
        geo_id BIGINT NOT NULL,
        order_ts DATETIME2 NOT NULL,
        order_status VARCHAR(30) NOT NULL,
        channel VARCHAR(30) NOT NULL,
        currency VARCHAR(10) NOT NULL,
        gross_amount NUMERIC(14,2) NOT NULL,
        discount_amount NUMERIC(14,2) NOT NULL,
        tax_amount NUMERIC(14,2) NOT NULL,
        net_amount NUMERIC(14,2) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
        updated_at DATETIME2 NOT NULL DEFAULT GETDATE(),
        CONSTRAINT FK_orders_customer FOREIGN KEY (customer_id) REFERENCES globalcart.dim_customer(customer_id),
        CONSTRAINT FK_orders_geo FOREIGN KEY (geo_id) REFERENCES globalcart.dim_geo(geo_id)
    );
END;
GO

-- 6. fact_order_items
IF OBJECT_ID('globalcart.fact_order_items', 'U') IS NULL
BEGIN
    CREATE TABLE globalcart.fact_order_items (
        order_item_id BIGINT PRIMARY KEY,
        order_id BIGINT NOT NULL,
        product_id BIGINT NOT NULL,
        qty INT NOT NULL,
        unit_list_price NUMERIC(12,2) NOT NULL,
        unit_sell_price NUMERIC(12,2) NOT NULL,
        unit_cost NUMERIC(12,2) NOT NULL,
        line_discount NUMERIC(14,2) NOT NULL,
        line_tax NUMERIC(14,2) NOT NULL,
        line_net_revenue NUMERIC(14,2) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
        updated_at DATETIME2 NOT NULL DEFAULT GETDATE(),
        CONSTRAINT FK_items_orders FOREIGN KEY (order_id) REFERENCES globalcart.fact_orders(order_id),
        CONSTRAINT FK_items_product FOREIGN KEY (product_id) REFERENCES globalcart.dim_product(product_id)
    );
END;
GO
