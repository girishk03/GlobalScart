
    
    

select
    order_item_id as unique_field,
    count(*) as n_records

from "globalcart"."globalcart_analytics"."fct_sales"
where order_item_id is not null
group by order_item_id
having count(*) > 1


