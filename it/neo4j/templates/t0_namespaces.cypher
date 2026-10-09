// 지식 지도 이름 공간 목록(G4): 학생 노드(ns 가 있는 노드)의 이름 공간과 노드 수. 수업 기준(ns 없음)은 목록에 넣지 않는다(화면 기본값).
MATCH (n) WHERE n.ns IS NOT NULL
RETURN n.ns AS ns, count(n) AS nodes ORDER BY ns
