"""The two existing DMN proposal-registration operations, never physical effects."""
from . import mcp_check

TOOLS=frozenset({'hyd-dmn/submit_decision','hyd-dmn/submit_purchase'})


def call(spec,qualified,arguments):
    if qualified not in TOOLS:
        raise ValueError('승인 전 저장할 수 있는 도구는 DMN 제안 등록뿐입니다')
    tool=qualified.split('/')[1]
    def work(session):
        meta=next((t for t in mcp_check._list_tools(session) if t['name']==tool),None)
        if not meta:
            return {'status':'refused','result':None}
        invalid=mcp_check._argument_problem(meta,arguments)
        if invalid:return invalid
        response=session.request('tools/call',{'name':tool,'arguments':arguments})
        return {'status':'ok','result':mcp_check.shape_result(response,32000)}
    result=mcp_check._with_session(spec,25,work)
    result.setdefault('result',None)
    return result
