"""Real TimescaleDB sensor queries and read boundaries, no LLM/plant writes."""
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'common'),str(ROOT/'it/agent'),str(ROOT/'it/dmn-mcp')]
from agentsvc.tools.mcp_tsdb import TimeSeriesDB
from dmn_mcp.tools import enveloped


def main():
    out=ROOT/'.evidence/reaudit/a051-timeseries-live';out.mkdir(exist_ok=True)
    checks=[]
    def save(name,value):(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,ok):
        checks.append(dict(name=name,passed=bool(ok)));save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    db=TimeSeriesDB();db.dsn='postgresql://hyd_timeseries_reader:hyd-timeseries-read-local@127.0.0.1:5432/hyd'
    with db._conn() as c:
        role=c.execute("select current_user,has_table_privilege(current_user,'public.tag_1s','INSERT'),has_table_privilege(current_user,'public.audit','SELECT'),current_setting('transaction_read_only')").fetchone()
    save('role',role)
    check('actual sensor principal cannot insert tags or read audit and uses read-only transaction',role==('hyd_timeseries_reader',False,False,'on'))
    schema=db.describe_schema();save('schema',schema)
    check('schema comes from actual permitted tables and observed sensor tags',set(schema['tables'])=={'tag_1s','feat_1s','tag_1m'} and any(s['name']=='VS1' for s in schema['recent_series']))
    anchor=datetime.now(timezone.utc).isoformat()
    where=f"asset='HYD-01' AND name='VS1' AND time > TIMESTAMPTZ '{anchor}'-interval '30 seconds' AND time <= TIMESTAMPTZ '{anchor}'"
    observed=db.query('SELECT count(*) AS samples,min(value) AS low,max(value) AS high,min(time) AS first,max(time) AS last FROM tag_1s WHERE '+where)
    save('observed',observed)
    count,low,high,first,last=observed['rows'][0]
    check('current sensor window has real timestamped samples',count>1 and first<=last and low<=high)
    duration=f'''WITH samples AS (SELECT time,value,LAG(time) OVER (ORDER BY time) AS previous FROM tag_1s WHERE {where})
        SELECT count(*) AS observations,BOOL_AND(value > {{threshold}}) AS all_observed_high,
        EXTRACT(EPOCH FROM max(time)-min(time)) AS covered_seconds,
        EXTRACT(EPOCH FROM max(time-previous)) AS maximum_gap_seconds,
        EXTRACT(EPOCH FROM TIMESTAMPTZ '{anchor}'-max(time)) AS newest_age_seconds FROM samples'''
    true=db.query(duration.format(threshold=low-1));false=db.query(duration.format(threshold=high+1))
    save('condition-true',true);save('condition-false',false)
    check('same source window changes predicate truth with supplied threshold',true['rows'][0][1] is True and false['rows'][0][1] is False)
    check('duration query also exposes coverage gap and newest age',true['rows'][0][2] is not None and true['rows'][0][3] is not None and true['rows'][0][4]>=0)
    empty=enveloped(lambda:db.query("SELECT value FROM tag_1s WHERE asset='A051-NONEXISTENT' AND time>now()-interval '30 seconds'"))()
    save('empty',empty);check('unobserved asset is normal zero rows not a fabricated value',empty['result']=='ok' and empty['document']['row_count']==0)
    bad=enveloped(lambda:db.query('SELECT nonexistent_value FROM tag_1s'))()
    save('bad-column',bad);check('invalid generated column is an explicit repairable error',bad['result']=='error' and bad['error_kind']=='INVALID')
    for name,sql in [('write','DELETE FROM tag_1s'),('outside','SELECT * FROM audit'),('sleep','SELECT pg_sleep(1)')]:
        rejected=enveloped(lambda:db.query(sql))();save(name,rejected)
        check(name+' is rejected before execution',rejected['result']=='error' and rejected['error_kind']=='INVALID')
    bucket=db.query("SELECT time_bucket(interval '1 minute',time) AS bucket,avg(value) FROM tag_1s WHERE asset='HYD-01' AND name='VS1' AND time>now()-interval '2 minutes' GROUP BY 1")
    save('bucket',bucket);check('actual Timescale time_bucket works through guarded query',bucket['row_count']>0)
    old=db.dsn;db.dsn='postgresql://hyd_timeseries_reader:unused@127.0.0.1:1/hyd'
    unavailable=enveloped(lambda:db.query('SELECT 1'))();db.dsn=old
    save('unavailable',unavailable);check('unavailable source is UNKNOWN rather than zero rows',unavailable['error_kind']=='UNKNOWN')
    evidence=db.evaluate([dict(id='probe',sql="SELECT avg(value) FROM tag_1s WHERE asset=%(asset)s AND name='VS1' AND time>now()-interval '30 seconds'",expect='gt',threshold=-1)],'HYD-01')
    save('evidence',evidence);check('existing parameterized Evidence path still reads actual data',evidence['probe']['value'] is not None and 'error' not in evidence['probe'])


if __name__=='__main__':main()
