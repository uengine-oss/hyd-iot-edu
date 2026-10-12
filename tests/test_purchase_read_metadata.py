"""Actual MCP discovery describes the two read sources without changing results."""
import asyncio
import importlib
import sys

from entsim import data


def test_purchase_tool_discovery_explains_source_ranges_and_keeps_legacy_empty_result(monkeypatch):
    monkeypatch.setenv('ENTERPRISE_MCP_TOOLSET','purchasing')
    sys.modules.pop('enterprise_mcp.server',None)
    try:
        server=importlib.import_module('enterprise_mcp.server')
        tools=asyncio.run(server.mcp.get_tools())
        assert set(tools)=={'spare_stock','part_quotes','scm_suppliers'}
        description=tools['scm_suppliers'].description
        assert '원천표의 part_no가 요청 부품과 같은 행만' in description
        assert '목록 0건은' in description and '없다는 뜻이 아닙니다' in description
        assert 'part_quotes로 읽어 대조' in description
        assert '견적 관계와 공급사 원천을 연결' in tools['part_quotes'].description
        # Existing product fixtures: no new supplier/price/approval data.
        legacy=data.scm_suppliers('P-PMP-SEAL')
        quotes=data.part_quotes('P-PMP-SEAL')
        assert legacy['facts']['std_price']==50 and legacy['records']==[]
        assert len(quotes['records'])==3
        assert {r['supplier'] for r in quotes['records'] if r['avl']}=={'sup:a','sup:b'}
        assert {r['id'] for r in data.scm_suppliers('P-CLR-CORE')['records']}=={'sup:a','sup:b','sup:c'}
    finally:
        sys.modules.pop('enterprise_mcp.server',None)
