MATCH p = (:Asset {code: 'HYD-01'})-[:HAS_COMPONENT]->(:Component)<-[:MOUNTED_ON]-(:Sensor)-[:MEASURES]->(:StateVariable) RETURN p;
