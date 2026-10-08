/* B6 출발본: 내가 만든 구성(에이전트 · 스킬 · MCP · 업무분장 · 흐름 · 배정 · 배포)을 파일로 받기 · 파일로 불러오기 · 기준으로 되돌리기.
   API: GET /api/config/export · POST /api/config/import {bundle, secrets?, skip_missing_secrets?} · POST /api/config/reset
   불러오기는 "되돌리기 → 순서대로 적용 → 다시 읽어 대조"이고, 실패하면 어디서 왜 멈췄는지와 적용 전 상태로 되돌렸는지 보여 준다.
   비밀값(MCP 접속 헤더 · 환경변수의 토큰 등)은 파일에 없다 — 필요하면 여기서 입력하거나 그 서버만 건너뛴다. */
(function () {
  const H = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const base = () => (typeof API !== 'undefined' ? API.process : '');
  const COUNT_WORDS = { mcp_servers: 'MCP 서버', skills: '스킬', agents: '에이전트', role_members: '업무분장', flows: '흐름',
    flow_versions: '흐름 판본', assignments: '단계 배정', deployments: '배포', secrets_needed: '입력할 비밀값' };

  async function call(path, body) {
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 180000);      // 불러오기는 MCP 연결 검사를 하므로 길게
    try {
      const r = await fetch(base() + path, body === undefined ? { cache: 'no-store', signal: ctl.signal }
        : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctl.signal });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) {
        const d = j.detail, e = new Error(typeof d === 'string' ? d : (d && d.reason) || `요청 실패 (${r.status})`);
        e.detail = d && typeof d === 'object' ? d : {}; e.status = r.status; throw e;
      }
      return { body: j, headers: r.headers };
    } catch (e) {
      if (e.name === 'AbortError') throw new Error('응답 시간 초과 — 잠시 뒤 상태를 확인하세요');
      throw e;
    } finally { clearTimeout(timer); }
  }

  const list = items => items && items.length ? `<ul>${items.map(x => `<li>${H(x)}</li>`).join('')}</ul>` : '';
  const counts = s => Object.entries(COUNT_WORDS).filter(([k]) => s && s[k]).map(([k, w]) => `${w} ${s[k]}`).join(' · ') || '내가 만든 것 없음(기준 그대로)';

  function render(el) {
    el.innerHTML =
      UI.card({ title: '출발본 내보내기', sub: '지금 내가 만든 구성만 파일 하나로 받습니다. 기준 구성과 비밀값은 들어가지 않습니다.',
        body: `<div class="form-actions"><span class="form-msg" id="cfgExportMsg" role="status"></span><button type="button" class="btn primary" id="cfgExport">파일 받기</button></div>` }) +
      UI.card({ title: '출발본 불러오기', sub: '강사가 준 출발본 파일을 올리면 지금 구성을 기준으로 되돌린 뒤 파일 내용으로 다시 세웁니다. 망쳐도 다시 불러오면 됩니다.',
        body: `<div class="form-grid"><div class="field wide"><label for="cfgFile">출발본 파일(.json)</label><input type="file" id="cfgFile" accept=".json,application/json"></div></div>
          <div id="cfgSecrets"></div>
          <div class="form-actions"><span class="form-msg" id="cfgImportMsg" role="status"></span><button type="button" class="btn primary" id="cfgImport">불러오기</button></div>
          <div id="cfgImportResult"></div>` }) +
      UI.card({ title: '기준으로 되돌리기', sub: '내가 만든 에이전트 · 스킬 · 배정 · 업무분장 · MCP 서버 · 흐름 · 배포와 끝난 질문 기록을 지웁니다. 기준은 그대로입니다.',
        body: `<div class="form-actions"><span class="form-msg" id="cfgResetMsg" role="status"></span><button type="button" class="btn danger" id="cfgReset">기준으로 되돌리기</button></div>
          <div id="cfgResetResult"></div>` });
    const $ = id => el.querySelector('#' + id);
    const msg = (id, text, bad) => { $(id).textContent = text; $(id).className = 'form-msg ' + (bad ? 'neg' : 'pos'); };
    let pending = null;                                   // 비밀값을 기다리는 파일

    $('cfgExport').addEventListener('click', async () => {
      $('cfgExport').disabled = true;
      try {
        const { body, headers } = await call('/api/config/export');
        const name = (/filename="([^"]+)"/.exec(headers.get('Content-Disposition') || '') || [])[1] || 'hyd-starter.json';
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' }));
        a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 5000);
        msg('cfgExportMsg', `받았습니다 — ${counts(body.summary)}` + (body.not_included.length ? ` · 담지 않은 것 ${body.not_included.length}건: ${body.not_included.map(x => x.what + ' — ' + x.reason).join(' / ')}` : ''));
      } catch (e) { msg('cfgExportMsg', e.message, true); }
      finally { $('cfgExport').disabled = false; }
    });

    function secretForm(needs) {
      $('cfgSecrets').innerHTML = UI.section('비밀값 입력', needs.map(n => n.slots.map(s =>
        UI.field({ label: `${n.server} · ${s.label}`, input: `<input type="password" autocomplete="off" data-server="${H(n.server)}" data-slot="${H(s.slot)}">`,
          hint: '파일에는 담지 않은 값입니다' })).join('')).join('')) +
        `<div class="form-actions"><button type="button" class="btn" id="cfgSkip">비밀값이 없는 서버만 건너뛰고 불러오기</button></div>`;
      $('cfgSkip').addEventListener('click', () => run(true));
    }
    function secretsFromForm() {
      const out = {};
      el.querySelectorAll('#cfgSecrets input[data-slot]').forEach(i => { if (i.value) (out[i.dataset.server] = out[i.dataset.server] || {})[i.dataset.slot] = i.value; });
      return out;
    }
    function showResult(r) {
      $('cfgImportResult').innerHTML = UI.fold(`적용한 것 ${r.applied.reduce((n, a) => n + a.count, 0)}건 · 건너뛴 것 ${r.skipped.length}건`,
        r.applied.map(a => `<p><b>${H(a.label)}</b> ${a.count}건</p>${list(a.items)}`).join('') +
        (r.skipped.length ? `<p><b>건너뛴 것</b></p>${list(r.skipped.map(s => `${s.what} — ${s.reason}`))}` : ''), { open: true });
    }
    function showFailure(d) {
      const parts = [];
      if (d.problems) parts.push(`<p><b>파일에서 고칠 곳</b></p>${list(d.problems.map(p => `${p.where}: ${p.reason}`))}`);
      if (d.blocking) parts.push(`<p><b>막은 것</b></p>${list(d.blocking.map(b => b.reason))}`);
      if (d.failed_label) {
        parts.push(`<p><b>멈춘 단계</b> ${H(d.failed_label)}</p>`);
        if (d.applied && d.applied.length) parts.push(`<p><b>그 전에 적용된 단계</b></p>${list(d.applied.map(a => `${a.label} ${a.count}건`))}`);
        if (d.partially_applied && d.partially_applied.length) parts.push(`<p><b>멈춘 단계에서 들어간 것</b></p>${list(d.partially_applied)}`);
        if (d.not_applied && d.not_applied.length) parts.push(`<p><b>적용하지 않은 단계</b></p>${list(d.not_applied.map(s => s.label))}`);
        parts.push(`<p>${d.rolled_back ? UI.chipText('불러오기 전 상태로 되돌림', 'success') : UI.chipText('불러오기 전 상태로 되돌리지 못함', 'danger') + ' ' + H(d.rollback_error || '')}</p>`);
      }
      $('cfgImportResult').innerHTML = parts.length ? UI.fold('왜 안 됐는지', parts.join(''), { open: true }) : '';
    }
    async function run(skip) {
      if (!pending) { msg('cfgImportMsg', '출발본 파일을 고르세요', true); return; }
      $('cfgImport').disabled = true; msg('cfgImportMsg', '불러오는 중 — MCP 서버 연결 검사를 하므로 조금 걸립니다');
      try {
        const { body } = await call('/api/config/import', { bundle: pending, secrets: secretsFromForm(), skip_missing_secrets: !!skip });
        msg('cfgImportMsg', body.message); $('cfgSecrets').innerHTML = ''; showResult(body);
        if (UI.toast) UI.toast(body.message, { tone: 'pos' });
      } catch (e) {
        msg('cfgImportMsg', e.message, true); showFailure(e.detail || {});
        if (e.detail && e.detail.needs_secrets && !e.detail.problems) secretForm(e.detail.needs_secrets);
      } finally { $('cfgImport').disabled = false; }
    }
    $('cfgFile').addEventListener('change', async () => {
      pending = null; $('cfgSecrets').innerHTML = ''; $('cfgImportResult').innerHTML = '';
      const f = $('cfgFile').files[0]; if (!f) return;
      try {
        pending = JSON.parse(await f.text());
        msg('cfgImportMsg', `${f.name} — ${counts(pending.summary)}`);
      } catch (e) { msg('cfgImportMsg', `JSON 파일이 아닙니다: ${e.message}`, true); }
    });
    $('cfgImport').addEventListener('click', async () => {
      if (!pending) { msg('cfgImportMsg', '출발본 파일을 고르세요', true); return; }
      const yes = await UI.confirm({ title: '출발본을 불러올까요?', body: '지금 내가 만든 구성을 지우고 파일 내용으로 다시 세웁니다. 기준 구성과 질문 기록은 그대로입니다.', ok: '불러오기' });
      if (yes) run(false);
    });
    $('cfgReset').addEventListener('click', async () => {
      const yes = await UI.confirm({ title: '기준으로 되돌릴까요?', body: '내가 만든 구성을 모두 지웁니다. 먼저 출발본으로 받아 두면 다시 불러올 수 있습니다.', ok: '되돌리기', danger: true });
      if (!yes) return;
      $('cfgReset').disabled = true;
      try {
        const { body } = await call('/api/config/reset', {});
        msg('cfgResetMsg', body.message); $('cfgResetResult').innerHTML = UI.fold('지운 것', list(body.steps.map(s => `${s.label}: ${s.text}`)));
        if (UI.toast) UI.toast(body.message, { tone: 'pos' });
      } catch (e) {
        msg('cfgResetMsg', e.message, true);
        const d = e.detail || {};
        $('cfgResetResult').innerHTML = d.blocking ? list(d.blocking.map(b => b.reason)) : d.done ? `<p>지운 단계: ${H(d.done.map(x => x.label).join(', ') || '없음')}</p>` : '';
      } finally { $('cfgReset').disabled = false; }
    });
  }

  window.hydConfig = { mount: render, counts };
  document.addEventListener('DOMContentLoaded', () => { const el = document.getElementById('configBundleView'); if (el) render(el); });
})();
