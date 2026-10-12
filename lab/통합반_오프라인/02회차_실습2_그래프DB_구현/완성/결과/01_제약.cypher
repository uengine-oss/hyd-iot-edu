// 이 파일은 schema.json 의 클래스 11개마다 식별자 id 에 유일 제약을 건다.

// Asset(설비)의 id 는 겹치지 않는다
CREATE CONSTRAINT lab_asset_id IF NOT EXISTS FOR (n:Asset) REQUIRE n.id IS UNIQUE;

// Component(구성 요소)의 id 는 겹치지 않는다
CREATE CONSTRAINT lab_component_id IF NOT EXISTS FOR (n:Component) REQUIRE n.id IS UNIQUE;

// Sensor(센서)의 id 는 겹치지 않는다
CREATE CONSTRAINT lab_sensor_id IF NOT EXISTS FOR (n:Sensor) REQUIRE n.id IS UNIQUE;

// Actuator(구동기)의 id 는 겹치지 않는다
CREATE CONSTRAINT lab_actuator_id IF NOT EXISTS FOR (n:Actuator) REQUIRE n.id IS UNIQUE;

// StateVariable(상태 변수)의 id 는 겹치지 않는다
CREATE CONSTRAINT lab_statevariable_id IF NOT EXISTS FOR (n:StateVariable) REQUIRE n.id IS UNIQUE;

// Part(부품)의 id 는 겹치지 않는다
CREATE CONSTRAINT lab_part_id IF NOT EXISTS FOR (n:Part) REQUIRE n.id IS UNIQUE;

// Symptom(증상)의 id 는 겹치지 않는다
CREATE CONSTRAINT lab_symptom_id IF NOT EXISTS FOR (n:Symptom) REQUIRE n.id IS UNIQUE;

// FailureMode(고장 유형)의 id 는 겹치지 않는다
CREATE CONSTRAINT lab_failuremode_id IF NOT EXISTS FOR (n:FailureMode) REQUIRE n.id IS UNIQUE;

// Cause(원인)의 id 는 겹치지 않는다
CREATE CONSTRAINT lab_cause_id IF NOT EXISTS FOR (n:Cause) REQUIRE n.id IS UNIQUE;

// Skill(조치)의 id 는 겹치지 않는다
CREATE CONSTRAINT lab_skill_id IF NOT EXISTS FOR (n:Skill) REQUIRE n.id IS UNIQUE;

// Supplier(공급사)의 id 는 겹치지 않는다
CREATE CONSTRAINT lab_supplier_id IF NOT EXISTS FOR (n:Supplier) REQUIRE n.id IS UNIQUE;
