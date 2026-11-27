// 적재 — 노드는 id로 같은 대상을 알아보고(MERGE), 값은 처음 만들 때만 넣는다(ON CREATE SET — 다시 적재해도 수정본이 고친 값을 되돌리지 않음). 관계는 양 끝 id와 관계 이름으로 알아본다.
// 넣을 것: Component
UNWIND $rows AS row MERGE (n:Component {id: row.id}) ON CREATE SET n = row;

// 넣을 것: Part
UNWIND $rows AS row MERGE (n:Part {id: row.id}) ON CREATE SET n = row;

// 넣을 것: Quantity
UNWIND $rows AS row MERGE (n:Quantity {id: row.id}) ON CREATE SET n = row;

// 넣을 것: Sensor
UNWIND $rows AS row MERGE (n:Sensor {id: row.id}) ON CREATE SET n = row;

// 넣을 것: Unit
UNWIND $rows AS row MERGE (n:Unit {id: row.id}) ON CREATE SET n = row;

// 넣을 것: HAS_COMPONENT
UNWIND $rows AS row MATCH (a:Asset {id: row.a}), (b:Component {id: row.b}) MERGE (a)-[r:HAS_COMPONENT]->(b) ON CREATE SET r = row.props;

// 넣을 것: MONITORED_BY
UNWIND $rows AS row MATCH (a:Component {id: row.a}), (b:Sensor {id: row.b}) MERGE (a)-[r:MONITORED_BY]->(b) ON CREATE SET r = row.props;

// 넣을 것: OBSERVES
UNWIND $rows AS row MATCH (a:Sensor {id: row.a}), (b:Quantity {id: row.b}) MERGE (a)-[r:OBSERVES]->(b) ON CREATE SET r = row.props;
