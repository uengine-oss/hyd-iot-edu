-- 옛 설비 DB(원천 hyd-legacy, 스키마 legacy) — 실라버스 통합 40행 실습 06: 학생이 제공 파일 it/portal/www/samples/legacy-plant-db.sql 을
-- 데이터 연결에서 확인하고(표 · 샘플 행) 「판단 입력의 원천」에 잇고 되돌린다. 그 표가 실제 DB 에 있어야 샘플 · 연결 판정이 선다.
-- 아래 「제공 파일 본문」은 그 파일의 첫 CREATE TABLE 부터 끝까지 그대로다(정본은 제공 파일). 마이그레이션은 DB 컨테이너 안에서
-- 저장소 파일을 읽을 수 없어 본문을 담는다 — 둘이 다르면 workspace/개발/tests/test_fabric.py 의 옛 설비 DB 시험이 실패한다.
-- 읽기는 업무 DB 와 같은 전용 읽기 계정(hyd_enterprise_reader)이 한다. anon · authenticated 에는 주지 않는다.
create schema if not exists legacy;
revoke all on schema legacy from public;
set search_path = legacy;

-- ---- 제공 파일 본문 (it/portal/www/samples/legacy-plant-db.sql) ----
CREATE TABLE "T_EQP00" (
  "EQP_CD"  varchar(10) PRIMARY KEY,
  "EQP_NM"  varchar(40),
  "LOC_CD"  char(3),
  "INST_DT" date,
  "USE_YN"  char(1)
);

CREATE TABLE "T_EQP01" (
  "SEQ_NO"  bigint PRIMARY KEY,
  "EQP_CD"  varchar(10) NOT NULL,
  "MSR_DTM" timestamp NOT NULL,
  "C_PRS_A" numeric(6,1),
  "C_PRS_B" numeric(6,1),
  "C_TMP_O" numeric(5,1),
  "C_FLW_A" numeric(5,2),
  "C_VIB_F" numeric(5,2),
  "C_LD_R"  smallint,
  "ST_CD"   char(2)
);

CREATE TABLE "T_MNT10" (
  "WO_NO"   varchar(14) PRIMARY KEY,
  "EQP_CD"  varchar(10),
  "WO_TP"   char(2),
  "REQ_DT"  date,
  "CMP_DT"  date,
  "MH_QT"   numeric(5,1),
  "CST_AMT" integer,
  "RMK"     varchar(200)
);

INSERT INTO "T_EQP00" ("EQP_CD", "EQP_NM", "LOC_CD", "INST_DT", "USE_YN") VALUES
  ('HYD-01', '유압 유닛 1호', 'A01', '2009-03-14', 'Y'),
  ('HYD-02', '유압 유닛 2호', 'A02', '2011-07-02', 'Y'),
  ('HYD-03', '유압 유닛 3호', 'B01', '2014-11-20', 'Y'),
  ('HYD-00', '유압 유닛 시제품', 'Z99', '2004-05-01', 'N');

INSERT INTO "T_EQP01" ("SEQ_NO", "EQP_CD", "MSR_DTM", "C_PRS_A", "C_PRS_B", "C_TMP_O", "C_FLW_A", "C_VIB_F", "C_LD_R", "ST_CD") VALUES
  (1001, 'HYD-01', '2019-06-03 08:00:00', 182.4, NULL, 47.8, 9.12, 0.58, 90, '00'),
  (1002, 'HYD-02', '2019-06-03 08:00:00', 181.9, NULL, 48.1, 9.08, 0.61, 90, '00'),
  (1003, 'HYD-03', '2019-06-03 08:00:00', 182.1, NULL, 47.5, 9.10, 0.62, 85, '00'),
  (1004, 'HYD-01', '2019-06-10 08:00:00', 181.7, NULL, 51.9, 9.05, 0.60, 90, '00'),
  (1005, 'HYD-02', '2019-06-10 08:00:00', 176.3, NULL, 48.6, 8.71, 0.59, 90, '00'),
  (1006, 'HYD-03', '2019-06-10 08:00:00', 182.0, NULL, 47.9, 9.11, 0.84, 85, '00'),
  (1007, 'HYD-01', '2019-06-17 08:00:00', 182.2, NULL, 55.6, 9.07, 0.61, 90, '10'),
  (1008, 'HYD-02', '2019-06-17 08:00:00', 169.8, NULL, 49.0, 8.24, 0.60, 90, '10'),
  (1009, 'HYD-03', '2019-06-17 08:00:00', 181.8, NULL, 48.3, 9.09, 1.12, 85, '10'),
  (1010, 'HYD-01', '2019-06-24 08:00:00', 181.5, NULL, 57.2, 9.04, 0.63, 80, '20'),
  (1011, 'HYD-02', '2019-06-24 08:00:00', 164.1, NULL, 49.4, 7.91, 0.62, 80, '20'),
  (1012, 'HYD-03', '2019-06-24 08:00:00', 181.6, NULL, 48.8, 9.06, 1.41, 80, '20'),
  (1013, 'HYD-01', '2019-07-01 08:00:00', 182.3, NULL, 48.0, 9.13, 0.59, 90, '00'),
  (1014, 'HYD-02', '2019-07-01 08:00:00', 182.0, NULL, 47.7, 9.10, 0.60, 90, '00'),
  (1015, 'HYD-03', '2019-07-01 08:00:00', 182.2, NULL, 47.6, 9.11, 0.57, 85, '00');

INSERT INTO "T_MNT10" ("WO_NO", "EQP_CD", "WO_TP", "REQ_DT", "CMP_DT", "MH_QT", "CST_AMT", "RMK") VALUES
  ('WO190617-0001', 'HYD-01', 'CM', '2019-06-17', '2019-06-25', 3.5, 180000, '쿨러 핀 막힘 세척'),
  ('WO190617-0002', 'HYD-02', 'CM', '2019-06-17', '2019-06-27', 8.0, 2350000, '주 펌프 축 씰 교체'),
  ('WO190617-0003', 'HYD-03', 'CM', '2019-06-17', '2019-06-28', 6.0, 940000, '팬 베어링 교체'),
  ('WO190701-0001', 'HYD-01', 'PM', '2019-07-01', '2019-07-01', 1.5, 60000, '정기 점검'),
  ('WO190701-0002', 'HYD-02', 'PM', '2019-07-01', NULL, NULL, NULL, '정기 점검 (미완료)');
-- ---- 제공 파일 본문 끝 ----

reset search_path;
grant usage on schema legacy to hyd_enterprise_reader;
grant select on all tables in schema legacy to hyd_enterprise_reader;
