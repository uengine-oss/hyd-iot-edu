import json,urllib.request
H='http://127.0.0.1:64531'
def run(q):
    req=urllib.request.Request(H+'/db/neo4j/tx/commit',json.dumps({'statements':[{'statement':q,'includeStats':True}]}).encode(),{'Content-Type':'application/json'})
    d=json.load(urllib.request.urlopen(req,timeout=30)); return json.dumps(d['errors'] or d['results'][0].get('stats',{}),ensure_ascii=False)
print(run("CREATE (a:임시시험 {id:'t-A'})-[:감시된다]->(b:임시시험 {id:'t-B'})"))
print(run("MATCH (a:임시시험 {id:'t-A'}) DELETE a"))
print(run("MATCH (n:임시시험) DETACH DELETE n"))
print(run("MATCH (n) RETURN count(n)"))
