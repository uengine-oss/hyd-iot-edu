"""Path-preserving qualitative BSC effects.

No natural-language condition parsing: an edge that carries a condition sentence (AFFECTS / INFLUENCES `condition`) is
UNKNOWN — the effect stays an identified estimate shown as conditional — and an edge without one holds (TRUE). The graph
has no executable interpretation of a condition sentence (the reviewed-interpretation writer was removed: nothing could
make one), so none is read here.
"""
from copy import deepcopy

from . import ranking

STRENGTH = {'high':1.0,'medium':0.6,'low':0.3}


def check_condition(edge, facts, forecasts):
    text=edge.get('condition') or ''
    result={'edge':edge['key'],'description':text,'status':'TRUE','inputs':{}}
    if text:
        result.update(status='UNKNOWN',error='조건 문장만 있고 판정할 수 있는 해석이 없습니다')
    return result


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
