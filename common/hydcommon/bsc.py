"""Path-preserving qualitative BSC effects with explicit three-state predicates.

No natural-language condition parsing. Unknown effects remain identified estimates.
"""
from copy import deepcopy
import json
import re

from . import ranking

STRENGTH = {'high':1.0,'medium':0.6,'low':0.3}


def validate_policy(value):
    if isinstance(value,str):
        if len(value)>16000: raise ValueError('BSC condition policy is too large')
        try: value=json.loads(value)
        except (ValueError,RecursionError) as exc: raise ValueError('invalid BSC condition JSON') from exc
    if not isinstance(value,dict) or set(value)!={'version','description','inputs','expression'}:
        raise ValueError('BSC condition requires version, description, inputs and expression')
    if type(value['version']) is not int or value['version']!=1:
        raise ValueError('unsupported BSC condition version')
    if not isinstance(value['description'],str) or len(value['description'])>2000:
        raise ValueError('BSC condition description must preserve the reviewed text')
    inputs=value['inputs']
    if not isinstance(inputs,dict) or len(inputs)>32: raise ValueError('up to32 BSC condition inputs allowed')
    for alias,source in inputs.items():
        if not isinstance(alias,str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}',alias) or alias in ranking.FUNCTIONS:
            raise ValueError('invalid BSC condition alias')
        if (not isinstance(source,dict) or set(source)!={'source','variable'} or source['source'] not in ('fact','forecast')
                or not isinstance(source['variable'],str) or not 1<=len(source['variable'])<=160):
            raise ValueError('BSC input must explicitly name a fact or forecast variable')
    ranking.compile_expression(value['expression'],set(inputs))
    return json.loads(ranking.canonical(value))


def check_condition(edge, facts, forecasts):
    text=edge.get('condition') or ''
    result={'edge':edge['key'],'description':text,'status':'TRUE','inputs':{}}
    raw=edge.get('conditionPolicy')
    if raw is None and not text: return result
    try:
        if raw is None: raise ValueError('condition text has no reviewed executable interpretation')
        policy=validate_policy(raw)
        if policy['description']!=text: raise ValueError('condition description changed after interpretation')
        for alias,source in policy['inputs'].items():
            value=facts.get(source['variable']) if source['source']=='fact' else (forecasts.get(source['variable']) or {}).get('value')
            result['inputs'][alias]=dict(source,value=value)
        result['status']='TRUE' if ranking.predicate(policy['expression'],{a:v['value'] for a,v in result['inputs'].items()}) else 'FALSE'
    except (ValueError,TypeError,KeyError) as exc:
        result.update(status='UNKNOWN',error=str(exc))
    return result


def fact_variables(rows):
    found=set()
    for row in rows:
        for edge in row.get('edges') or []:
            if edge.get('conditionPolicy') is None: continue
            try: policy=validate_policy(edge['conditionPolicy'])
            except ValueError: continue
            found.update(v['variable'] for v in policy['inputs'].values() if v['source']=='fact')
    return found


def evaluate_paths(rows, facts, forecasts):
    evaluations=[]
    for row in rows:
        path=deepcopy(row)
        if 'owners' in path:
            path['owners']=sorted(path['owners'])
        edges=path.get('edges')
        if edges:
            nodes=path['nodes']
            if len(nodes)!=len(edges)+1 or len(nodes)!=len(set(nodes)):
                raise ValueError('BSC path is cyclic or has inconsistent nodes')
            direction,weight=1,1.0
            checks=[]
            for pos,edge in enumerate(edges):
                if edge['source']!=nodes[pos] or edge['target']!=nodes[pos+1]:
                    raise ValueError('BSC path edge does not match its nodes')
                if edge['type']!=('AFFECTS' if pos==0 else 'INFLUENCES') or type(edge.get('sign')) is not int or edge['sign'] not in (-1,1):
                    raise ValueError('BSC path requires explicit relation kinds and signs')
                direction*=edge['sign']
                if pos:
                    if edge.get('strength') not in STRENGTH: raise ValueError('BSC influence strength is unknown')
                    weight*=STRENGTH[edge['strength']]
                checks.append(check_condition(edge,facts,forecasts))
            if row['direction'] not in ('UP','DOWN'): raise ValueError('BSC measure direction is unknown')
            status='FALSE' if any(c['status']=='FALSE' for c in checks) else 'UNKNOWN' if any(c['status']=='UNKNOWN' for c in checks) else 'TRUE'
            path.update(path_id='|'.join(e['key'] for e in edges),weight=weight,dir=direction,
                        good=(direction==1)==(row['direction']=='UP'),checks=checks,status=status)
        else:
            # Pre-materialized effects cannot manufacture graph evidence.
            weight=ranking.number(row['weight'])
            if weight<0: raise ValueError('BSC weight must be nonnegative')
            path.update(path_id='projection:'+ranking.fingerprint(row),weight=weight,checks=[],
                        status='UNKNOWN' if row.get('conditional') else 'TRUE',projection='materialized_without_path')
        evaluations.append(path)
    evaluations.sort(key=lambda p:p['path_id'])
    groups={}
    for path in evaluations:
        groups.setdefault((path['measure'],path['dir']),[]).append(path)
    effects=[]
    for _,paths in sorted(groups.items()):
        confirmed=max((p['weight'] for p in paths if p['status']=='TRUE'),default=0)
        possible=max((p['weight'] for p in paths if p['status']=='UNKNOWN'),default=0)
        for status,weight in [('TRUE',confirmed),('UNKNOWN',max(0,possible-confirmed))]:
            if weight<=0: continue
            peak=confirmed if status=='TRUE' else possible
            supporting=[p for p in paths if p['status']==status and p['weight']==peak]
            sample=supporting[0]
            owners=sorted({o for p in supporting for o in (p.get('owners') or [p.get('owner')]) if o})
            effects.append({'measure':sample['measure'],'name':sample['name'],'owner':' / '.join(owners) or None,
                'dir':sample['dir'],'good':sample['good'],'weight':round(weight,6),'conditional':status=='UNKNOWN',
                'conditionStatus':status,'conds':sorted({t for p in supporting for t in p.get('conds') or []}),
                'supportingPaths':[p['path_id'] for p in supporting]})
    return effects,evaluations


def consent_paths(paths):
    """Compare definitions and applicability, not sensor drift within a predicate."""
    return [{k:deepcopy(v) for k,v in p.items() if k!='checks'} for p in paths]
