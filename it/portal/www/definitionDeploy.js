/* U4: 흐름 판본 배포 · 비교 · 되돌리기 — 경보가 여는 "운영 판본"을 바꾼다. 열린 처리 건은 자기 판본으로 끝난다.
   자리: 흐름 화면에서 고른 흐름의 「판본 · 배포」 절(index.html view-flows 의 #definitionDeployPanel)과, 화면 아래의 「경보별 운영 흐름」 표(#deployRoutes).
   어느 흐름을 보일지는 흐름 화면(flows.js)이 목록에서 고른 것이다 — select(정의). 이 파일에는 흐름을 고르는 칸이 없다.
   읽는 때: 흐름 화면에 들어올 때마다(hydTabs.onShow) 정의 · 배포 상태를 새로 읽는다. 다른 화면에 있을 때는 읽지 않는다. 흐름 화면이 판본을 등록하면 reload(정의)를 부른다.
   API: GET /api/process/definitions · GET …/{id}/versions · GET …/{id}/compare?from_version&to_version · POST …/{id}/deploy · POST …/{id}/rollback
   화면 기준: process-gpt-vue3 ProcessDefinitionVersionManager(판본 목록 · 반영 버전 표시 · 반영 요청) · VersionComparison(바뀐 요소 목록).
   B4: 경보 → 흐름 표(GET /api/flows/deployments) · 기준과 비교(GET /api/flows/deploy-compare). */
