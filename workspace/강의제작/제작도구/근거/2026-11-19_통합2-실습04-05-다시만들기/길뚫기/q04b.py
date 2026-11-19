import json,urllib.request
H=json.load(open('lab/랩_연결.json',encoding='utf-8'))['http']
def run(q):
    req=urllib.request.Request(H+'/db/neo4j/tx/commit',json.dumps({'statements':[{'statement':q}]}).encode(),{'Content-Type':'application/json'})
    d=json.load(urllib.request.urlopen(req,timeout=30)); return d['errors'] or [x['row'] for x in d['results'][0]['data']]
for q in ["MATCH (n) RETURN labels(n) AS 레이블, count(n) AS 개수 ORDER BY 개수 DESC",
          "MATCH ()-[r]->() RETURN type(r) AS 관계유형, count(r) AS 개수 ORDER BY 개수 DESC"]:
    print(q,'\n  ->',json.dumps(run(q),ensure_ascii=False))
