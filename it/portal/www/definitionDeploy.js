/* U4: 흐름 판본 배포 · 비교 · 되돌리기 — 경보가 여는 "운영 판본"을 바꾼다. 열린 처리 건은 자기 판본으로 끝난다.
   자리: 흐름 화면의 ④ 배포(index.html view-flows 의 #definitionDeployPanel — 접기가 아니라 늘 보이는 단계다. 옛 자리는 관리 화면의 접기였다).
   읽는 때: 흐름 화면에 들어올 때마다(hydTabs.onShow) 정의 · 배포 상태를 새로 읽는다. 다른 화면에 있을 때는 읽지 않는다. 흐름 화면이 판본을 등록하면 reload(정의)를 부른다.
   API: GET /api/process/definitions · GET …/{id}/versions · GET …/{id}/compare?from_version&to_version · POST …/{id}/deploy · POST …/{id}/rollback
   화면 기준: process-gpt-vue3 ProcessDefinitionVersionManager(판본 목록 · 반영 버전 표시 · 반영 요청) · VersionComparison(바뀐 요소 목록).
   B4: 경보 → 흐름 표(GET /api/flows/deployments) · 기준 흐름으로 되돌리기(POST /api/flows/deploy-reset) · 기준과 비교(GET /api/flows/deploy-compare). */
