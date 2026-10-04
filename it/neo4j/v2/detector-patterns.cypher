// Additive detector metadata. Existing edited values are preserved, never reset.
// clear predicates: DECISIONS 13/61, existing cooler hysteresis contract.
UNWIND [
  ['pattern:cooler-degradation','TS1 < 52 and slope(TS1) <= 0'],
  ['pattern:pump-leakage',"PLC.state == 'RUN' and ((PS1 >= 168 and FS1 >= 8) or LoadSP < 80)"],
  ['pattern:fan-vibration','VS1 < 1.1']
] AS row
MATCH (p:AnomalyPattern {id:row[0]})
SET p.detectionMode = coalesce(p.detectionMode, 'held'),
    p.clearRule = coalesce(p.clearRule, row[1]),
    p.clearHoldSeconds = coalesce(p.clearHoldSeconds, 60),
    p.slopeWindowSeconds = coalesce(p.slopeWindowSeconds, 60),
    p.severity = coalesce(p.severity, 'HIGH');

// Pump prose already requires RUN; represent that guard in the executable TESTS.
MATCH (p:AnomalyPattern {id:'pattern:pump-leakage'}), (i:InputData {id:'in:plc-state'})
MERGE (p)-[test:TESTS]->(i)
ON CREATE SET test.operator = '==', test.value = 'RUN';

MATCH (p:AnomalyPattern {id:'pattern:overheat-trip'})
SET p.detectionMode = coalesce(p.detectionMode, 'plc-trip');
