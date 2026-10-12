// Exact ERP part identity for the explicit source-backed purchasing route.
MATCH (p:Part {partNo:$partNo})
RETURN p.id AS id,p.name AS name,p.partNo AS partNo
