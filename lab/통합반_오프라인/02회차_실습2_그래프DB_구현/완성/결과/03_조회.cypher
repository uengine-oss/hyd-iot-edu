// 이 파일은 지난 시간에 던진 세 물음에, 관계를 따라가 답하는 조회 질의 3개를 담는다(읽기만 한다).
// 질의마다 적은 「나와야 맞는 것」은 실행해 본 결과가 아니라, graph.json 을 읽어 관계를 따라가며 따져 본 것이다.
// 물음에 나온 말은 name 또는 aliases 에서 정확히 같은 것으로 찾는다. 설비는 code 로, 공급사의 등급은 grade 로 찾는다.
// Part 는 schema.json 에 aliases 가 없으므로 name 으로만 찾는다.

// 조회 1. '열교환기'에 붙어 있는 센서 가운데 실물 계기는 무엇이고, 그것이 재는 값의 한계는 얼마이며 위쪽 한계인가 아래쪽 한계인가?
// 나와야 맞는 것: 1행. 센서 '유온 센서', 태그 'TS1', 재는_값 '유온', 한계 65, 단위 '℃', 한계_방향 'upper'(위쪽 한계), 한계_설명 '65 ℃에서 인터록'.
// 따져 본 길: '열교환기'는 comp:oil-cooler('오일 쿨러')의 aliases 에 있다. 여기에 붙은 센서는 sen:ts1 과 sen:ce 둘이고, sen:ce 는 virtual 이 true 라서 빠진다.
MATCH (c:Component)
WHERE c.name = '열교환기' OR '열교환기' IN c.aliases
MATCH (s:Sensor)-[:MOUNTED_ON]->(c)
WHERE s.virtual = false
MATCH (s)-[:MEASURES]->(v:StateVariable)
RETURN s.name AS 센서, s.tag AS 태그, v.name AS 재는_값, v.limit AS 한계, v.unit AS 단위, v.limit_direction AS 한계_방향, v.limit_note AS 한계_설명
ORDER BY s.tag;

// 조회 2. HYD-02 의 '유압 펌프'에 들어가는 교체 부품을 승인 공급사 가운데 가장 싸게 사려면 어디에서 얼마인가?
// 나와야 맞는 것: 1행. 부품 '펌프 축 씰 키트', 품번 'P-PMP-SEAL', 공급사 'A정밀 (저가)', 단가 35(만원).
// 따져 본 길: '유압 펌프'는 comp:main-pump('주 펌프 (A)')의 aliases 에 있고, 이 구성 요소가 쓰는 부품은 part:p-pmp-seal 하나다.
//            이 부품의 공급사는 sup:a(35), sup:b(55), sup:c(20) 셋인데, sup:c 는 approved 가 false 라서 빠지고 남은 둘 가운데 35 가 가장 싸다.
// 부품마다 가장 싼 값을 내고, 값이 같은 승인 공급사가 여럿이면 모두 낸다.
MATCH (:Asset {code: 'HYD-02'})-[:HAS_COMPONENT]->(c:Component)
WHERE c.name = '유압 펌프' OR '유압 펌프' IN c.aliases
MATCH (c)-[:USES_PART]->(p:Part)-[r:SUPPLIED_BY]->(s:Supplier)
WHERE s.approved = true
WITH p, min(r.price) AS 가장_싼_값
MATCH (p)-[r:SUPPLIED_BY]->(s:Supplier)
WHERE s.approved = true AND r.price = 가장_싼_값
RETURN p.name AS 부품, p.part_no AS 품번, s.name AS 공급사, r.price AS 단가
ORDER BY p.part_no, s.name;

// 조회 3. 순정 공급사에서만 산다면 팬 베어링은 얼마이고 며칠 걸리는가?
// 나와야 맞는 것: 1행. 부품 '팬 베어링', 공급사 'B-OEM (순정)', 단가 28(만원), 납기_날수 3.
// 따져 본 길: part:p-fan-brg 의 공급사는 sup:a(grade '저가')와 sup:b(grade '순정') 둘이고, grade 가 '순정'인 것은 sup:b 뿐이다.
// 물음에 승인 여부는 없으므로 approved 는 조건에 넣지 않는다.
MATCH (p:Part {name: '팬 베어링'})-[r:SUPPLIED_BY]->(s:Supplier {grade: '순정'})
RETURN p.name AS 부품, s.name AS 공급사, r.price AS 단가, r.lead_days AS 납기_날수
ORDER BY s.name;
