MERGE (k:Knowledge {id: "HM-8:SOP-COOL-14:step:1"}) SET k.text = "시험용 지식";
MERGE (d:Document {id: "HM-8@1.1"});
MATCH (k:Knowledge {id: "HM-8:SOP-COOL-14:step:1"}), (d:Document {id: "HM-8@1.1"}) MERGE (k)-[:FROM_DOCUMENT]->(d);
