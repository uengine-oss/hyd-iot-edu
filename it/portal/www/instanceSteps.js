/* 인스턴스 진행 단계 — 정의의 순서와 업무 상태로 "지금 어디쯤인지" 를 만든다.
   원본: process-gpt-vue3/src/shared/instanceSteps.js (uengine-oss). ES module 을 브라우저 전역(window.hydSteps)으로만 바꿨고
   규칙은 그대로다: 엔진이 TODO 예정 업무를 미리 만들어 두므로 TODO 는 '진행 중' 이 아니고, 고르는 게이트웨이에서 가지 않은
   가지는 skipped 로 둔다(포털은 진행 중 단계 수와 흐름도 칸의 상태에만 쓴다 — instances.js · flow.js). */
(function () {
  /** 이미 시작됐지만 아직 끝나지 않은 작업 행의 상태 — 엔진(procsvc/engine.py)의 살아 있는 상태와 같다. TODO 는 넣지 않는다(예정 업무). */
  const LIVE_STATUSES = new Set(['IN_PROGRESS', 'SUBMITTED', 'PENDING']);

  /** 업무 상태 → 단계 상태('done' | 'current' | 'skipped' | 'todo'). */
  function stepStateOf(status) {
    if (status === 'DONE') return 'done';
    if (status === 'CANCELLED') return 'skipped';
    if (LIVE_STATUSES.has(status)) return 'current';
    return 'todo';
  }

  /** 여러 갈래 중 고르는 게이트웨이. 병렬 게이트웨이는 모든 가지를 함께 여니 넣지 않는다. */
  const CHOOSING_GATEWAYS = new Set(['exclusiveGateway', 'inclusiveGateway', 'eventBasedGateway']);

  /** 흐름 그래프 — 다음 · 앞 노드와 '시작에서 가장 먼 거리'(깊이). 되돌아가는 흐름은 깊이에서 뺀다. */
  function flowGraph(sequences, events) {
    const next = new Map();
    const prev = new Map();
    (sequences || []).forEach((seq) => {
      if (!seq || !seq.source || !seq.target) return;
      if (!next.has(seq.source)) next.set(seq.source, []);
      next.get(seq.source).push(seq.target);
      if (!prev.has(seq.target)) prev.set(seq.target, []);
      prev.get(seq.target).push(seq.source);
    });
    const depth = new Map();
    const backEdges = new Set();
    const start = (events || []).find((e) => e && e.type === 'startEvent');
    if (!start || next.size === 0) return { next, prev, depth, backEdges };
    const visiting = new Set();
    const visited = new Set();
    const postorder = [];
    const visit = (id) => {
      visiting.add(id);
      (next.get(id) || []).forEach((to) => {
        if (visiting.has(to)) backEdges.add(`${id}>${to}`);
        else if (!visited.has(to)) visit(to);
      });
      visiting.delete(id);
      visited.add(id);
      postorder.push(id);
    };
    visit(start.id);
    depth.set(start.id, 0);
    postorder.reverse().forEach((from) => {
      const d = depth.get(from);
      if (d === undefined) return;
      (next.get(from) || []).forEach((to) => {
        if (backEdges.has(`${from}>${to}`)) return;
        if ((depth.get(to) ?? -1) < d + 1) depth.set(to, d + 1);
      });
    });
    return { next, prev, depth, backEdges };
  }

  /** 정의에 적힌 흐름 순서대로 액티비티를 늘어놓는다 (시작에서 가장 먼 거리 = 단계의 깊이). */
  function orderActivities(activities, sequences, events, graph = flowGraph(sequences, events)) {
    const all = (activities || []).filter(Boolean);
    if (all.length === 0) return [];
    const { depth } = graph;
    if (depth.size === 0) return all.slice();
    const indexOf = new Map(all.map((a, i) => [a.id, i]));
    const reached = all.filter((a) => depth.has(a.id));
    reached.sort((a, b) => depth.get(a.id) - depth.get(b.id) || indexOf.get(a.id) - indexOf.get(b.id));
    return [...reached, ...all.filter((a) => !depth.has(a.id))];
  }

  /** 가지 않게 된 가지의 노드 id — 고르는 게이트웨이의 가지 가운데 하나라도 시작됐으면 나머지 가지는 간 적 없는 가지다. */
  function untakenBranches({ sequences, gateways, started }) {
    const { next, prev } = flowGraph(sequences, []);
    const typeOf = new Map((gateways || []).filter(Boolean).map((g) => [g.id, g.type]));
    const branchStarted = (head) => {
      const seen = new Set();
      const stack = [head];
      while (stack.length) {
        const id = stack.pop();
        if (seen.has(id)) continue;
        seen.add(id);
        if (started.has(id)) return true;
        if (typeOf.has(id)) (next.get(id) || []).forEach((t) => stack.push(t));
      }
      return false;
    };
    const skipped = new Set();
    typeOf.forEach((type, gw) => {
      if (!CHOOSING_GATEWAYS.has(type)) return;
      const heads = next.get(gw) || [];
      const taken = heads.filter(branchStarted);
      if (taken.length === 0) return;
      heads.filter((h) => !taken.includes(h)).forEach((h) => skipped.add(h));
    });
    if (skipped.size === 0) return skipped;
    let grew = true;
    while (grew) {
      grew = false;
      prev.forEach((from, id) => {
        if (skipped.has(id) || started.has(id)) return;
        if (from.length > 0 && from.every((f) => skipped.has(f))) {
          skipped.add(id);
          grew = true;
        }
      });
    }
    return skipped;
  }

  /** 고르는 게이트웨이마다 가지(갈래)에 속한 노드 — 액티비티 id → { id, name, lane, lanes }. */
  /** 단계 목록. 같은 단계를 다시 한 경우는 가장 최근 업무의 상태를 쓴다. 가지 않은 가지와 끝난 뒤 남은 예정 단계는 skipped. */
  function buildSteps({ activities, sequences, events, gateways, workList, finished }) {
    const latest = new Map();
    const at = (x) => new Date((x && (x.endDate || x.startDate)) || 0).getTime();
    (workList || []).forEach((w) => {
      const key = w && (w.tracingTag || (w.task && w.task.activity_id));
      if (!key) return;
      const prev = latest.get(key);
      if (!prev || (w.generation || 0) > (prev.generation || 0)
          || ((w.generation || 0) === (prev.generation || 0) && at(w) >= at(prev))) latest.set(key, w);
    });
    const started = new Set();
    latest.forEach((w, id) => { if (stepStateOf(w.status) !== 'todo') started.add(id); });
    const untaken = untakenBranches({ sequences, gateways, started });
    const graph = flowGraph(sequences, [...(events || []), ...(gateways || [])]);
    return orderActivities(activities, sequences, null, graph).map((activity) => {
      const work = latest.get(activity.id);
      let state = work ? stepStateOf(work.status) : 'todo';
      if (state === 'todo' && (finished || untaken.has(activity.id))) state = 'skipped';
      return { id: activity.id, name: activity.name || activity.id, state, status: work ? work.status : null };
    });
  }

  window.hydSteps = { stepStateOf, buildSteps };
})();