(function () {
  const $d = id => document.getElementById(id);
  const base = id => API.process + '/api/process/definitions/' + encodeURIComponent(id);
  let status = null, compareWith = null, deployedIds = new Set(), rows = [], chosen = '';
  const patName = p => UI.patternName(p), nameOf = hydDefinitions.name;   // 패널 일 · 흐름 이름은 definitionRegistry.js 의 한 벌(W3-28)
  const tag = (label, tone) => `<span class="tag"${tone ? ` data-tone="${tone}"` : ''}>${esc(label)}</span>`;
  // 경보 → 흐름 한 줄의 구분: 흐름 목록과 같은 말(기본 제공 / 내가 배포한 흐름)로, 서버가 준 표시로 가른다. 종류 표시라 상태색(초록)을 쓰지 않는다.
  // 주황은 상태다 — 기본 제공 흐름의 운영 판본이 처음 판본에서 바뀌어 있을 때
  const kindTag = (label, tone) => `<span class="tag" data-plain${tone ? ` data-tone="${tone}"` : ''}>${esc(label)}</span>`;
  // 기본 제공 흐름은 표시하지 않는다(모든 줄이 같은 값인 뱃지는 정보가 없다) — 내가 배포했거나 운영 판본이 바뀐 줄만 말한다
  const routeKind = x => x.reference || x.class_flow ? '' : /기준 흐름/.test(x.source || '') ? tag('기본 제공 · 운영 판본 바뀜', 'warn') : kindTag('내가 배포한 흐름', 'brand');

  async function loadRoutes() {
    const r = await getJ(API.process + '/api/flows/deployments');
    const marked = r.routes.some(x => routeKind(x));
    const body = r.routes.map(x => `<tr><th scope="row">${esc(patName(x.pattern))}</th><td>${esc(nameOf(x.definition, x.name))}</td><td class="num">${esc(x.version)}</td>${marked ? `<td>${routeKind(x)}</td>` : ''}</tr>`).join('');
    const shadow = r.flows.filter(f => f.shadowed.length).map(f => `<p class="muted">${esc(nameOf(f.definition, f.name))}: ${f.shadowed.map(patName).map(esc).join(', ')}는 더 최근에 배포한 흐름이 엽니다.</p>`).join('');
    $d('deployRoutes').innerHTML = (body ? `<div class="table-container"><table class="table"><thead><tr><th>경보</th><th>여는 흐름</th><th class="num">운영 판본</th>${marked ? '<th>구분</th>' : ''}</tr></thead><tbody>${body}</tbody></table></div>`
      : UI.empty('경보로 시작하는 흐름이 없습니다', '경보로 시작하는 흐름을 배포하면 어느 경보가 어느 흐름을 여는지 여기에 보입니다.')) + shadow;
    $d('deployRoutesNote').textContent = r.reset_needed ? '내가 배포한 흐름이 경보를 엽니다.' : '경보가 나면 이 표의 흐름과 판본으로 처리 건이 열립니다.';
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
    if (!reason) throw Error('사유를 적으세요 — 왜 이 판본을 운영에 올리는지(되돌리는지)가 배포 이력에 남습니다');
    return { by, reason };
  }
  function syncButtons() {
    const can = !!(status && status.rollback_version);
    $d('deployRollback').hidden = !can;
    $d('deployRollback').disabled = panel.busy || !can;
    $d('deployRollbackText').textContent = can ? `이전 배포 판본(${status.rollback_version})으로 되돌리기` : '이전 배포 판본으로 되돌리기';
  }
  async function loadDefinitions(selected) {
    rows = await getJ(API.process + '/api/process/definitions');
    deployedIds = new Set(rows.filter(r => r.deployed_version).map(r => r.id));
    if (selected) chosen = selected;
    window.dispatchEvent(new Event('hyd:deployed'));      // 흐름 화면이 목록 · 단계 줄의 배포 여부를 다시 그린다(flows.js)
    await loadRoutes();
    await loadStatus();
  }
  // 고른 흐름의 판본 · 배포 상태. 등록한 판본이 없는 흐름(가져오기만 한 초안)이면 이 절을 숨긴다
  async function loadStatus() {
    const registered = !!chosen && rows.some(r => r.id === chosen);
    $d('definitionDeployPanel').hidden = !registered;
    if (!status || status.id !== chosen) message('');      // 다른 흐름을 골랐다 — 앞 흐름의 알림 줄을 지운다
    if (!registered) { status = null; window.dispatchEvent(new Event('hyd:deploy-status')); return; }
    const want = chosen, got = await getJ(base(want) + '/versions');
    if (want !== chosen) return;      // 읽는 사이 다른 흐름을 골랐다 — 이 응답은 그 흐름의 것이 아니다
    status = got; compareWith = null;
    render();
  }
  function versionTag(v) {
    if (v.deployed) return tag('운영 중', 'ok');
    if (!v.deployable) return tag('검사 실패 · 배포 불가', 'danger');
    return tag('배포 가능');
  }
  function render() {
    const s = status;
    $d('deploySummary').textContent = s.deployed_version ? `운영 판본 ${s.deployed_version}` : '배포한 판본 없음';
    $d('deployStatus').innerHTML = `<p class="muted">${esc(s.alert_entry
      ? '배포한 판본이 다음 경보부터 처리 건을 엽니다. 이미 열린 처리 건은 자기 판본으로 끝납니다.'
      : '직접 시작하는 흐름은 배포하지 않습니다.')}</p>`;
    // 다음에 배포할 판본(아직 배포하지 않은 가장 새 판본)에 표시만 단다 — 주 단추로 할지는 흐름 화면이 단계 줄에 맞춰 정한다(flows.js markPrimary).
    // 직접 시작하는 흐름에는 배포를 권하지 않는다(표시를 달지 않는다)
    const next = s.alert_entry ? [...s.versions].reverse().find(v => !v.deployed && v.deployable) : null;
    $d('deployVersions').innerHTML = `<ul class="flow-vers">${[...s.versions].reverse().map(v => `<li><div class="flow-ver"><b>판본 <span class="num">${esc(v.version)}</span></b>${versionTag(v)}` +
      `<span class="muted">${v.registered_at ? '등록 ' + esc(UI.dateTime(v.registered_at)) : '등록 시각 없음'}</span><span class="flow-ver-acts">` +
      (s.deployed_version && !v.deployed ? `<button type="button" class="btn" data-variant="ghost" data-size="sm" data-compare="${esc(v.version)}">운영 판본과 비교</button>` : '') +
      (refComparable(s, v) ? `<button type="button" class="btn" data-variant="ghost" data-size="sm" data-refcompare="${esc(v.version)}">기준과 비교</button>` : '') +
      (v.deployed ? '' : `<button type="button" class="btn" data-variant="outline" data-size="sm" data-deploy="${esc(v.version)}"${v === next ? ' data-deploy-next' : ''} ${v.deployable ? '' : 'disabled'}>${UI.icon('upload')}이 판본 배포</button>`) +
      `</span></div>${v.problem ? `<div class="alert" data-variant="destructive" role="alert">${UI.icon('circle-alert')}<h2>이 판본은 검사에 실패해 배포할 수 없습니다</h2><section>${esc(v.problem)}</section></div>` : ''}</li>`).join('')}</ul>`;
    $d('deployReasonField').hidden = !s.versions.some(v => !v.deployed && v.deployable) && !s.rollback_version;
    $d('deployCompare').innerHTML = s.versions.length > 1 ? UI.fold('판본 비교<span class="muted">두 판본에서 바뀐 단계 · 연결 · 조건</span>', `<div class="flow-compare">` +
      UI.field({ label: '기준', input: `<select id="deployFrom">${s.versions.map(v => `<option value="${esc(v.version)}" ${v.deployed ? 'selected' : ''}>${esc(v.version)}${v.deployed ? ' (운영)' : ''}</option>`).join('')}</select>` }) +
      UI.field({ label: '비교 대상', input: `<select id="deployTo">${s.versions.map(v => `<option value="${esc(v.version)}" ${v.version === (compareWith || s.versions[s.versions.length - 1].version) ? 'selected' : ''}>${esc(v.version)}</option>`).join('')}</select>` }) +
      `<button type="button" class="btn" data-variant="outline" data-deploy-compare>바뀐 것 보기</button></div><div id="deployDiff"></div>`, { open: !!compareWith }) : '';
    $d('deployHistory').innerHTML = UI.fold(`배포 이력<span class="muted">${s.history.length}건</span>`,
      s.history.length ? `<div class="stream-log">${s.history.map(h => `<div class="line">${UI.icon(h.action === 'deploy' || h.action === 'seed' ? 'upload' : 'rotate-ccw')}<span class="line-text"><b>${esc(actionName(h.action))} → 판본 ${esc(h.version)}</b>` +
        `<span class="line-sub">${h.previous_version ? '이전 ' + esc(h.previous_version) + ' · ' : ''}${esc(UI.who(h.actor))} · ${esc(h.reason)}</span></span><time class="line-time num">${esc(UI.dateTime(h.created_at))}</time></div>`).join('')}</div>` : UI.empty('배포 이력이 없습니다', '판본을 배포하거나 되돌리면 누가 왜 했는지 여기에 남습니다.'));
    $d('deployRefDiff').innerHTML = '';
    if (compareWith) runCompare().catch(e => { $d('deployDiff').innerHTML = UI.errorBlock('판본을 비교하지 못했습니다', e.message); });
    syncButtons();
    window.dispatchEvent(new Event('hyd:deploy-status'));      // 흐름 화면이 머리의 상태 뱃지와 「시작」 절을 이 상태로 맞춘다
  }
  // 「기준과 비교」: 서버가 정한 이 흐름의 비교 기준(versions 응답 compare_base = flow_deploy.compare_base)이 있을 때만, 기준 판본 자신은 빼고(W3-03).
  // 화면이 기준 규칙(경보 흐름인가 · 처음부터 들어 있던 흐름인가)을 따로 셈하지 않는다
  const refComparable = (s, v) => !!s.compare_base && !(s.compare_base.definition === s.id && s.compare_base.version === v.version);
  // 배포 · 되돌리기 결과 한 줄: 흐름은 이름으로, 경보는 경보 이름으로(서버 applies_to 의 경보 코드를 그대로 보이지 않는다 — W3-17)
  function doneText(out, name, verb) {
    const when = out.patterns.length ? `다음 경보(${out.patterns.map(patName).join(' · ')})부터` : out.applies_to;
    return `「${nameOf(out.definition, name)}」 운영 판본 ${out.previous_version || '없음'} → ${out.version} ${verb}. ${when} 적용됩니다.`;
  }
  // refComparable · doneText 는 시험(test_www_definitionDeploy)이, 나머지는 흐름 화면(flows.js)이 부른다.
  // deployed(정의): 그 흐름에 운영 판본이 있는가(마지막으로 읽은 값). rows(): 등록된 정의 판본 목록(마지막으로 읽은 값). status(): 고른 흐름의 판본 · 배포 상태.
  // select(정의): 흐름 화면이 목록에서 고른 흐름 — 그 흐름의 판본 · 배포를 읽어 그린다. reload(정의): 판본 등록 · 되돌리기 뒤 목록을 새로 읽고, 정의를 주면 그 흐름을 고른다
  window.hydDefinitionDeploy = { refComparable, doneText, deployed: id => deployedIds.has(id), rows: () => rows, status: () => (status && status.id === chosen ? status : null),
    select: id => { chosen = id || ''; return loadStatus().catch(e => message(e.message, true)); }, reload: selected => action(() => loadDefinitions(selected)) };
  const actionName = a => ({ seed: '처음 설치', deploy: '배포', rollback: '되돌리기', reset: '기준으로 되돌리기', withdraw: '경보 경로에서 내림' }[a] || a);
  const diffTag = change => tag(change, { '추가': 'ok', '삭제': 'danger', '변경': 'warn' }[change]);
  async function runRefCompare(version) {
    const d = await getJ(API.process + `/api/flows/deploy-compare?definition=${encodeURIComponent(status.id)}&version=${encodeURIComponent(version)}`);
    const ref = d.reference;
    $d('deployRefDiff').innerHTML = `<div class="flow-diff"><h4>판본 ${esc(version)} ↔ 기준 「${esc(nameOf(ref.definition, ref.name))}」 판본 ${esc(ref.version)}</h4>` +
      `<p class="muted">기준을 고른 까닭: ${esc(UI.plain(ref.why))}${ref.pattern ? ' — 경보 ' + esc(patName(ref.pattern)) : ''}</p>` + (d.same ? UI.empty('기준 흐름과 같습니다', '단계 · 연결 · 조건이 기준과 다르지 않습니다.') :
        `<p>${esc(UI.plain(d.summary))}</p>` + (d.steps.length ? `<ul class="flow-issues">${d.steps.map(t => `<li>${esc(UI.plain(t))}</li>`).join('')}</ul>` : '<p class="muted">바뀐 단계 · 연결은 없습니다.</p>') +
        UI.fold(`바뀐 것 전체<span class="muted">${d.changes.length}건</span>`, `<ul class="flow-issues">${d.changes.map(ch => `<li>${esc(UI.plain(ch.text))}</li>`).join('')}</ul>`)) + '</div>';
  }
  async function runCompare() {
    const from = $d('deployFrom').value, to = $d('deployTo').value;
    if (from === to) { $d('deployDiff').innerHTML = UI.empty('같은 판본입니다', '다른 판본을 고르세요.'); return; }
    const diff = await getJ(base(status.id) + `/compare?from_version=${encodeURIComponent(from)}&to_version=${encodeURIComponent(to)}`);
    const c = diff.counts;
    $d('deployDiff').innerHTML = diff.same ? UI.empty('차이가 없습니다', `${from} → ${to}: 단계 · 연결 · 조건 · 변수 · 역할 · 폼이 같습니다.`) :
      `<p class="flow-diff-sum"><span class="muted num">${esc(from)} → ${esc(to)}</span>${tag('추가 ' + c['추가'], 'ok')}${tag('삭제 ' + c['삭제'], 'danger')}${tag('변경 ' + c['변경'], 'warn')}</p>` +
      `<ul class="flow-diff-list">${diff.changes.map(ch => `<li><div class="flow-ver"><b>${esc(UI.plain(ch.text))}</b>${diffTag(ch.change)}</div>` +
        (ch.fields && ch.fields.length ? UI.fold(`바뀐 항목<span class="muted">${ch.fields.length}개</span>`, `<div class="table-container"><table class="table"><thead><tr><th>항목</th><th>전</th><th>후</th></tr></thead><tbody>${ch.fields.map(f => `<tr><th scope="row">${esc(UI.plain(f.label))}</th><td>${esc(UI.plain(f.before))}</td><td>${esc(UI.plain(f.after))}</td></tr>`).join('')}</tbody></table></div>`, { open: ch.change === '변경' }) : '') +
        '</li>').join('')}</ul>`;
  }
  hydTabs.onShow(name => { if (name === 'flows') { showMe(); action(() => loadDefinitions()); } });
  showMe();
  $d('deployRollback').addEventListener('click', () => action(async () => {
    const body = who();      // 담당자 · 사유가 없으면 묻기 전에 멈춘다
    if (!await UI.confirm({ title: `이전 배포 판본(${status.rollback_version})으로 되돌릴까요?`, body: '다음 경보부터 그 판본으로 처리 건이 열립니다. 이미 열린 처리 건은 자기 판본으로 끝납니다.', ok: '되돌리기', danger: true })) return;
    const out = await postJ(base(status.id) + '/rollback', body);
    await loadDefinitions(status.id);
    message(doneText(out, status.name, '되돌림'));
  }));
  // 고른 흐름의 절(#definitionDeployPanel)과 화면 아래의 경보별 운영 흐름(#deployRoutesBox) 두 자리의 누름을 한 곳에서 받는다
  function onClick(ev) {
    const deploy = ev.target.closest('[data-deploy]'), compare = ev.target.closest('[data-compare]'), refCompare = ev.target.closest('[data-refcompare]');
    if (refCompare) return action(() => runRefCompare(refCompare.dataset.refcompare));
    if (deploy) action(async () => {
      const out = await postJ(base(status.id) + '/deploy', { ...who(), version: deploy.dataset.deploy });
      await loadDefinitions(status.id);
      message(doneText(out, status.name, '배포'));
    });
    else if (compare) { compareWith = compare.dataset.compare; action(async () => { render(); }); }
    else if (ev.target.closest('[data-deploy-compare]')) action(runCompare);
  }
  $d('definitionDeployPanel').addEventListener('click', onClick);
  $d('deployRoutesBox').addEventListener('click', onClick);
})();
