"""공장 규모 자료(실전반 2회차)가 설계 랩 제공 코드(session2_model_tool.py)에 더하는 것 — 통합반 원본은 한 글자도 바꾸지 않고, 그 원본 글에 아래 조각을 덧대 실전반 판을 만든다.

덧대는 것은 실습 랩 규모에는 없고 공장 규모 자료에만 있는 사실을 받는 일반 로직뿐이다(코딩랩 K-3 · K-10 — 같은 생성기에서 자료 범위만 연 판).
1. 설비에 바로 붙는 센서(붙은곳 「설비 전체」) — 설비와 센서를 잇는 관계를 관계 표에 적으면 그리로 잇고, 적지 않았으면 그 줄을 짚고 멈춘다.
2. 수 칸에 그 행의 단위가 붙어 적힌 값(「130 bar」) — 붙은 글이 그 행의 단위 칸과 같을 때만 수로 읽는다.
3. 교체부품 칸이 품명만 적힌 줄 — 예비품 목록의 품명과 글자까지 같은 것이 하나일 때만 잇는다(견적표의 품번 칸도 같은 법으로 읽는다).
4. 공급 자료(견적 · 승인 등록) — 공급사 · 견적 클래스를 클래스 표에 적었을 때만 읽는다: 공급사 이름의 괄호 풀이 떼기, 품번 칸 찾기, 「%」 · 「주」 바꾸기,
   기준일의 승인 상태 찾기(구매 기준서 7.3 — 승인 여부는 SCM 등록을 따른다), 값마다 출처 줄 남기기, 구매팀 질문(질문 5)에 답하기.
원본의 그 자리가 바뀌면 조용히 지나가지 않고 멈춘다(자리를 하나로 찾지 못함).
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPLY_POINT = '같은 공급사 · 같은 부품의 견적 두 줄'      # 실전반 설계 랩의 셋째 결정 지점(정한_것.csv 지점 줄)

PATCHES = [
    # ── 클래스 · 관계의 범위
    ("OPTIONAL_KINDS = ['실물']      # 자리(구성 요소)와 일련번호가 붙은 실물을 나눌 때만 결과/클래스.csv에 적는다\n"
     "LABEL = {'설비': 'Asset', '구성 요소': 'Component', '센서': 'Sensor', '물리량': 'Quantity', '부품': 'Part', '실물': 'Unit'}\n",
     "OPTIONAL_KINDS = ['실물', '공급사', '견적']      # 실물 = 자리(구성 요소)와 일련번호가 붙은 실물을 나눌 때만, 공급사 · 견적 = 공급 조건을 모델에 담을 때만 결과/클래스.csv에 적는다\n"
     "LABEL = {'설비': 'Asset', '구성 요소': 'Component', '센서': 'Sensor', '물리량': 'Quantity', '부품': 'Part', '실물': 'Unit', '공급사': 'Supplier', '견적': 'Quote'}\n"
     "ASSET_WIDE = '설비 전체'      # 센서 목록 붙은곳 칸의 이 글 = 구성 요소 하나가 아니라 설비에 붙는 센서\n"
     "AS_OF = '2026-10-15'          # 자료 기준일(현장 메모 첫머리)\n"
     "QUOTES, AVL = '공급_조건.csv', '승인공급사_목록.csv'\n"),
    ("TABLE = {'설비': '설비_대장.csv', '구성 요소': '구성요소_목록.csv', '센서': '센서_목록.csv', '부품': '예비품_목록.csv', '실물': '구성요소_목록.csv'}\n",
     "TABLE = {'설비': '설비_대장.csv', '구성 요소': '구성요소_목록.csv', '센서': '센서_목록.csv', '부품': '예비품_목록.csv', '실물': '구성요소_목록.csv', '견적': QUOTES}\n"),
    ("           '물리량': {'물리량': '내 규칙이 묶음에 붙인 이름', '기준단위': '그 묶음의 센서 행이 가장 많이 쓴 단위'}}\n",
     "           '물리량': {'물리량': '내 규칙이 묶음에 붙인 이름', '기준단위': '그 묶음의 센서 행이 가장 많이 쓴 단위'},\n"
     "           '공급사': {'공급사': '견적표 공급사 칸에서 괄호 풀이를 뗀 이름(승인 공급사 목록에 적힌 이름)'},\n"
     "           '견적': {'승인상태': '승인 공급사 목록에서 그 공급사 · 부품의 기준일 승인 상태(등록의 유효기한이 지났으면 「유효기한 경과」, 등록이 없으면 「미등록」)',\n"
     "                    '승인조건': '그 등록의 조건 칸', '견적출처': '이 견적의 원자료 줄(파일:줄)', '승인출처': '그 승인 등록의 원자료 줄(파일:줄)'}}\n"),
    ("         '구성 요소-부품': ('구성 요소', '부품'), '구성 요소-실물': ('구성 요소', '실물')}\n"
     "OPTIONAL_LINKS = ('구성 요소-실물',)   # 구성 요소 자리와 그 실물을 나눌 때만 적는 관계\n",
     "         '구성 요소-부품': ('구성 요소', '부품'), '구성 요소-실물': ('구성 요소', '실물'),\n"
     "         '설비-센서': ('설비', '센서'), '공급사-견적': ('공급사', '견적'), '견적-부품': ('견적', '부품')}\n"
     "OPTIONAL_LINKS = ('구성 요소-실물', '설비-센서', '공급사-견적', '견적-부품')   # 실물을 나눌 때 · 설비에 바로 붙는 센서를 담을 때 · 공급 조건을 담을 때만 적는 관계\n"),
    ("DECISIONS = {'이름': ['구성 요소 자리와 그 실물'], '센서': ['같은 물리량의 범위'], '부품': ['구성 요소 자리와 그 실물', '같은 물리량의 범위']}\n",
     "DECISIONS = {'이름': ['구성 요소 자리와 그 실물'], '센서': ['같은 물리량의 범위'], '부품': ['구성 요소 자리와 그 실물', '같은 물리량의 범위'],\n"
     "             '공급': [" + repr(SUPPLY_POINT) + "]}\n"),
    # ── 품명만 적힌 칸
    ("    if cell and len(hits) == 1 and hits[0] in parts:\n"
     "        return hits[0], f'품번 교차표({next(c[\"표기종류\"] for c in cross if c[\"다른표기\"] == cell)})'\n"
     "    return None, ''\n",
     "    if cell and len(hits) == 1 and hits[0] in parts:\n"
     "        return hits[0], f'품번 교차표({next(c[\"표기종류\"] for c in cross if c[\"다른표기\"] == cell)})'\n"
     "    named = [p for p, name in PART_NAMES.items() if name == cell and p in parts]      # 품명만 적힌 칸 — 예비품 목록의 품명과 글자까지 같은 것이 하나일 때만\n"
     "    if cell and len(named) == 1:\n"
     "        return named[0], '품명(예비품 목록)'\n"
     "    return None, ''\n"
     "\n\n"
     "PART_NAMES = {}      # {사내 품번: 품명} — raw()가 예비품 목록을 읽을 때 채운다\n"),
    ("def raw():\n"
     "    return {n: table(DATA / n) for n in ['설비_대장.csv', '구성요소_목록.csv', '센서_목록.csv', '예비품_목록.csv', '품번_교차표.csv']}\n",
     "def raw():\n"
     "    src = {n: table(DATA / n) for n in ['설비_대장.csv', '구성요소_목록.csv', '센서_목록.csv', '예비품_목록.csv', '품번_교차표.csv']}\n"
     "    PART_NAMES.clear()\n"
     "    PART_NAMES.update({r['품번']: r['품명'] for _, r in src['예비품_목록.csv']})\n"
     "    return src\n"),
    # ── 단위가 붙어 적힌 수
    ("def typed(value, kind):\n"
     "    \"\"\"원자료 글자 → (자료형에 맞춘 값, 맞는가). 수 = 숫자만, 날짜 = YYYY-MM-DD.\"\"\"\n"
     "    if kind == '수':\n"
     "        ok = bool(re.fullmatch(r'-?\\d+(?:\\.\\d+)?', value))\n",
     "def typed(value, kind, unit=''):\n"
     "    \"\"\"원자료 글자 → (자료형에 맞춘 값, 맞는가). 수 = 숫자만(그 행의 단위 칸과 같은 글이 뒤에 붙은 값은 그 수로 읽는다 — 「130 bar」), 날짜 = YYYY-MM-DD.\"\"\"\n"
     "    if kind == '수':\n"
     "        if unit and value.endswith(unit) and re.fullmatch(r'-?\\d+(?:\\.\\d+)?', value[:-len(unit)].strip()):\n"
     "            value = value[:-len(unit)].strip()\n"
     "        ok = bool(re.fullmatch(r'-?\\d+(?:\\.\\d+)?', value))\n"),
    ("                one['안맞음'] = [(line, r[p['칸']]) for line, r in data if r[p['칸']] and not typed(r[p['칸']], p['자료형'])[1]]\n",
     "                one['안맞음'] = [(line, r[p['칸']]) for line, r in data if r[p['칸']] and not typed(r[p['칸']], p['자료형'], r.get('단위', ''))[1]]\n"),
    ("                v, ok = typed(v, p['자료형'])\n",
     "                v, ok = typed(v, p['자료형'], values.get('적힌단위', ''))\n"),
    ("                            수=sum(1 for _, r in data if r[col] and typed(r[col], '수')[1]),\n",
     "                            수=sum(1 for _, r in data if r[col] and typed(r[col], '수', r.get('단위', ''))[1]),\n"),
    ("        node('센서', sid, f'자료/센서_목록.csv:{line}', {**r, '단위': out_unit}, factor)\n"
     "        rel_('구성 요소-센서', comps[(code, place_of(line, r)[0])][0], sid, f'센서_목록.csv:{line}')\n",
     "        node('센서', sid, f'자료/센서_목록.csv:{line}', {**r, '단위': out_unit, '적힌단위': unit_}, factor)\n"
     "        if r['붙은곳'] == ASSET_WIDE:      # 설비에 바로 붙는 센서\n"
     "            rel_('설비-센서', assets[code], sid, f'센서_목록.csv:{line}')\n"
     "        else:\n"
     "            rel_('구성 요소-센서', comps[(code, place_of(line, r)[0])][0], sid, f'센서_목록.csv:{line}')\n"),
    # ── 설비에 바로 붙는 센서
    ("    def place_of(line, r):\n"
     "        cname = name_of(named, r['붙은곳'], model_of[r['설비코드']])\n",
     "    def place_of(line, r):\n"
     "        if r['붙은곳'] == ASSET_WIDE:\n"
     "            if '설비-센서' not in links:\n"
     "                raise Stop(f'자료/센서_목록.csv:{line}: 붙은곳 「{ASSET_WIDE}」 — 이 센서는 구성 요소 하나가 아니라 설비에 붙습니다. 결과/관계.csv에 설비와 센서를 잇는 관계 줄을 더하거나, '\n"
     "                           '이 행을 모델에 담지 않으려면 결과/행_처리.csv에 「빼기」로 적습니다.')\n"
     "            return ASSET_WIDE, ''\n"
     "        cname = name_of(named, r['붙은곳'], model_of[r['설비코드']])\n"),
    ("    if unit:\n"
     "        out['구성 요소-실물'] = (f\"{unit['설비코드']} {unit['구성요소']}\", unit['일련번호'])\n"
     "    return out\n",
     "    if unit:\n"
     "        out['구성 요소-실물'] = (f\"{unit['설비코드']} {unit['구성요소']}\", unit['일련번호'])\n"
     "    wide = next((r for _, r in src['센서_목록.csv'] if r['붙은곳'] == ASSET_WIDE), None)\n"
     "    if wide:\n"
     "        out['설비-센서'] = (wide['설비코드'], f\"{wide['센서명']}({wide['태그']})\")\n"
     "    if (DATA / QUOTES).is_file():\n"
     "        q = table(DATA / QUOTES)[0][1]\n"
     "        out['공급사-견적'] = (supplier_name(q['공급사']), f\"{q['품번']} 견적({q['견적일']})\")\n"
     "        out['견적-부품'] = (f\"{supplier_name(q['공급사'])} 견적({q['견적일']})\", q['품번'])\n"
     "    return out\n"),
    # ── 행 처리: 견적 줄도 받는다
    ("        if r['파일'] not in ('설비_대장.csv', '구성요소_목록.csv', '센서_목록.csv'):\n"
     "            raise Stop(f'결과/행_처리.csv:{line}: 파일 「{r[\"파일\"]}」 — 설비_대장.csv · 구성요소_목록.csv · 센서_목록.csv 가운데 하나입니다.')\n",
     "        if r['파일'] not in ('설비_대장.csv', '구성요소_목록.csv', '센서_목록.csv', QUOTES):\n"
     "            raise Stop(f'결과/행_처리.csv:{line}: 파일 「{r[\"파일\"]}」 — 설비_대장.csv · 구성요소_목록.csv · 센서_목록.csv · {QUOTES} 가운데 하나입니다.')\n"),
    # ── 클래스 표: 공급사 · 견적은 함께, 관계 표와 함께
    ("    if ('실물' in classes) != ('구성 요소-실물' in links):\n",
     "    supply = [('공급사' in classes), ('견적' in classes), ('공급사-견적' in links), ('견적-부품' in links)]\n"
     "    if any(supply) and not all(supply):\n"
     "        raise Stop('결과/클래스.csv · 결과/관계.csv: 공급 조건을 담으려면 클래스.csv에 「공급사」 · 「견적」 줄과, 관계.csv에 공급사와 견적 · 견적과 부품을 잇는 줄 둘을 함께 적습니다(지금은 일부만 있습니다).')\n"
     "    if ('실물' in classes) != ('구성 요소-실물' in links):\n"),
    # ── 모델 만들기: 부품 뒤에 공급
    ("    info['카디널리티'] = check_cardinality(links, rels, where_of)\n"
     "    for link, (name, start, end, _, line, least, _) in links.items():      # 「적어도 하나」로 정한 쪽에서 이 관계가 하나도 없는 대상\n",
     "    info['공급'] = supply(classes, ids, parts, part_id, handled, node, rel_) if '견적' in classes else None\n"
     "    info['카디널리티'] = check_cardinality(links, rels, where_of)\n"
     "    for link, (name, start, end, _, line, least, _) in links.items():      # 「적어도 하나」로 정한 쪽에서 이 관계가 하나도 없는 대상\n"),
    ("def make_model(classes, props, links, nodes, rels):\n",
     "def supplier_name(text):\n"
     "    \"\"\"견적표 공급사 칸의 괄호 앞 이름(「B-OEM (순정)」 · 「B-OEM(순정)」 → 「B-OEM」).\"\"\"\n"
     "    return re.split(r'\\s*\\(', text, 1)[0].strip()\n"
     "\n\n"
     "def quote_rows():\n"
     "    \"\"\"견적표 줄마다 읽은 값(일반 로직) → [(줄, 원자료 행, 읽은 값 dict, 바꾼 것 [(칸, 원래 글, 읽은 값)])]. 공급사 = 괄호 풀이를 뗀 이름, 품번 = 사내 품번(품명으로 적힌 칸은 예비품 목록의 같은 품명 하나),\n"
     "    불량률 = 0~1 비율(「8%」 → 0.08), 납기(일) = 일(「2주」 → 14), 승인상태 · 승인조건 · 승인출처 = 승인 공급사 목록의 그 공급사 · 부품 등록(기준일에 유효기한이 지났으면 「유효기한 경과」, 없으면 「미등록」).\"\"\"\n"
     "    raw()\n"
     "    avl = {(r['공급사'], r['품번']): (line, r) for line, r in table(DATA / AVL)}\n"
     "    out = []\n"
     "    for line, r in table(DATA / QUOTES):\n"
     "        where, changed = f'자료/{QUOTES}:{line}', []\n"
     "        v = dict(r)\n"
     "        v['공급사'] = supplier_name(r['공급사'])\n"
     "        if v['공급사'] != r['공급사']:\n"
     "            changed.append(('공급사', r['공급사'], v['공급사']))\n"
     "        if r['품번'] not in PART_NAMES:\n"
     "            hits = [p for p, name in PART_NAMES.items() if name == r['품번']]\n"
     "            if len(hits) != 1:\n"
     "                raise Stop(f'{where}: 품번 칸 「{r[\"품번\"]}」을 사내 품번으로 찾지 못했습니다(예비품 목록에서 품명이 같은 것 {len(hits)}개).')\n"
     "            v['품번'] = hits[0]\n"
     "            changed.append(('품번', r['품번'], hits[0]))\n"
     "        for col, tail, times in (('불량률', '%', 0.01), ('납기(일)', '주', 7)):\n"
     "            t = r[col]\n"
     "            if t.endswith(tail) and number(t[:-1]) is not None:\n"
     "                v[col] = '%g' % round(number(t[:-1]) * times, 6)\n"
     "                changed.append((col, t, v[col]))\n"
     "        entry = avl.get((v['공급사'], v['품번']))\n"
     "        if entry is None:\n"
     "            v.update(승인상태='미등록', 승인조건='', 승인출처='')\n"
     "        else:\n"
     "            aline, a = entry\n"
     "            v.update(승인상태='유효기한 경과' if a['유효기한'] and a['유효기한'] < AS_OF else a['승인상태'], 승인조건=a['조건'], 승인출처=f'자료/{AVL}:{aline}')\n"
     "        v['견적출처'] = where\n"
     "        out.append((line, r, v, changed))\n"
     "    return out\n"
     "\n\n"
     "def supply(classes, ids, parts, part_id, handled, node, rel_):\n"
     "    \"\"\"공급사 · 견적 인스턴스와 그 관계를 만든다. 견적 식별자가 겹치는 줄은 node가 그 줄을 짚고 멈춘다 — 어느 줄을 담을지는 결과/행_처리.csv와 식별자 틀이 정한다.\n"
     "    돌려주는 것: 화면용 {'줄': [(줄, 공급사, 사내 품번, 견적일, 유효기한, 승인상태, 담음)], '바꾼_값': [...], '겹침': {(공급사, 품번): [줄]}}.\"\"\"\n"
     "    decided('공급')\n"
     "    rows = quote_rows()\n"
     "    pairs = {}\n"
     "    for line, _, v, _ in rows:\n"
     "        pairs.setdefault((v['공급사'], v['품번']), []).append(line)\n"
     "    suppliers, shown = {}, []\n"
     "    for line, _, v, _ in rows:\n"
     "        kept = not handled(QUOTES, line)\n"
     "        shown.append((f'{QUOTES}:{line}', v['공급사'], v['품번'], v['견적일'], v['유효기한'], v['승인상태'], '담음' if kept else '뺌'))\n"
     "        if not kept:\n"
     "            continue\n"
     "        where = f'자료/{QUOTES}:{line}'\n"
     "        if v['공급사'] not in suppliers:\n"
     "            suppliers[v['공급사']] = make_id(ids['공급사'], '공급사', {'공급사': v['공급사']}, where)\n"
     "            node('공급사', suppliers[v['공급사']], where, {'공급사': v['공급사']})\n"
     "        qid = make_id(ids['견적'], '견적', v, where)\n"
     "        node('견적', qid, where, {**v, '적힌단위': ''})\n"
     "        rel_('공급사-견적', suppliers[v['공급사']], qid, f'{QUOTES}:{line}')\n"
     "        rel_('견적-부품', qid, part_id[v['품번']], f'{QUOTES}:{line}')\n"
     "    return {'줄': shown, '바꾼_값': [(f'{QUOTES}:{line}', col, old, new) for line, _, _, changed in rows for col, old, new in changed],\n"
     "            '겹침': {k: v for k, v in pairs.items() if len(v) > 1}}\n"
     "\n\n"
     "def make_model(classes, props, links, nodes, rels):\n"),
    # ── 식별자 미리보기 · 속성 대어 보기: 견적은 읽은 값으로, 공급사는 그 이름으로
    ("def instances(kind, src):\n"
     "    \"\"\"그 클래스의 인스턴스가 나오는 원자료 행(실물은 일련번호가 적힌 구성 요소 행).\"\"\"\n"
     "    return [(line, r) for line, r in src[TABLE[kind]] if not (kind == '실물' and not r['일련번호'])]\n",
     "def instances(kind, src):\n"
     "    \"\"\"그 클래스의 인스턴스가 나오는 원자료 행(실물은 일련번호가 적힌 구성 요소 행, 견적은 견적표 줄을 읽은 값).\"\"\"\n"
     "    if kind == '견적':\n"
     "        return [(line, v) for line, _, v, _ in quote_rows()]\n"
     "    return [(line, r) for line, r in src[TABLE[kind]] if not (kind == '실물' and not r['일련번호'])]\n"),
    # ── 물어보기: 설비에 바로 붙는 센서, 구매팀 질문
    ("                if serials:\n"
     "                    row(props[c].get(cname, c) + ' 실물', serials, 다른_이름=[x + ' 실물' for x in other])\n",
     "                if serials:\n"
     "                    row(props[c].get(cname, c) + ' 실물', serials, 다른_이름=[x + ' 실물' for x in other])\n"
     "            wide = sorted(props[s].get(tag, '?') for s in ends(hit[0], '설비-센서'))\n"
     "            if wide:      # 구성 요소 하나가 아니라 설비에 붙은 센서\n"
     "                row(ASSET_WIDE, ' · '.join(wide))\n"),
    ("                asset = next((a for c in starts(s, '구성 요소-센서') for a in starts(c, '설비-구성 요소')), None)\n",
     "                asset = next((a for c in starts(s, '구성 요소-센서') for a in starts(c, '설비-구성 요소')), None) or next(iter(starts(s, '설비-센서')), None)\n"),
    ("        else:\n"
     "            raise Stop(f'결과/기대_답.csv: 질문 「{q}」 — 질문은 1 · 2 · 3과 내가 더한 4입니다.')\n",
     "        elif q == '5':\n"
     "            for one in purchase(value, key, lack, of, props, starts, ends):\n"
     "                row(*one[:2], **one[2])\n"
     "        else:\n"
     "            raise Stop(f'결과/기대_답.csv: 질문 「{q}」 — 질문은 1 · 2 · 3과 내가 더한 4, 구매팀이 묻는 5입니다.')\n"),
    ("def filtered(schema, graph, asked, item, where='결과/기대_답.csv'):\n",
     "def purchase(value, key, lack, of, props, starts, ends):\n"
     "    \"\"\"질문 5(구매팀) — 품번이나 표기 → 그 부품을 쓰는 설비(항목 = 찾은 사내 품번)와, 기준일에 유효기한이 남은 견적을 공급사마다(항목 = 사내 품번/공급사 이름,\n"
     "    답 = 「승인상태 · 단가(만원) · 불량률 · 납기(일)」 — 한 공급사에 견적이 여럿이면 견적일 차례로 「 / 」로 잇는다). 돌려주는 것: [(항목, 답, {'출처': ...})].\"\"\"\n"
     "    no, other, code = key('부품', '품번'), key('부품', '다른표기'), key('설비', '설비코드')\n"
     "    miss = next((lack(k, c) for k, c, p in (('부품', '품번', no), ('설비', '설비코드', code)) if p is None), None)\n"
     "    if miss:\n"
     "        return [('', miss, {})]\n"
     "    ids = sorted(i for i in of('부품') if props[i].get(no) == value or value in props[i].get(other or '', []))\n"
     "    if not ids:\n"
     "        return [('', '없음', {})]\n"
     "    if not of('견적'):\n"
     "        return [('', '답할 수 없음(모델에 견적 클래스가 없음 — 공급 조건을 아직 담지 않음)', {})]\n"
     "    cols = {c: key('견적', c) for c in ('유효기한', '승인상태', '단가(만원)', '불량률', '납기(일)', '견적일', '견적출처', '승인출처')}\n"
     "    sname = key('공급사', '공급사')\n"
     "    out = []\n"
     "    for pid in ids:\n"
     "        assets = sorted({props[a].get(code, a) for c in starts(pid, '구성 요소-부품') for a in starts(c, '설비-구성 요소')})\n"
     "        pno = props[pid].get(no, pid)\n"
     "        out.append((pno, ' · '.join(assets) or '쓰는 설비 없음', {}))\n"
     "        need_ = [c for c in ('유효기한', '승인상태', '단가(만원)', '불량률', '납기(일)') if cols[c] is None]\n"
     "        if need_ or sname is None:\n"
     "            out.append((pno + '/', lack('견적', need_[0]) if need_ else lack('공급사', '공급사'), {}))\n"
     "            continue\n"
     "        per = {}\n"
     "        for q in starts(pid, '견적-부품'):\n"
     "            p = props[q]\n"
     "            if str(p.get(cols['유효기한'], '')) < AS_OF:      # 기준일에 유효기한이 지난 견적\n"
     "                continue\n"
     "            show = lambda c: '없음' if p.get(cols[c]) in (None, '') else ('%g' % p[cols[c]] if isinstance(p[cols[c]], (int, float)) else str(p[cols[c]]))\n"
     "            for s in starts(q, '공급사-견적'):\n"
     "                per.setdefault(props[s].get(sname, s), []).append((str(p.get(cols['견적일'] or '', '')), ' · '.join(show(c) for c in ('승인상태', '단가(만원)', '불량률', '납기(일)')),\n"
     "                                                                 ' · '.join(str(p[cols[c]]) for c in ('견적출처', '승인출처') if cols[c] and p.get(cols[c]))))\n"
     "        if not per:\n"
     "            out.append((pno + '/', '기준일에 유효한 견적 없음', {}))\n"
     "        for sup, quotes in sorted(per.items()):\n"
     "            quotes.sort()\n"
     "            out.append((f'{pno}/{sup}', ' / '.join(x[1] for x in quotes), {'출처': ' / '.join(x[2] for x in quotes if x[2])}))\n"
     "    return out\n"
     "\n\n"
     "def filtered(schema, graph, asked, item, where='결과/기대_답.csv'):\n"),
]


def tool_source():
    """공장 규모 판 제공 코드의 글(옛 이름 그대로 — 새 구조 이름으로 바꾸는 일은 session2_project.convert가 한다)."""
    text = (HERE / 'session2_model_tool.py').read_text(encoding='utf-8')
    for old, new in PATCHES:
        if text.count(old) != 1:
            raise ValueError('session2_model_tool.py의 그 자리가 바뀌었습니다 — 공장 규모 덧댐을 다시 봅니다: ' + old[:70])
        text = text.replace(old, new)
    return text


def tool_module(root=None):
    """공장 규모 판 제공 코드를 모듈로 불러온다(강사 참조 계산용). root를 주면 그 폴더의 자료/ · 결과/를 읽는다."""
    import importlib.util
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'factory_model_tool.py'
        path.write_text(tool_source(), encoding='utf-8', newline='\n')
        spec = importlib.util.spec_from_file_location('factory_model_tool', path)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
    if root is not None:
        tool.HERE, tool.DATA, tool.OUT = Path(root), Path(root) / '자료', Path(root) / '결과'
    return tool
