// ① 필수 속성 tag 와 virtual 이 없는 센서
CREATE (s:Sensor {id: 'sen:test', name: '시험용 센서'});
// ② 센서와 같은 id 를 가진 구성 요소
CREATE (c:Component {id: 'sen:ts1', name: '시험용 구성 요소'});
// ③ 끝이 상태 변수가 아니라 구성 요소인 MEASURES
MATCH (s:Sensor {id: 'sen:test'}), (c:Component {id: 'comp:oil-cooler'}) CREATE (s)-[:MEASURES]->(c);
// ④ 센서 하나가 상태 변수 둘을 재는 MEASURES
MATCH (s:Sensor {id: 'sen:test'}), (v:StateVariable {id: 'sv:ts1'}) CREATE (s)-[:MEASURES]->(v);
MATCH (s:Sensor {id: 'sen:test'}), (v:StateVariable {id: 'sv:ps1'}) CREATE (s)-[:MEASURES]->(v);
// ⑤ 그래프 DB에 없는 id 를 끝으로 적은 MOUNTED_ON
MATCH (s:Sensor {id: 'sen:test'}), (c:Component {id: 'comp:cooler'}) MERGE (s)-[:MOUNTED_ON]->(c);
