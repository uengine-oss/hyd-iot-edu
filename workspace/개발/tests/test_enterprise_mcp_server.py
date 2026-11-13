"""업무 MCP 서버(it/enterprise-mcp/enterprise_mcp/server.py) — 도구 묶음 나누기(전체 · 보전 · 구매)와 건강 검사.

묶음은 서버가 켜질 때 환경 변수로 정해지므로 하위 프로세스로 실제로 켜 본다. 건강 검사는 conftest stack 이 띄운 실제 서버 셋.
"""
import json
import os
import subprocess
import sys

import httpx
import pytest

from conftest import HOST_ENV, ROOT

LIST = 'import asyncio, json, enterprise_mcp.server as s; print(json.dumps(sorted(asyncio.run(s.mcp.get_tools()))))'
ALL = sorted(['mes_orders', 'erp_contract', 'erp_inventory', 'cmms_history', 'qms_lots', 'scm_suppliers', 'ems_demand', 'spare_stock',
              'part_quotes', 'maintenance_windows', 'pm_status', 'describe_schema', 'describe_catalog', 'query'])


def tools_of(toolset):
    env = dict(HOST_ENV, PYTHONUTF8='1', ENTERPRISE_MCP_TOOLSET=toolset,
               PYTHONPATH=os.pathsep.join([str(ROOT / 'common'), str(ROOT / 'it' / 'enterprise-mcp')]))
    return subprocess.run([sys.executable, '-c', LIST], capture_output=True, env=env, timeout=120)


@pytest.mark.parametrize('toolset, tools', [
    ('all', ALL),
    ('maintenance', sorted(['pm_status', 'maintenance_windows', 'cmms_history', 'mes_orders'])),
    ('purchasing', sorted(['spare_stock', 'part_quotes', 'scm_suppliers'])),
], ids=['전체', '보전', '구매'])
def test_도구_묶음은_나눈_서버마다_자기_읽기만_두고_자유_SQL은_전체에만_있다(toolset, tools):
    done = tools_of(toolset)
    assert done.returncode == 0, done.stderr.decode('utf8', 'replace')[-800:]
    assert json.loads(done.stdout.decode().splitlines()[-1]) == tools


def test_모르는_도구_묶음이면_서버가_켜지지_않고_까닭을_말한다():
    done = tools_of('everything')
    assert done.returncode != 0 and 'all | maintenance | purchasing' in done.stderr.decode('utf8', 'replace')


@pytest.mark.parametrize('service', ['enterprise-mcp', 'enterprise-mcp-maint', 'enterprise-mcp-purchase'])
def test_건강_검사는_읽기_전용_계정의_읽기_전용_연결인지를_판정한다(stack, service):
    h = httpx.get(stack.services[service].url + '/healthz', timeout=20).json()
    assert h == {'ok': True, 'role': 'hyd_enterprise_reader', 'read_only': True}
