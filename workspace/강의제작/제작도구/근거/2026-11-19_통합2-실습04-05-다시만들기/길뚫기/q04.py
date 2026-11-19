import json,urllib.request,sys
H='http://127.0.0.1:64531'
def run(q):
    req=urllib.request.Request(H+'/db/neo4j/tx/commit',json.dumps({'statements':[{'statement':q,'includeStats':True}]}).encode(),{'Content-Type':'application/json'})
    d=json.load(urllib.request.urlopen(req,timeout=30))
    if d['errors']: return 'ERR '+json.dumps(d['errors'],ensure_ascii=False)
    r=d['results'][0]; return {'cols':r['columns'],'rows':[x['row'] for x in r['data']]}
Q=[
"MATCH (n) RETURN count(n)",
"MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component) RETURN c.name",
"MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component) WHERE c.name='오일 쿨러' RETURN c.id",
"MATCH p=(:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(pt:Part) RETURN c.name, pt.name",
"MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:USES_PART]->(pt:Part) WHERE c.name='오일 쿨러' RETURN c.name, pt.name, pt.partNo",
"MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor) RETURN c.name, s.name, s.tag, s.virtual ORDER BY c.name, s.tag",
"MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor) WHERE s.virtual = false RETURN c.name, s.name, s.tag ORDER BY c.name, s.tag",
"MATCH (:Asset {code:'HYD-01'})-[:HAS_COMPONENT]->(c:Component)-[:MONITORED_BY]->(s:Sensor) RETURN c.name, count(s) AS sensors, collect(s.tag) AS tags ORDER BY sensors DESC, c.name",
]
for q in Q: print(q,'\n  ->',json.dumps(run(q),ensure_ascii=False))
