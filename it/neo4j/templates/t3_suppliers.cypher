// T3-g — 공급사 승인 여부 (구매요청 조치의 공급사가 AVL인지)
MATCH (s:Supplier) RETURN s.id AS id, s.name AS name, s.avl AS avl
