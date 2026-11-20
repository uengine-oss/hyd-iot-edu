# 새 판 MAP 초안 — build_ontology.py의 MAP 자리에 바꿔 끼운다(도구 작업자가 MAP 문법을 고친 뒤). 대본원고_새판.md의 ▸ 차례와 같다.
# 짚기 P(대상)의 강조 모양은 대상 종류의 기본값(원 = 동그라미, 그림판 글자 · 증거 줄 = 밑줄, 칸 · 단추 = 테두리, 글상자 줄 = 띠, 화살표 끝 · 넓은 자리 = 없음)을 쓴다.
# 같은 대상을 짚었다가 떠났다 다시 짚는 차례(커서 되돌아옴)를 두지 않는다.
MAP = {
 # 1구간
 'g004': [A([['click', 'sel:#sb_form_q'], ['type', 'arrows.app'], ['key', 'Enter'], ['reinstall']])],
 'g005': [A([['openLink', 'result:arrows.app']])],
 'g006': [T(ck('text:Use necessary cookies only')), A(ck('done'))],
 'g007': [P('canvasMid'), P('panelMid'), L('')],
 'g008': [A(ck('customize'))],
 'g009': [P('style:radius'), T([['click', 'style:radius'], ['key', 'ControlOrMeta+A'], ['type', '60'], ['key', 'Tab']])],
 'g010': [T([['panelScroll', 'styleSel:detail-orientation']]), P('styleSel:detail-orientation'),
          A([['click', 'styleSel:detail-orientation'], ['click', 'styleOpt:detail-orientation=horizontal'], ['panelScroll']])],
 'g011': [T([['drag', '', FIRST_X, None]])],
 # 2구간
 'g012': [A(ck('node:'))], 'g013': [P('caption'), A(cap(H))],
 'g015': [P('labelPlus'), A(ck('labelPlus'))],
 'g016': [T([['click', 'labelInput'], ['type', 'Asset'], ['key', 'Tab']])], 'g017': [P('ctext:Asset')],
 'g019': [T(ck('node:' + H)), P('inner:' + H), P('ring:' + H), A(gt(H, K, click=False))],
 'g020': [A(nn(K))], 'g021': [EF(H, K), ET(H, K)], 'g022': [L(H), L(K)],
 'g023': [T([['edge', H, K]]), P('type'), A(ty('HAS_COMPONENT'))],
 'g024': [P('ctext:HAS_COMPONENT')],
 'g025': [EF(H, K), ET(H, K)],
 'g027': [L(K), P('ctext:HAS_COMPONENT')],
 'g028': [L(K)], 'g029': [A(gt(K, S))], 'g030': [T(nn(S))],
 'g031': [L(K), L(S)], 'g032': [EF(K, S), T([['edge', K, S]]), A(ty('MONITORED_BY'))],
 'g033': [L(K), L(S)],
 # 3구간
 'g034': [A(gt(S, U))], 'g035': [T(cap(U)), A(lab(U))], 'g036': [L(U), L(S)],
 'g038': [L(U), EF(S, U)],
 'g039': [T([['edge', S, U]]), P('reverse'), A(ck('reverse'))], 'g040': [A(ty('OBSERVED_BY'))], 'g041': [L(U), L(S)],
 'g042': [L(K)], 'g043': [A(gt(U, F))], 'g044': [T(cap(F)), A(lab(F))],
 'g045': [L(U), L(F), A(et(U, F, 'INDICATES'))], 'g046': [L(K), A(con(F, K))], 'g047': [L(F), L(K), A(et(F, K, 'OCCURS_IN'))],
 'g048': [L(U), L(S), L(F), L(K)],
 # 4구간
 'g049': [L(K)], 'g050': [A(gt(F, PO))], 'g051': [A(nn(PO))], 'g052': [L(PO), L(F), EF(F, PO)], 'g053': [A(et(F, PO, 'CAUSES', rev=True))],
 'g054': [L(PO), L(F)], 'g056': [T(ck('node:' + PO)), P('propPlus'), A(ck('propPlus'))],
 'g057': [P('propKey'), P('propVal'), A([['click', 'propKey'], ['type', '냉각 효율']])],
 'g058': [T([['click', 'propVal'], ['type', '30초 평균 < 70 %']]), T([['key', 'Tab']])], 'g059': [P('props:' + PO)],
 'g060': [T(ck('propPlus')), A(pv('팬 진동', '2분 평균 < 0.9 mm/s'))], 'g061': [P('props:' + PO + '#2'), P('props:' + PO)],
 # 5구간
 'g063': [A(gt(F, MX))], 'g064': [T(nn(MX))], 'g065': [L(F), L(MX)], 'g066': [A(et(F, MX, 'MITIGATED_BY'))], 'g067': [A(gt(F, PC))], 'g068': [A(nn(PC))],
 'g069': [L(F), L(PC), A(et(F, PC, 'REMEDIED_BY'))], 'g070': [P('ctext:MITIGATED_BY'), P('ctext:REMEDIED_BY')],
 'g071': [A(con(PC, PO))], 'g072': [L(PC), L(PO), A(et(PC, PO, 'ADDRESSES'))], 'g074': [A(gt(MX, M85))], 'g075': [T(cap(M85)), A(lab(M85))],
 'g076': [L(MX), L(M85), A(et(MX, M85, 'REFERS_TO'))], 'g077': [T(gt(PC, M87)), A(nn(M87))], 'g078': [A(et(PC, M87, 'REFERS_TO'))],
 'g079': [L(PO), L(PC), L(M87)],
 # 6구간
 'g081': [A(gt(F, FD))], 'g082': [T(cap(FD)), A(lab(FD))], 'g083': [A(et(F, FD, 'CAUSES', rev=True))],
 'g084': [A([['click', 'node:' + FD], ['click', 'propPlus']], pv('팬 진동', '2분 평균 ≥ 0.9 mm/s'))], 'g085': [P('props:' + PO + '#2'), P('props:' + FD)],
 'g086': [A(gt(F, FI))], 'g087': [T(nn(FI)), A(et(F, FI, 'REMEDIED_BY'))], 'g088': [A(con(FI, FD), et(FI, FD, 'ADDRESSES'))],
 'g089': [A(gt(FI, M81), nn(M81))], 'g090': [A(et(FI, M81, 'REFERS_TO'))],
 # 7구간
 'g092': [A(gt(F, AT))], 'g093': [T(nn(AT)), A(et(F, AT, 'CAUSES', rev=True))],
 'g094': [A([['click', 'node:' + AT], ['click', 'propPlus']], pv('캐비닛 온도', '2분 평균 ≥ 35 ℃'))], 'g095': [A(gt(AT, CV))], 'g096': [A(nn(CV))],
 'g097': [L(CV), L(AT), EF(AT, CV), A(et(AT, CV, 'ADDRESSES', rev=True))], 'g098': [A(con(F, CV), et(F, CV, 'REMEDIED_BY'))],
 'g099': [A(con(CV, M87), et(CV, M87, 'REFERS_TO'))], 'g100': [L(PC), L(M87), L(CV)],
 'g101': [L(PO), L(PC), L(FD), L(FI), L(AT), L(CV)],
 # 8구간
 'g103': [L(FD), A(gt(F, BR))], 'g104': [A(nn(BR))], 'g105': [L(BR), L(F)], 'g106': [A(et(F, BR, 'LEADS_TO', rev=True))],
 'g107': [P('props:' + FD), A(gt(BR, VB))], 'g108': [T(nn(VB)), A(et(BR, VB, 'INDICATES', rev=True))], 'g109': [L(VB), L(BR), L(F)],
 'g111': [L(PC), L(M87), L(CV)], 'g112': [A([['edge', FI, M81]])], 'g113': [T(ck('propPlus')), A(pv('절차', 'SOP-FAN-11'))],
 'g114': [A(sop(CV, M87, 'SOP-COOL-15'))], 'g115': [A(sop(PC, M87, 'SOP-COOL-14'))], 'g116': [A(sop(MX, M85, 'SOP-COOL-11'))],
 'g117': [P('ctext:SOP-COOL-14'), P('ctext:SOP-COOL-15')],
 # 9구간 — 색칠
 'g118': [T(ck('node:' + PO)), T([['ctrlclick', 'node:' + FD]]), T([['ctrlclick', 'node:' + AT]])],
 'g119': [P('selCount'), P('style:node-color'), A(color(RED))],
 'g120': [T(ck('node:' + MX)), T([['ctrlclick', 'node:' + PC]]), T([['ctrlclick', 'node:' + CV]]), T([['ctrlclick', 'node:' + FI]]), A(color(GREEN))],
 # 10구간 — 그림으로 판단하기
 'g121': [T(ck('blank')), L(U), L(F), L(PO), L(FD), L(AT)], 'g122': [N(CASE), P('noteLine:1'), P('noteLine:2'), P('noteLine:3')],
 'g123': [P('props:' + PO + '#1'), P('props:' + PO + '#2')], 'g124': [P('props:' + FD), P('props:' + AT), L(PO)],
 'g125': [OFF, L(PO), L(PC), P('ctext:SOP-COOL-14'), L(M87), L(MX)], 'g126': [N(CASE14), P('props:' + FD), L(FI), P('ctext:SOP-FAN-11'), L(M81)],
 'g127': [L(VB), L(BR), L(MX)], 'g128': [OFF, L(PC), L(FI)], 'g129': [N(CASE38), P('props:' + AT), P('props:' + PO), L(PC), L(CV)],
 'g130': [OFF, P('props:' + PO + '#2')],
 # 11구간 — 내보내기 · 새 그림 · 가져오기
 'g131': [A(ck('export'))], 'g132': [P('tab:PNG'), A([['download', 'png', 'Untitled graph']])], 'g133': [A([['click', 'tab:JSON'], ['download', 'json', 'Untitled graph']])],
 'g134': [A(ck('done'))], 'g135': [A(ck('blank'))], 'g136': [A(ck('logo'))],
 'g137': [P('menu:New'), A([['click', 'menu:newLocal']])], 'g138': [A(ck('blank'))],
 'g139': [A([['click', 'logo'], ['click', 'menu:Import']])], 'g140': [A([['choose', 'json']])], 'g141': [A(ck('importButton'))],
 'g142': [P('selCount'), P('props:' + PO), P('ctext:SOP-FAN-11'), L(PC)], 'g143': [L(F), P('ctext:LEADS_TO')],
 'g144': [A([['click', 'blank'], ['click', 'node:'], ['click', 'text:Delete'], ['verify']])],
 # 12구간 — Cypher
 'g146': [A(ck('export'))], 'g147': [A(ck('tab:Cypher'))], 'g148': [P('cypherText'), P('cypherHead'), A(ck('done'))],
}
