/* B6 출발본: 내가 만든 구성(에이전트 · 스킬 · MCP · 역할 · 흐름 · 배정 · 배포)을 파일로 받기 · 파일로 불러오기 · 기준으로 되돌리기.
   API: GET /api/config/export · POST /api/config/import {bundle, secrets?, skip_missing_secrets?, by, request_id} · POST /api/config/reset {by, request_id}
   불러오기 · 되돌리기는 도는 동안 서버가 적는 단계별 진행을 읽어 채운다(hydLive.track — GET /api/progress/{request_id}).
   불러오기는 "되돌리기 → 순서대로 적용 → 다시 읽어 대조"이고, 실패하면 어디서 왜 멈췄는지와 적용 전 상태로 되돌렸는지 보여 준다.
   설정에 그대로 적힌 비밀값(MCP 접속 헤더의 토큰 등)은 파일에 없다 — 필요하면 여기서 입력하거나 그 서버만 건너뛴다.
   불러오기가 막힌 단계면 서버가 준 까닭이 단추 바로 뒤 한 줄로 보인다(마우스를 올리지 않아도 — courseAccess.js apply).
   모양은 키트의 것이다: 일마다 판의 한 절(.panel-sec), 진행은 실시간 상자(hydLive.track), 결과는 .result + .evid, 되돌리기는 확인 대화상자(alert-dialog). */
