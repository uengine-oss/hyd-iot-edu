import json
import pytest
from enterprise_mcp.catalog import page


def test_catalog_pages_reconstruct_every_column_and_constraint_without_summary_loss():
    tables=[dict(name=f't{i}',kind='r',comment='원문 의미',
                 columns=[{'name':f'c{j}','type':'numeric(18,4)','comment':'정밀도 보존','default':None} for j in range(31)],
                 constraints=[{'name':'pk','definition':'PRIMARY KEY (c0)'}]) for i in range(35)]
    catalog={'catalog':'db','schema':'ent','relations':tables}
    names=[];offset=0
    while offset is not None:
        result=page(catalog,offset=offset)
        assert len(json.dumps(result,ensure_ascii=False))<32000
        names += [r['name'] for r in result['relations']]
        offset=result['next_offset']
    assert names==[t['name'] for t in tables]
    entries=[];offset=0
    while offset is not None:
        result=page(catalog,table='t0',offset=offset)
        entries += result['entries'];offset=result['next_offset']
    assert [r['value'] for r in entries if r['kind']=='column']==tables[0]['columns']
    assert [r['value'] for r in entries if r['kind']=='constraint']==tables[0]['constraints']
    assert len(catalog['relations'][0]['columns'])==31


@pytest.mark.parametrize('kwargs',[{'table':'missing'},{'offset':-1},{'limit':0},{'limit':21}])
def test_catalog_rejects_invalid_page_instead_of_faking_empty_metadata(kwargs):
    with pytest.raises(ValueError):page({'catalog':'db','schema':'ent','relations':[]},**kwargs)


def test_qualified_table_uses_only_the_reader_visible_schema():
    catalog={'catalog':'db','schema':'ent','relations':[
        {'name':'work_orders','kind':'r','comment':None,'columns':[{'name':'id'}],'constraints':[]}]}
    assert page(catalog,'ent.work_orders')==page(catalog,'work_orders')
    with pytest.raises(ValueError):page(catalog,'other.work_orders')


def test_actual_mcp_schema_enforces_page_bounds():
    import asyncio
    from fastmcp import Client
    from enterprise_mcp.server import mcp
    async def check():
        async with Client(mcp) as client:
            meta=next(t for t in await client.list_tools() if t.name=='describe_catalog')
            assert meta.inputSchema['properties']['limit']['maximum']==20
            assert meta.inputSchema['properties']['offset']['minimum']==0
            with pytest.raises(Exception):await client.call_tool('describe_catalog',{'limit':30})
    asyncio.run(check())
