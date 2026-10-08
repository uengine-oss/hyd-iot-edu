/* U4 (TODO 4): 흐름 판본 배포 · 비교 · 되돌리기 — 경보가 여는 "운영 판본"을 바꾼다. 열린 처리 건은 자기 판본으로 끝난다.
   API: GET /api/process/definitions · GET …/{id}/versions · GET …/{id}/compare?from_version&to_version · POST …/{id}/deploy · POST …/{id}/rollback
   화면 기준: process-gpt-vue3 ProcessDefinitionVersionManager(판본 목록 · 반영 버전 표시 · 반영 요청) · VersionComparison(바뀐 요소 목록).
   B4: 경보 → 흐름 표(GET /api/flows/deployments) · 기준 흐름으로 되돌리기(POST /api/flows/deploy-reset) · 기준과 비교(GET /api/flows/deploy-compare). */
(function () {
  const $d = id => document.getElementById(id);
  const base = id => API.process + '/api/process/definitions/' + encodeURIComponent(id);
  let status = null, busy = false, compareWith = null;
  const patName = p => (typeof PATTERN_LABEL !== 'undefined' && PATTERN_LABEL[p]) || p;
  function box(id, before) { let el = $d(id); if (!el) { el = document.createElement('div'); el.id = id; $d(before).before(el); } return el; }
  async function loadRoutes() {
    const r = await getJ(API.process + '/api/flows/deployments');
    const rows = r.routes.map(x => `<tr><th>${esc(patName(x.pattern))}</th><td>${esc(x.name || UI.defName(x.definition))} · 판본 ${esc(x.version)}</td><td>${UI.chipText(x.source, x.reference ? 'success' : 'warning')}</td></tr>`).join('');
    const shadow = r.flows.filter(f => f.shadowed.length).map(f => `<p class="muted">${esc(f.name || f.definition)}: ${f.shadowed.map(patName).map(esc).join(', ')}는 더 최근에 배포한 흐름이 엽니다</p>`).join('');
    box('deployRoutes', 'deployStatus').innerHTML = UI.card({
      title: '경보 → 흐름 (지금 배포된 것)', chips: r.at_reference ? UI.chipText('기준 흐름', 'success') : UI.chipText('내가 바꾼 흐름 있음', 'warning'),
      value: `기준 판본 <b>${esc(r.reference.version)}</b>${r.reference.changed ? ` · 지금 운영 ${esc(r.reference.deployed_version)}` : ''}`,
      sub: '다음 경보부터 이 표대로 열립니다. 이미 열린 처리 건은 자기 판본으로 끝납니다.',
      body: `<table class="compact-table"><tbody>${rows}</tbody></table>${shadow}` +
        `<div class="form-actions"><button type="button" class="btn" id="deployResetRef" ${r.at_reference ? 'disabled' : ''}>기준 흐름으로 되돌리기</button></div>`
    });
  }
  const message = (text, error = false) => { $d('deployMessage').textContent = text; $d('deployMessage').className = 'form-msg ' + (error ? 'neg' : 'pos'); };
  async function action(fn) {
    if (busy) return;
    busy = true;
    const buttons = [...$d('definitionDeployPanel').querySelectorAll('button')]; buttons.forEach(b => b.disabled = true);
    try { await fn(); } catch (e) { message(e.message, true); }
    finally { busy = false; buttons.forEach(b => b.disabled = false); syncButtons(); }
  }
  function who() {
    const by = $d('deployBy').value.trim(), reason = $d('deployReason').value.trim();
    if (!by) throw Error('담당자를 적으세요');
    if (!reason) throw Error('사유를 적으세요');
    try { localStorage.setItem('hyd.deployBy', by); } catch (e) { /* per-viewer convenience only */ }
    return { by, reason };
  }
  function syncButtons() {
    $d('deployRollback').disabled = busy || !status || !status.rollback_version;
    $d('deployRollback').textContent = status && status.rollback_version ? `이전 배포 판본(${status.rollback_version})으로 되돌리기` : '이전 배포 판본으로 되돌리기';
  }
  async function loadDefinitions(selected) {
    const rows = await getJ(API.process + '/api/process/definitions');
    const ids = [...new Set(rows.map(r => r.id))];
    const select = $d('deployChoice'); const current = selected || select.value; select.replaceChildren();
    ids.forEach(id => {
      const row = rows.find(r => r.id === id), option = document.createElement('option');
      option.value = id; option.textContent = `${UI.defName(id)} · ${id}` + (row.deployed_version ? ` (운영 ${row.deployed_version})` : ' (배포 전)');
      select.appendChild(option);
    });
    if (ids.includes(current)) select.value = current;
    await loadRoutes();
    if (!ids.length) { $d('deployStatus').innerHTML = UI.empty('등록된 정의가 없습니다', '먼저 위 패널에서 정의 판본을 등록하세요'); return; }
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
      title: esc(s.name || UI.defName(s.id)), chips: s.alert_entry ? UI.chipText('경보 진입 정의', 'accent') : UI.chipText('직접 시작 전용', 'neutral'),
      value: s.deployed_version ? `운영 판본 <b>${esc(s.deployed_version)}</b>` : '배포된 판본 없음',
      sub: s.alert_entry ? '다음 경보부터 운영 판본으로 처리 건이 열립니다. 이미 열린 처리 건은 자기 판본으로 끝납니다.' : '이 정의는 경보가 아니라 직접 시작으로만 실행됩니다.',
      body: deployed && deployed.registered_at ? `<p class="muted">운영 판본 등록 ${esc(UI.dateTime(deployed.registered_at))}${deployed.message ? ' · ' + esc(deployed.message) : ''}</p>` : ''
    });
    $d('deployVersions').innerHTML = [...s.versions].reverse().map(v => `<div class="item"><div class="row"><strong>판본 ${esc(v.version)}</strong>${versionChip(v)}</div>` +
      `<p class="muted">${v.registered_at ? '등록 ' + esc(UI.dateTime(v.registered_at)) : '등록 시각 없음'}${v.form_source === 'legacy-live' ? ' · 기존 폼(판본 안에 폼 없음)' : ''}</p>` +
      (v.problem ? UI.fold('검사 실패 사유', `<p class="neg">${esc(v.problem)}</p>`, { cls: 'small' }) : '') +
      `<div class="form-actions">` +
      (s.deployed_version && !v.deployed ? `<button type="button" class="btn small" data-compare="${esc(v.version)}">운영 판본과 비교</button>` : '') +
      (!(s.reference && v.version === s.reference_version) ? `<button type="button" class="btn small" data-refcompare="${esc(v.version)}">기준과 비교</button>` : '') +
      `<button type="button" class="btn ${v.deployed || !v.deployable ? 'small' : 'primary'}" data-deploy="${esc(v.version)}" ${v.deployed || !v.deployable ? 'disabled' : ''}>${v.deployed ? '운영 중' : '이 판본 배포'}</button></div></div>`).join('');
    $d('deployCompare').innerHTML = s.versions.length > 1 ? UI.section('판본 비교', `<div class="field"><label for="deployFrom">기준</label><select id="deployFrom">${s.versions.map(v => `<option value="${esc(v.version)}" ${v.deployed ? 'selected' : ''}>${esc(v.version)}${v.deployed ? ' (운영)' : ''}</option>`).join('')}</select></div>` +
      `<div class="field"><label for="deployTo">비교 대상</label><select id="deployTo">${s.versions.map(v => `<option value="${esc(v.version)}" ${v.version === (compareWith || s.versions[s.versions.length - 1].version) ? 'selected' : ''}>${esc(v.version)}</option>`).join('')}</select></div>`) +
      `<div class="form-actions"><button type="button" class="btn small" id="deployCompareRun">바뀐 것 보기</button></div><div id="deployDiff"></div>` : '';
    $d('deployHistory').innerHTML = UI.fold(`배포 이력 ${UI.chipText(String(s.history.length), 'neutral')}`,
      s.history.length ? `<div class="list">${s.history.map(h => `<div class="item"><div class="row"><strong>${esc(actionName(h.action))} → 판본 ${esc(h.version)}</strong><span class="muted">${esc(UI.dateTime(h.created_at))}</span></div>` +
        `<p class="muted">${h.previous_version ? '이전 ' + esc(h.previous_version) + ' · ' : ''}${esc(UI.who(h.actor))} · ${esc(h.reason)}</p></div>`).join('')}</div>` : UI.empty('배포 이력이 없습니다'), { cls: 'small' });
    if (compareWith) runCompare();
    syncButtons();
  }
  const actionName = a => ({ seed: '기동 시드', deploy: '배포', rollback: '되돌리기', reset: '기준으로 되돌리기', withdraw: '경보 경로에서 내림' }[a] || a);
  async function runRefCompare(version) {
    const d = await getJ(API.process + `/api/flows/deploy-compare?definition=${encodeURIComponent(status.id)}&version=${encodeURIComponent(version)}`);
    box('deployRefDiff', 'deployCompare').innerHTML = UI.section(`기준(${d.reference.version})과 비교 — 판본 ${version}`,
      d.same ? UI.empty('기준 흐름과 같습니다') :
        `<p class="muted">${esc(d.summary)}</p>` + (d.steps.length ? `<ul>${d.steps.map(t => `<li>${esc(t)}</li>`).join('')}</ul>` : '<p class="muted">바뀐 단계·연결은 없습니다</p>') +
        UI.fold(`바뀐 것 전체 ${d.changes.length}`, `<div class="list">${d.changes.map(ch => `<div class="item"><strong>${esc(ch.text)}</strong></div>`).join('')}</div>`, { cls: 'small' }));
  }
  async function runCompare() {
    const from = $d('deployFrom').value, to = $d('deployTo').value;
    if (from === to) { $d('deployDiff').innerHTML = UI.empty('같은 판본입니다', '다른 판본을 고르세요'); return; }
    const diff = await getJ(base(status.id) + `/compare?from_version=${encodeURIComponent(from)}&to_version=${encodeURIComponent(to)}`);
    const c = diff.counts;
    $d('deployDiff').innerHTML = diff.same ? UI.empty('차이가 없습니다', `${from} → ${to}: 단계·연결·조건·변수·역할·폼이 같습니다`) :
      `<p class="muted">${esc(from)} → ${esc(to)}: ${UI.chipText('추가 ' + c['추가'], 'success')} ${UI.chipText('삭제 ' + c['삭제'], 'danger')} ${UI.chipText('변경 ' + c['변경'], 'warning')}</p>` +
      `<div class="list">${diff.changes.map(ch => `<div class="item"><div class="row"><strong>${esc(ch.text)}</strong>${UI.chipText(ch.change, { '추가': 'success', '삭제': 'danger', '변경': 'warning' }[ch.change])}</div>` +
        (ch.fields && ch.fields.length ? UI.fold(`바뀐 항목 ${ch.fields.length}`, `<table class="compact-table"><tbody>${ch.fields.map(f => `<tr><th>${esc(f.label)}</th><td>${esc(f.before)}</td><td>→ ${esc(f.after)}</td></tr>`).join('')}</tbody></table>`, { cls: 'small', open: ch.change === '변경' }) : '') +
        '</div>').join('')}</div>`;
  }
  $d('definitionDeployPanel').addEventListener('toggle', () => {
    if ($d('definitionDeployPanel').open && !status) action(() => loadDefinitions());
  });
  try { $d('deployBy').value = localStorage.getItem('hyd.deployBy') || ''; } catch (e) { /* storage may be blocked */ }
  $d('deployChoice').addEventListener('change', () => action(() => loadStatus()));
  $d('deployRefresh').addEventListener('click', () => action(() => loadDefinitions()));
  $d('deployRollback').addEventListener('click', () => action(async () => {
    const out = await postJ(base(status.id) + '/rollback', who());
    await loadDefinitions(status.id);
    message(`${out.definition} 운영 판본을 ${out.previous_version} → ${out.version}으로 되돌렸습니다. ${out.applies_to} 적용됩니다.`);
  }));
  $d('definitionDeployPanel').addEventListener('click', ev => {
    const deploy = ev.target.closest('[data-deploy]'), compare = ev.target.closest('[data-compare]'), refCompare = ev.target.closest('[data-refcompare]');
    if (ev.target.id === 'deployResetRef') return action(async () => {
      const by = $d('deployBy').value.trim();
      if (!by) throw Error('담당자를 적으세요');
      if (!await UI.confirm({ title: '기준 흐름으로 되돌릴까요?', body: '내가 배포한 흐름은 경보 경로에서 내리고, 기준 흐름의 운영 판본을 기준 판본으로 돌립니다. 등록한 판본과 열린 처리 건은 그대로입니다.', ok: '되돌리기', danger: true })) return;
      const out = await postJ(API.process + '/api/flows/deploy-reset', { by, reason: $d('deployReason').value.trim() || null });
      await loadDefinitions(status && status.id);
      message(out.message);
    });
    if (refCompare) return action(() => runRefCompare(refCompare.dataset.refcompare));
    if (deploy) action(async () => {
      const out = await postJ(base(status.id) + '/deploy', { ...who(), version: deploy.dataset.deploy });
      await loadDefinitions(status.id);
      message(`${out.definition} 운영 판본 ${out.previous_version || '없음'} → ${out.version} 배포. ${out.applies_to} 적용됩니다.`);
    });
    else if (compare) { compareWith = compare.dataset.compare; action(async () => { render(); }); }
    else if (ev.target.id === 'deployCompareRun') action(runCompare);
  });
})();