(function () {
  const H = esc;                                        // 포털 공용 이스케이프(ui.js)
  const IMPORT = 'config.import';                        // 수업 경계 행동 키 — 수업 단계에서는 서버가 막고 까닭을 준다(courseAccess.js)
  // [이름, 세는 말] — 도구 서버는 도구 연결 화면(mcp.js)과 같은 이름
  const COUNT_WORDS = { mcp_servers: ['도구 서버', '개'], skills: ['스킬', '개'], agents: ['AI 에이전트', '개'], roles: ['역할', '개'], flows: ['흐름', '개'],
    flow_versions: ['흐름 판본', '개'], assignments: ['단계 배정', '건'], deployments: ['배포', '건'], secrets_needed: ['입력할 비밀값', '개'] };

  // 공용 요청 함수 하나(requestJ) — 불러오기는 MCP 연결 검사를 하므로 3분, 내보내기는 파일 이름 머리글이 필요하다. 서버 사유 칸(detail)은 그대로 쓴다
  // 누가 했나 = 이 PC의 담당자. 서버는 비어 있으면 400 으로 거절한다(inbox.actor_or_400) — 못 읽었으면 보내지 않고 까닭을 말한다
  function actor() {
    const id = window.hydInbox?.me?.()?.id;
    if (!id) throw Object.assign(new Error('담당자 정보를 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.'), { detail: {} });
    return id;
  }
  async function call(path, body) {
    try {
      return await requestJ(API.process + path, { timeout: 180000, withHeaders: true,
        ...(body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
    } catch (e) { if (!e.detail || typeof e.detail !== 'object') e.detail = {}; throw e; }
  }

  const counts = s => Object.entries(COUNT_WORDS).filter(([k]) => s && s[k]).map(([k, [w, unit]]) => `${w} ${s[k]}${unit}`).join(' · ') || '내가 만든 것 없음(기준 그대로)';
  // 출발본에는 기본 제공 흐름(시작할 때 설치되는 흐름)의 지금 판본도 담긴다(불러오기가 흐름을 모두 내리고 파일대로 다시 세우기 때문이다).
  // 서버 요약(summary)이 내가 만든 것(flows · flow_versions · deployments)과 기본 제공 흐름(provided_flows)을 갈라 센다 — 화면은 그 수를 그대로 말한다
  const bundleCounts = bundle => { const s = bundle.summary || {}; return counts(s) + (s.provided_flows ? ` · 함께 담긴 기본 제공 흐름 ${s.provided_flows}개(지금 배포된 판본)` : ''); };
  // [기준으로 되돌리기]가 지우는 것과 남기는 것 — 절 문구와 확인 창이 이 한 곳을 쓴다. 서버 config_bundle.py 가 하는 일 그대로다: 단계는 RESET_STEPS(지식 → 배포 → 흐름 →
  // 에이전트 → 도구 서버 → 질문 · 채점 · 시험 기록), 남기는 것은 RESET_KEPT. 서버가 범위를 바꾸면 여기만 고친다. 실제로 지운 것 · 남긴 것은 응답(removed · kept · base_missing)을 그대로 보인다
  const RESET_REMOVES = '내가 적재한 문서의 지식(기본 제공 판으로 돌아갑니다) · 업무 DB 표 정의 · 화면에서 만든 조치 방법, 내가 만든 AI 에이전트 · 스킬 · 역할 · 단계 배정 · 도구 서버 · 비밀 값, 내가 가져온 흐름과 그 배포, 끝난 질문 기록, 판단 채점의 정답표와 실행 기록, 에이전트 시험 비교 기록';
  const RESET_KEEPS = [
    ['기본 제공 에이전트 · 스킬 · 역할 · 도구 서버 · 흐름과 기본 제공 문서의 지식', '그대로 둡니다'],
    ['처리 건과 처리 건 기록', '그대로 둡니다. 지운 흐름으로 끝난 처리 건만 목록에서 숨깁니다'],
    ['모의 업무 시스템에 생긴 발주 · 정비 요청과 가상 설비의 상태', '「유압 설비 › 결함 시뮬레이션」의 [설비 초기화] · [업무 데이터 초기화]로 되돌립니다'],
  ];
  const RESET_NOTE = '내가 만든 구성과 넣은 지식은 처음 상태가 됩니다. 처리 건 기록과 모의 업무 시스템의 기록은 남습니다.';
  const SERVERS = 'tool_servers.register';               // 도구 서버를 만들 수 없는 단계에서는 되돌리기가 내 도구 서버와 비밀 값을 지우지 않는다(서버 mcp_reset 의 locked)
  // 되돌리는 범위 — 「내가 만든 것을 지운다」는 포털에서 이 한 곳뿐이다(흐름 · 에이전트 · 도구 연결 화면은 여기로 보낸다). 종류 하나만 되돌리는 것은 그 종류의 서버 API 를 그대로 부른다.
  // [키, 이름, 지우는 것과 남는 것, 요청, 결과 문장(응답 → 글), 수업 경계 행동 키(막힌 단계면 단추가 꺼지고 까닭이 보인다)]
  const josa = (word, pair) => window.hydWords.josa(word, pair);
  const SCOPES = [
    ['all', '전체', RESET_REMOVES],
    ['agents', 'AI 에이전트 · 스킬 · 역할 · 단계 배정', '내가 만든 에이전트와 스킬, 스킬 붙이기, 역할, 단계 배정을 지웁니다. 흐름이 쓰는 역할과 기본 제공 에이전트 · 역할은 남습니다.',
      by => postJ(API.process + '/api/agents/reset', { by }),
      o => { const removed = [['에이전트', o.agents, '개'], ['스킬', o.skills, '개'], ['스킬 붙이기', o.attachments, '건'], ['역할', o.roles, '개'], ['단계 배정', o.assignments, '건']].filter(([, n]) => n > 0).map(([name, n, unit]) => `${name} ${n}${unit}`);
        return (removed.length ? `되돌렸습니다. 내가 만든 ${removed.join(', ')}${josa(removed[removed.length - 1], '을/를')} 지웠습니다.` : '되돌렸습니다. 지울 것이 없었습니다.')
          + ((o.kept_roles || []).length ? ` 흐름이 쓰는 역할 ${o.kept_roles.length}개는 남겼습니다.` : '') + ((o.returned_tasks || []).length ? ` 열려 있던 단계 ${o.returned_tasks.length}건은 기본 담당으로 돌아갔습니다.` : ''); }],
    ['mcp', '도구 서버 · 비밀 값', '내가 등록한 서버와 포털 밖에서 추가한 서버, 모든 연결 검사 기록(기본 제공 서버의 것 포함), 비밀 값을 지웁니다. 기본 제공 서버는 남고, 지운 서버를 도구로 붙였던 에이전트는 그 서버 없이 실행됩니다.',
      by => postJ(API.process + '/api/mcp/reset', { by }),
      r => `되돌렸습니다. 서버 ${r.removed_servers.length}개, 검사 기록 ${r.removed_checks}개, 비밀 값 ${r.removed_secrets}개를 지웠습니다.`, 'tool_servers.register'],
    ['flows', '가져온 흐름 · 판본', '내가 가져온 흐름과 판본, 단계 설정 초안을 지웁니다. 기준 흐름과, 지금 경보에 배포된 흐름(기본 제공 포함)은 남습니다.',
      by => postJ(API.process + '/api/flows/reset', { by }),
      r => `되돌렸습니다. 판본 ${r.versions}개와 초안 ${r.drafts}개를 지웠습니다.` + ((r.kept || []).length ? ` 배포 중인 흐름 ${r.kept.length}개(${r.kept.join(', ')})는 남겼습니다.` : '')],
    ['deploy', '경보에 배포한 흐름', '내가 배포한 흐름만 경보 경로에서 내립니다. 기본 제공 흐름은 남고 그 운영 판본은 기준 판본으로 돌아갑니다. 등록한 판본과 열린 처리 건은 그대로입니다.',
      by => postJ(API.process + '/api/flows/deploy-reset', { by, reason: null }),
      r => r.message],
  ];

  function render(el) {
    // 세 가지 일을 위에서 아래로: 받기 → 불러오기 → 되돌리기. 일마다 판의 한 절(키트 .panel-sec) — 제목 · 한 문장 · 단추 하나, 그 아래에 진행(실시간 상자)과 결과
    const part = (icon, title, note, body) => `<div class="panel-sec"><h3>${UI.icon(icon)}${title}</h3><p class="muted">${note}</p>${body}</div>`;
    const foot = (button, msgId) => `<footer class="form-foot"><span class="muted" id="${msgId}" role="status"></span>${button}</footer>`;
    el.innerHTML = '<div class="panel-sec"><div id="studentCasesView"></div></div>' +
      part('download', '출발본 내보내기', '내가 만든 구성을 파일 하나로 받습니다. 기본 제공 에이전트 · 스킬 · 도구 서버와 비밀값은 담기지 않습니다.',
        foot(`<button type="button" class="btn" data-variant="outline" id="cfgExport">${UI.icon('download')}파일 받기</button>`, 'cfgExportMsg')) +
      part('upload', '출발본 불러오기', '출발본 파일을 올리면 지금 구성을 기준으로 되돌린 뒤 파일대로 다시 세웁니다.',
        `<div role="group" class="field"><label for="cfgFile">출발본 파일(.json)</label><input type="file" id="cfgFile" accept=".json,application/json"></div>
          <div id="cfgSecrets"></div>` +
          foot(`<button type="button" class="btn" id="cfgImport"${hydCourseAccess.attrs(IMPORT)}>${UI.icon('upload')}불러오기</button>`, 'cfgImportMsg') +
          `<div id="cfgImportResult" aria-live="polite"></div>`) +
      `<div class="panel-sec" id="cfgResetSec"><h3>${UI.icon(UI.acts.reset[1])}${H(UI.acts.reset[0])}</h3>` +
        `<div role="group" class="field"><label for="cfgResetScope">되돌릴 범위</label><select class="select" id="cfgResetScope">${SCOPES.map(([k, name]) => `<option value="${k}">${H(name)}</option>`).join('')}</select></div>` +
        `<div id="cfgResetWhat"></div>` +
        foot(UI.btn('reset', { variant: 'destructive', attrs: 'id="cfgReset"' }), 'cfgResetMsg') +
          `<div id="cfgResetResult" aria-live="polite"></div></div>`;
    const $ = id => el.querySelector('#' + id);
    hydCourseAccess.apply(el);                            // 막힌 단계면 [불러오기] 바로 뒤에 서버가 준 까닭 한 줄이 붙는다(courseAccess.js)
    window.hydStudentCases?.mount($('studentCasesView'));
    const msg = (id, text, bad) => { $(id).textContent = text; if (bad && text) $(id).dataset.tone = 'danger'; else delete $(id).dataset.tone; };
    // 결과 목록 한 줄(키트 .evid): 아이콘 + 굵은 이름 + 내용
    const lines = (icon, rows) => rows.length ? `<ul class="evid">${rows.map(([name, text]) => `<li>${UI.icon(icon)}<span><b>${H(name)}</b>${text ? ' ' + H(text) : ''}</span></li>`).join('')}</ul>` : '';
    const block = (title, body) => body ? `<div class="result"><div class="result-label">${title}</div>${body}</div>` : '';
    let pending = null;                                   // 비밀값을 기다리는 파일

    $('cfgExport').addEventListener('click', async () => {
      const end = hydLive.busy($('cfgExport'), '파일을 만드는 중');
      try {
        const { body, headers } = await call('/api/config/export');
        const name = (/filename="([^"]+)"/.exec(headers.get('Content-Disposition') || '') || [])[1] || 'hyd-starter.json';
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' }));
        a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
        msg('cfgExportMsg', `받았습니다 — ${bundleCounts(body)}` + (body.not_included.length ? ` · 담지 않은 것 ${body.not_included.length}건: ${body.not_included.map(x => x.what + ' — ' + x.reason).join(' / ')}` : ''));
      } catch (e) { msg('cfgExportMsg', e.message, true); }
      finally { end(false); }
    });

    function secretForm(needs) {
      $('cfgSecrets').innerHTML = UI.section('비밀값 입력', needs.map(n => n.slots.map(s =>
        UI.field({ label: `${hydWords.serverName(n.server)} — ${s.label}`, input: `<input type="password" autocomplete="off" data-server="${H(n.server)}" data-slot="${H(s.slot)}">`,
          hint: '파일에는 담지 않은 값입니다' })).join('')).join('')) +
        `<footer class="form-foot"><button type="button" class="btn" data-variant="outline" id="cfgSkip"${hydCourseAccess.attrs(IMPORT)}>비밀값이 없는 서버만 건너뛰고 불러오기</button></footer>`;
      $('cfgSkip').addEventListener('click', () => run(true));
      hydCourseAccess.apply(el);
    }
    function secretsFromForm() {
      const out = {};
      el.querySelectorAll('#cfgSecrets input[data-slot]').forEach(i => { if (i.value) (out[i.dataset.server] = out[i.dataset.server] || {})[i.dataset.slot] = i.value; });
      return out;
    }
    function showResult(r) {
      $('cfgImportResult').innerHTML = block(`적용한 것 ${r.applied.reduce((n, a) => n + a.count, 0)}건 · 건너뛴 것 ${r.skipped.length}건`,
        lines('check', r.applied.map(a => [`${a.label} ${a.count}건`, (a.items || []).join(' · ')])) + lines('minus', r.skipped.map(s => [s.what, '건너뜀 — ' + s.reason])));
    }
    // 실패: 어디서 왜 멈췄는지와, 불러오기 전 상태로 되돌렸는지를 진행 목록이 있던 자리에 남긴다
    function showFailure(d) {
      const parts = [];
      if (d.problems) parts.push(block('파일에서 고칠 곳', lines('x', d.problems.map(p => [p.where, p.reason]))));
      if (d.blocking) parts.push(block('막은 것', lines('x', d.blocking.map(b => [b.reason, '']))));
      if (d.failed_label) {
        parts.push(block('멈춘 단계', lines('x', [[d.failed_label, '']])));
        if (d.applied && d.applied.length) parts.push(block('그 전에 적용된 단계', lines('check', d.applied.map(a => [a.label, `${a.count}건`]))));
        if (d.partially_applied && d.partially_applied.length) parts.push(block('멈춘 단계에서 들어간 것', lines('circle-dot', d.partially_applied.map(x => [x, '']))));
        if (d.not_applied && d.not_applied.length) parts.push(block('적용하지 않은 단계', lines('circle-dashed', d.not_applied.map(s => [s.label, '']))));
        parts.push(`<p>${UI.chipText(d.rolled_back ? '되돌림' : '되돌리지 못함', d.rolled_back ? 'success' : 'danger')} ${d.rolled_back ? '불러오기 전 상태로 되돌렸습니다.' : '불러오기 전 상태로 되돌리지 못했습니다. ' + H(d.rollback_error || '')}</p>`);
      }
      $('cfgImportResult').innerHTML = parts.join('');
    }
    // 되돌리기 결과: 실제로 지운 것(removed) · 남긴 것(kept) · 지금 없는 기본 제공 문서(base_missing)를 서버가 준 말 그대로. 단계별 결과는 접어 둔다
    function resetResult(r) {
      const removed = r.removed || [], kept = r.kept || [], missing = r.base_missing || [], steps = r.steps || [];
      return block('지운 것', removed.length ? lines('check', removed.map(x => [x, ''])) : '<p class="muted">지울 것이 없었습니다. 기록(끝난 질문 · 판단 채점 · 시험 비교)만 비웠습니다.</p>')
        + block('남긴 것', lines('circle-dashed', kept.map(x => [x, ''])))
        + (missing.length ? `<div class="alert" data-reset-missing>${UI.icon('triangle-alert')}<h2>기본 제공 문서 ${missing.length}개의 지식이 지금 없습니다</h2><section>${H(missing.join(', '))} — 시작 파일을 다시 실행하면 다시 적재됩니다.</section></div>` : '')
        + (steps.length ? UI.fold(`단계별 결과<span class="muted num">${steps.length}</span>`, lines('check', steps.map(s => [s.label, s.text]))) : '');
    }
    let importing = false;                                // 불러오기 · 건너뛰고 불러오기는 한 번에 하나(두 번 누름)
    async function run(skip) {
      if (!pending) { msg('cfgImportMsg', '출발본 파일을 고르세요', true); return; }
      if (importing) return;
      importing = true;
      // 서버는 「파일 검사 → 지금 구성 보관 → 되돌리기 → 파일 내용을 순서대로 적용 → 다시 읽어 대조」의 단계가 시작 · 끝날 때마다 진행 기록에 적는다
      const end = hydLive.busy($('cfgImport'), '불러오는 중'); if ($('cfgSkip')) $('cfgSkip').disabled = true;
      msg('cfgImportMsg', '');
      const track = hydLive.track({ text: '출발본을 불러오는 중', hint: '지금 구성을 기준으로 되돌리고, 파일 내용을 순서대로 적용하고, 도구 서버 연결을 검사한 뒤 다시 읽어 대조합니다(길면 3분).' });
      track.mount($('cfgImportResult'));
      try {
        const { body } = await call('/api/config/import', { bundle: pending, secrets: secretsFromForm(), skip_missing_secrets: !!skip, by: actor(), request_id: track.id });
        msg('cfgImportMsg', body.message); $('cfgSecrets').innerHTML = ''; showResult(body);
        UI.toast(body.message, { tone: 'ok' });
      } catch (e) {
        msg('cfgImportMsg', e.message, true); showFailure(e.detail || {});
        if (e.detail && e.detail.needs_secrets && !e.detail.problems) secretForm(e.detail.needs_secrets);
      } finally { track.stop(); importing = false; end(false); if ($('cfgSkip')) $('cfgSkip').disabled = false; hydCourseAccess.apply(el); }
    }
    $('cfgFile').addEventListener('change', async () => {
      pending = null; $('cfgSecrets').innerHTML = ''; $('cfgImportResult').innerHTML = '';
      const f = $('cfgFile').files[0]; if (!f) return;
      try {
        pending = hydDefinitions.readObject(await f.text(), '출발본 파일');   // 틀린 자리를 한국어로(줄 · 글자) — 브라우저의 영문 오류 문장을 붙이지 않는다
        msg('cfgImportMsg', `${f.name} — ${bundleCounts(pending)}`);
      } catch (e) { msg('cfgImportMsg', `${e.message} — [파일 받기]로 받은 출발본 파일 그대로인지 확인하세요.`, true); }
    });
    $('cfgImport').addEventListener('click', async () => {
      if (!pending) { msg('cfgImportMsg', '출발본 파일을 고르세요', true); return; }
      const yes = await UI.confirm({ title: '출발본을 불러올까요?', body: '지금 내가 만든 구성(AI 에이전트 · 스킬 · 역할 · 단계 배정 · 도구 서버 · 흐름 · 배포)을 지우고 파일 내용으로 다시 세웁니다. 기본 제공 흐름(시작할 때 설치되는 흐름)도 지우고 파일 내용대로 다시 세웁니다. 지운 흐름으로 끝난 처리 건은 [처리 건] 목록에서 숨겨집니다. 진행 중인 처리 건이 있으면 아무것도 바꾸지 않고 멈춥니다. 기준 구성, 비밀 값, 질문 · 판단 채점 · 에이전트 시험 비교 기록은 그대로입니다.', ok: '불러오기' });
      if (yes) run(false);
    });
    // 고른 범위가 지우는 것과 남기는 것(전체는 남는 것의 목록까지). 수업 경계에 막힌 범위는 단추가 꺼지고 서버가 준 까닭이 보인다
    const scopeOf = () => SCOPES.find(x => x[0] === $('cfgResetScope').value) || SCOPES[0];
    const paintScope = ev => {
      const [key, , what, , , action] = scopeOf(), why = action ? hydCourseAccess.blocked(action) : '';
      const locked = key === 'all' ? hydCourseAccess.blocked(SERVERS) : '';      // 전체 되돌리기는 막히지 않는다 — 그 단계에서는 도구 서버와 비밀 값만 남긴다
      $('cfgResetWhat').innerHTML = key === 'all'
        ? `<p class="muted"><b>지우는 것</b> ${H(what)}.</p><p class="muted" data-reset-keeps><b>남는 것</b> ${H(RESET_KEEPS.map(([w]) => w).join(', '))}.</p>`
          + (locked ? `<p class="muted" data-reset-locked role="status" title="${H(locked)}">지금은 도구 서버를 등록할 수 없는 단계라 내 도구 서버와 비밀 값도 남깁니다.</p>` : '')
        : `<p class="muted">${H(what)}</p>` + (why ? `<p class="muted" data-tone="danger" role="status">${H(why)}</p>` : '');
      $('cfgReset').disabled = !!why;
      if (ev) { msg('cfgResetMsg', ''); $('cfgResetResult').innerHTML = ''; }      // 범위를 바꿨을 때만 앞 결과를 비운다(수업 단계 정보가 다시 읽힐 때는 그대로 둔다)
    };
    $('cfgResetScope').addEventListener('change', paintScope); paintScope();
    hydCourseAccess.onChange(() => paintScope());
    $('cfgReset').addEventListener('click', async () => {
      const [key, name, what, send, say] = scopeOf();
      if (key !== 'all') {      // 종류 하나만: 그 종류의 되돌리기 API 하나
        try { actor(); } catch (e) { msg('cfgResetMsg', e.message, true); return; }      // 담당자를 못 읽었으면 묻기 전에 멈춘다
        if (!await UI.confirm({ title: `${name}${josa(name, '을/를')} 기준으로 되돌릴까요?`, body: what, ok: '되돌리기', danger: true })) return;
        const end = hydLive.busy($('cfgReset'), '되돌리는 중');
        try {
          const text = say(await send(actor()));
          msg('cfgResetMsg', text); UI.toast(text, { tone: 'ok', timeout: 8000 });
          window.dispatchEvent(new CustomEvent('hyd-config-reset', { detail: { scope: key } }));      // 그 화면이 열려 있었으면 목록을 새로 읽는다
        } catch (e) { msg('cfgResetMsg', e.message, true); }
        finally { end(false); }
        return;
      }
      const yes = await UI.confirm({ title: '기준으로 되돌릴까요?', ok: '되돌리기', danger: true,
        body: `지우는 것: ${RESET_REMOVES}.\n\n남는 것:\n${RESET_KEEPS.map(([what, where]) => `· ${what} — ${where}`).join('\n')}${hydCourseAccess.blocked(SERVERS) ? '\n· 내 도구 서버와 비밀 값 — 지금은 도구 서버를 등록할 수 없는 단계라 지우지 않습니다' : ''}\n\n${RESET_NOTE} 먼저 출발본으로 받아 두면 구성은 다시 불러올 수 있습니다(지식 · 비밀 값 · 기록은 파일에 없습니다).` });
      if (!yes) return;
      const end = hydLive.busy($('cfgReset'), '되돌리는 중');
      $('cfgResetMsg').textContent = '';
      const track = hydLive.track({ text: '기준으로 되돌리는 중', hint: '내가 만든 것을 종류별로 차례로 지웁니다.' });
      track.mount($('cfgResetResult'));
      try {
        const { body } = await call('/api/config/reset', { by: actor(), request_id: track.id });
        msg('cfgResetMsg', '기준으로 되돌렸습니다'); $('cfgResetResult').innerHTML = resetResult(body);
        UI.toast(body.message, { tone: 'ok' });
        window.dispatchEvent(new CustomEvent('hyd-config-reset', { detail: { scope: 'all' } }));
      } catch (e) {
        msg('cfgResetMsg', e.message, true);
        const d = e.detail || {};
        // 지식 되돌리기가 도중에 멈췄으면 그때까지 되돌린 것(partial)도 말한다 — 「아무것도 바뀌지 않았다」로 읽히지 않게
        const p = d.partial || {}, part = [[(p.documents || []).length, '적재한 문서 판', '개'], [(p.skills || []).length, '화면에서 만든 조치 방법', '개'], [(p.ddl_batches || []).length, '업무 DB 표 정의 묶음', '개']].filter(([n]) => n).map(([n, w, u]) => [`${w} ${n}${u}`, '']);
        $('cfgResetResult').innerHTML = d.blocking ? block('막은 것', lines('x', d.blocking.map(b => [b.reason, ''])))
          : (d.done ? block('멈추기 전에 지운 단계', lines('check', d.done.map(x => [x.label, x.text || ''])) || '<p class="muted">없음</p>') : '')
            + block('멈춘 단계에서 이미 되돌린 것', lines('circle-dot', part));
      } finally { track.stop(); end(false); }
    });
  }

  // 다른 화면의 「관리에서 되돌리기」 링크([data-go-reset="범위"]): 관리 › 내 설정을 열고 그 범위를 골라 둔다(누르는 것은 사람이 한다)
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('[data-go-reset]'); if (!a) return;
    e.preventDefault();
    selectTab('admin');
    document.querySelector('#adminList [data-admin="configBundlePanel"]')?.click();
    const pick = document.getElementById('cfgResetScope'); if (!pick) return;
    pick.value = a.dataset.goReset; pick.dispatchEvent(new Event('change'));
    document.getElementById('cfgResetSec').scrollIntoView({ block: 'center' });
  });
  window.hydConfig = { mount: render };
  document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById('configBundleView'); if (!el) return;
    render(el);
    hydCourseAccess.onChange(() => hydCourseAccess.apply(el));      // 허용 범위가 늦게 와도 불러오기 단추와 까닭 글을 맞춘다
  });
})();
