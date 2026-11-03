MATCH (s:Supplier)-[r:SUPPLIES]->(p:Part)
WHERE p.id = $part OR $part IN coalesce(p.other_codes, [])
RETURN p.id AS part,s.id AS supplier,s.name AS name,r.supplier_part_no AS supplier_part_no,r.approved AS approved,r.approval_status AS approval_status,r.price_manwon AS price_manwon,r.defect_rate AS defect_rate,r.lead_days AS quoted_days,r.quote_date AS quoted_on,r.valid_until AS quote_until ORDER BY supplier