(function () {
  const $d = id => document.getElementById(id);
  const base = id => API.process + '/api/process/definitions/' + encodeURIComponent(id);
  let status = null, compareWith = null, deployedIds = new Set();
  const patName = p => UI.patternName(p), nameOf = hydDefinitions.name;   // 패널 일 · 흐름 이름은 definitionRegistry.js 의 한 벌(W3-28)
  function box(id, before) { let el = $d(id); if (!el) { el = document.createElement('div'); el.id = id; $d(before).before(el); } return el; }
  async function loadRoutes() {
    const r = await getJ(API.process + '/api/flows/deployments');
    const rows = r.routes.map(x => `<tr><th>${esc(patName(x.pattern))}</th><td>${esc(nameOf(x.definition, x.name))} · 판본 ${esc(x.version)}</td><td>${UI.chipText(x.source, x.reference ? 'success' : 'neutral')}</td></tr>`).join('');
    const shadow = r.flows.filter(f => f.shadowed.length).map(f => `<p class="muted">${esc(nameOf(f.definition, f.name))}: ${f.shadowed.map(patName).map(esc).join(', ')}는 더 최근에 배포한 흐름이 엽니다</p>`).join('');
    // P9: [기준 흐름으로 되돌리기]는 시작이 설치한 수업 흐름을 남긴다 — 수업 흐름만 있으면 되돌릴 것이 없다(서버 reset_needed)
    const resetNeeded = r.reset_needed;
    box('deployRoutes', 'deployStatus').innerHTML = UI.card({
      title: '경보 → 흐름 (지금 배포된 것)', chips: r.at_reference ? UI.chipText('기준 흐름', 'success') : resetNeeded ? UI.chipText('내가 바꾼 흐름 있음', 'warning') : UI.chipText('수업 흐름', 'accent'),
      value: `기준 판본 <b>${esc(r.reference.version)}</b>${r.reference.changed ? ` · 지금 운영 ${esc(r.reference.deployed_version)}` : ''}`,
      sub: '다음 경보부터 이 표대로 열립니다. 이미 열린 처리 건은 자기 판본으로 끝납니다.',
      body: `<table class="compact-table"><tbody>${rows}</tbody></table>${shadow}` +
        `<div class="form-actions"><button type="button" class="btn" id="deployResetRef" ${resetNeeded ? '' : 'disabled'}>기준 흐름으로 되돌리기</button></div>`
    });
  }
  const panel = hydDefinitions.task($d('definitionDeployPanel'), $d('deployMessage'), syncButtons), action = panel.run, message = panel.say;
  // 담당자 = 이 PC의 담당자(inbox.js me). 화면에 담당자 칸은 없고 숨은 칸(deployBy)에 이름만 둔다 — 자유 입력은 배포 이력에 지어낸 이름을 남겼다. 서버도 사람만 받는다(inbox.require_person)
  function showMe() {
    const m = window.hydInbox?.me?.(), el = $d('deployBy');
    el.readOnly = true; el.value = m ? m.name : ''; el.placeholder = '담당자 정보를 읽는 중…';
    return m;
  }
  window.addEventListener('hyd:me', () => { if ($d('deployBy')) showMe(); });
  function meId() {
    const m = showMe();
    if (!m) throw Error('담당자 정보를 읽지 못했습니다. 화면을 새로 고친 뒤 다시 해 주세요');
    return m.id;
  }
  function who() {
    const by = meId(), reason = $d('deployReason').value.trim();
    if (!reason) throw Error('사유를 적으세요');
    return { by, reason };
  }
  function syncButtons() {
    $d('deployRollback').disabled = panel.busy || !status || !status.rollback_version;
    $d('deployRollback').textContent = status && status.rollback_version ? `이전 배포 판본(${status.rollback_version})으로 되돌리기` : '이전 배포 판본으로 되돌리기';
  }
  async function loadDefinitions(selected) {
    const rows = await getJ(API.process + '/api/process/definitions');
    const ids = [...new Set(rows.map(r => r.id))];
    deployedIds = new Set(rows.filter(r => r.deployed_version).map(r => r.id));
    window.dispatchEvent(new Event('hyd:deployed'));      // 흐름 화면의 단계 표시가 배포 여부를 다시 그린다(flows.js drawSteps)
    const select = $d('deployChoice'); const current = selected || select.value; select.replaceChildren();
    ids.forEach(id => {
      const row = rows.find(r => r.id === id), option = document.createElement('option');
      // 경보로 열지 않는 정의(질문 · 교대 등)는 배포 개념이 없다 — 「배포 전」을 붙이지 않는다(W3-29)
      option.value = id; option.textContent = nameOf(id, row.name) + (row.deployed_version ? ` · 운영 판본 ${row.deployed_version}` : '');
      select.appendChild(option);
    });
    if (ids.includes(current)) select.value = current;
    await loadRoutes();
    if (!ids.length) { $d('deployStatus').innerHTML = UI.empty('등록된 흐름이 없습니다', '먼저 위 3단계에서 판본을 등록하세요'); return; }
    await loadStatus();
  }
  async function loadStatus() {
    const id = $d('deployChoice').value; if (!id) return;
    status = await getJ(base(id) + '/versions'); compareWith = null;
    render();
  }
  function versionChip(v) {
    if (v.deployed) return UI.chipText('운영 중 · 경보가 이 판본으로 열림', 'success');
    if (!v.deployable) return UI.chipText('검사 실패 · 배포 불가', 'danger');
    return UI.chipText('배포 가능', 'neutral');
  }
  function render() {
    const s = status, deployed = s.versions.find(v => v.deployed);
    $d('deployStatus').innerHTML = UI.card({
      title: esc(nameOf(s.id, s.name)), chips: s.alert_entry ? UI.chipText('경보로 시작하는 흐름', 'accent') : UI.chipText('직접 시작하는 흐름', 'neutral'),
      value: s.deployed_version ? `운영 판본 <b>${esc(s.deployed_version)}</b>` : '배포된 판본 없음',
      sub: s.alert_entry ? '다음 경보부터 운영 판본으로 처리 건이 열립니다. 이미 열린 처리 건은 자기 판본으로 끝납니다.' : '이 흐름은 경보가 아니라 직접 시작으로만 실행됩니다. 배포하지 않아도 5단계의 [직접 시작]으로 엽니다.',
      body: deployed && deployed.registered_at ? `<p class="muted">운영 판본 등록 ${esc(UI.dateTime(deployed.registered_at))}${deployed.message ? ' · ' + esc(deployed.message) : ''}</p>` : ''
    });
    $d('deployVersions').innerHTML = [...s.versions].reverse().map(v => `<div class="item"><div class="row"><strong>판본 ${esc(v.version)}</strong>${versionChip(v)}</div>` +
      `<p class="muted">${v.registered_at ? '등록 ' + esc(UI.dateTime(v.registered_at)) : '등록 시각 없음'}</p>` +
      (v.problem ? UI.fold('검사 실패 사유', `<p class="neg">${esc(v.problem)}</p>`, { cls: 'small' }) : '') +
      `<div class="form-actions">` +
      (s.deployed_version && !v.deployed ? `<button type="button" class="btn small" data-compare="${esc(v.version)}">운영 판본과 비교</button>` : '') +
      (refComparable(s, v) ? `<button type="button" class="btn small" data-refcompare="${esc(v.version)}">기준과 비교</button>` : '') +
      `<button type="button" class="btn ${v.deployed || !v.deployable ? 'small' : 'primary'}" data-deploy="${esc(v.version)}" ${v.deployed || !v.deployable ? 'disabled' : ''}>${v.deployed ? '운영 중' : '이 판본 배포'}</button></div></div>`).join('');
    $d('deployCompare').innerHTML = s.versions.length > 1 ? UI.section('판본 비교', `<div class="field"><label for="deployFrom">기준</label><select id="deployFrom">${s.versions.map(v => `<option value="${esc(v.version)}" ${v.deployed ? 'selected' : ''}>${esc(v.version)}${v.deployed ? ' (운영)' : ''}</option>`).join('')}</select></div>` +
      `<div class="field"><label for="deployTo">비교 대상</label><select id="deployTo">${s.versions.map(v => `<option value="${esc(v.version)}" ${v.version === (compareWith || s.versions[s.versions.length - 1].version) ? 'selected' : ''}>${esc(v.version)}</option>`).join('')}</select></div>`) +
      `<div class="form-actions"><button type="button" class="btn small" id="deployCompareRun">바뀐 것 보기</button></div><div id="deployDiff"></div>` : '';
    $d('deployHistory').innerHTML = UI.fold(`배포 이력 ${UI.chipText(String(s.history.length), 'neutral')}`,
      s.history.length ? `<div class="list">${s.history.map(h => `<div class="item"><div class="row"><strong>${esc(actionName(h.action))} → 판본 ${esc(h.version)}</strong><span class="muted">${esc(UI.dateTime(h.created_at))}</span></div>` +
        `<p class="muted">${h.previous_version ? '이전 ' + esc(h.previous_version) + ' · ' : ''}${esc(UI.who(h.actor))} · ${esc(h.reason)}</p></div>`).join('')}</div>` : UI.empty('배포 이력이 없습니다'), { cls: 'small' });
    if (compareWith) runCompare().catch(e => { $d('deployDiff').innerHTML = UI.errorBlock('판본을 비교하지 못했습니다', e.message); });
    syncButtons();
  }
  // 「기준과 비교」: 서버가 정한 이 흐름의 비교 기준(versions 응답 compare_base = flow_deploy.compare_base)이 있을 때만, 기준 판본 자신은 빼고(W3-03).
  // 화면이 기준 규칙(경보 흐름인가 · 수업 흐름인가)을 따로 셈하지 않는다
  const refComparable = (s, v) => !!s.compare_base && !(s.compare_base.definition === s.id && s.compare_base.version === v.version);
  // 배포 · 되돌리기 결과 한 줄: 흐름은 이름으로, 경보는 경보 이름으로(서버 applies_to 의 경보 코드를 그대로 보이지 않는다 — W3-17)
  function doneText(out, name, verb) {
    const when = out.patterns.length ? `다음 경보(${out.patterns.map(patName).join(' · ')})부터` : out.applies_to;
    return `「${nameOf(out.definition, name)}」 운영 판본 ${out.previous_version || '없음'} → ${out.version} ${verb}. ${when} 적용됩니다.`;
  }
  // refComparable · doneText 는 시험(test_www_definitionDeploy)이, deployed · reload 는 흐름 화면(flows.js)이 부른다.
  // deployed(정의): 그 흐름에 운영 판본이 있는가(마지막으로 읽은 값). reload(정의): 판본 등록 · 되돌리기 뒤 목록을 새로 읽고, 정의를 주면 그 흐름을 고른다
  window.hydDefinitionDeploy = { refComparable, doneText, deployed: id => deployedIds.has(id), reload: selected => action(() => loadDefinitions(selected)) };
  const actionName = a => ({ seed: '처음 설치', deploy: '배포', rollback: '되돌리기', reset: '기준으로 되돌리기', withdraw: '경보 경로에서 내림' }[a] || a);
  async function runRefCompare(version) {
    const d = await getJ(API.process + `/api/flows/deploy-compare?definition=${encodeURIComponent(status.id)}&version=${encodeURIComponent(version)}`);
    const ref = d.reference;
    box('deployRefDiff', 'deployCompare').innerHTML = UI.section(`판본 ${version} ↔ 기준 「${nameOf(ref.definition, ref.name)}」 판본 ${ref.version}`,
      `<p class="muted">기준을 고른 까닭: ${esc(UI.plain(ref.why))}${ref.pattern ? ' — 경보 ' + esc(patName(ref.pattern)) : ''}</p>` + (d.same ? UI.empty('기준 흐름과 같습니다') :
        `<p class="muted">${esc(UI.plain(d.summary))}</p>` + (d.steps.length ? `<ul>${d.steps.map(t => `<li>${esc(UI.plain(t))}</li>`).join('')}</ul>` : '<p class="muted">바뀐 단계·연결은 없습니다</p>') +
        UI.fold(`바뀐 것 전체 ${d.changes.length}`, `<div class="list">${d.changes.map(ch => `<div class="item"><strong>${esc(UI.plain(ch.text))}</strong></div>`).join('')}</div>`, { cls: 'small' })));
  }
  async function runCompare() {
    const from = $d('deployFrom').value, to = $d('deployTo').value;
    if (from === to) { $d('deployDiff').innerHTML = UI.empty('같은 판본입니다', '다른 판본을 고르세요'); return; }
    const diff = await getJ(base(status.id) + `/compare?from_version=${encodeURIComponent(from)}&to_version=${encodeURIComponent(to)}`);
    const c = diff.counts;
    $d('deployDiff').innerHTML = diff.same ? UI.empty('차이가 없습니다', `${from} → ${to}: 단계·연결·조건·변수·역할·폼이 같습니다`) :
      `<p class="muted">${esc(from)} → ${esc(to)}: ${UI.chipText('추가 ' + c['추가'], 'success')} ${UI.chipText('삭제 ' + c['삭제'], 'danger')} ${UI.chipText('변경 ' + c['변경'], 'warning')}</p>` +
      `<div class="list">${diff.changes.map(ch => `<div class="item"><div class="row"><strong>${esc(UI.plain(ch.text))}</strong>${UI.chipText(ch.change, { '추가': 'success', '삭제': 'danger', '변경': 'warning' }[ch.change])}</div>` +
        (ch.fields && ch.fields.length ? UI.fold(`바뀐 항목 ${ch.fields.length}`, `<table class="compact-table"><tbody>${ch.fields.map(f => `<tr><th>${esc(UI.plain(f.label))}</th><td>${esc(UI.plain(f.before))}</td><td>→ ${esc(UI.plain(f.after))}</td></tr>`).join('')}</tbody></table>`, { cls: 'small', open: ch.change === '변경' }) : '') +
        '</div>').join('')}</div>`;
  }
  hydTabs.onShow(name => { if (name === 'flows') { showMe(); action(() => loadDefinitions()); } });
  showMe();
  $d('deployChoice').addEventListener('change', () => action(() => loadStatus()));
  $d('deployRefresh').addEventListener('click', () => action(() => loadDefinitions()));
  $d('deployRollback').addEventListener('click', () => action(async () => {
    const body = who();      // 담당자 · 사유가 없으면 묻기 전에 멈춘다
    if (!await UI.confirm({ title: `이전 배포 판본(${status.rollback_version})으로 되돌릴까요?`, body: '다음 경보부터 그 판본으로 처리 건이 열립니다. 이미 열린 처리 건은 자기 판본으로 끝납니다.', ok: '되돌리기', danger: true })) return;
    const out = await postJ(base(status.id) + '/rollback', body);
    await loadDefinitions(status.id);
    message(doneText(out, status.name, '되돌림'));
  }));
  $d('definitionDeployPanel').addEventListener('click', ev => {
    const deploy = ev.target.closest('[data-deploy]'), compare = ev.target.closest('[data-compare]'), refCompare = ev.target.closest('[data-refcompare]');
    if (ev.target.id === 'deployResetRef') return action(async () => {
      const by = meId();
      if (!await UI.confirm({ title: '기준 흐름으로 되돌릴까요?', body: '학생이 배포한 흐름만 내립니다. 수업 흐름(시작할 때 설치되는 A · B · C)은 남습니다. 기준 흐름의 운영 판본은 기준 판본으로 돌리고, 등록한 판본과 열린 처리 건은 그대로입니다.', ok: '되돌리기', danger: true })) return;
      const out = await postJ(API.process + '/api/flows/deploy-reset', { by, reason: $d('deployReason').value.trim() || null });
      await loadDefinitions(status && status.id);
      message(out.message);   // 남긴 수업 흐름의 이름은 서버 문장이 말한다(flow_deploy.deploy_reset — kept 가 있으면 늘 이름까지)
    });
    if (refCompare) return action(() => runRefCompare(refCompare.dataset.refcompare));
    if (deploy) action(async () => {
      const out = await postJ(base(status.id) + '/deploy', { ...who(), version: deploy.dataset.deploy });
      await loadDefinitions(status.id);
      message(doneText(out, status.name, '배포'));
    });
    else if (compare) { compareWith = compare.dataset.compare; action(async () => { render(); }); }
    else if (ev.target.id === 'deployCompareRun') action(runCompare);
  });
})();
