/* 인스턴스 진행 단계 — 정의의 순서와 업무 상태로 "지금 어디쯤인지" 를 만든다.
   원본: process-gpt-vue3/src/shared/instanceSteps.js (uengine-oss). ES module 을 브라우저 전역(window.hydSteps)으로만 바꿨고
   규칙은 그대로다: 엔진이 TODO 예정 업무를 미리 만들어 두므로 TODO 는 '진행 중' 이 아니고, 고르는 게이트웨이에서 가지 않은
   가지는 skipped 로 두며, 분기는 묶음으로 그린다. */
(function () {
  /** 이미 시작됐지만 아직 끝나지 않은 업무의 상태. TODO 는 넣지 않는다(예정 업무). */
  const LIVE_STATUSES = new Set(['IN_PROGRESS', 'SUBMITTED', 'PENDING', 'NEW', 'RUNNING', 'Running']);

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
  function branchLanes(gateways, graph) {
    const { next, depth, backEdges } = graph;
    const reach = (head) => {
      const seen = new Set();
      const stack = [head];
      while (stack.length) {
        const id = stack.pop();
        if (seen.has(id)) continue;
        seen.add(id);
        (next.get(id) || []).forEach((to) => { if (!backEdges.has(`${id}>${to}`)) stack.push(to); });
      }
      return seen;
    };
    const laneOf = new Map();
    (gateways || [])
      .filter((g) => g && CHOOSING_GATEWAYS.has(g.type) && (next.get(g.id) || []).length > 1)
      .sort((a, b) => (depth.get(a.id) ?? Infinity) - (depth.get(b.id) ?? Infinity))
      .forEach((g) => {
        const heads = next.get(g.id);
        const reached = heads.map(reach);
        reached.forEach((set, lane) => {
          set.forEach((id) => {
            if (laneOf.has(id)) return;
            if (reached.some((other, j) => j !== lane && other.has(id))) return;
            laneOf.set(id, { id: g.id, name: g.name || '', lane, lanes: heads.length });
          });
        });
      });
    return laneOf;
  }

  /** 단계 목록. 같은 단계를 다시 한 경우는 가장 최근 업무의 상태를 쓴다. 가지 않은 가지와 끝난 뒤 남은 예정 단계는 skipped. */
  function buildSteps({ activities, sequences, events, gateways, workList, whoOf, mineTaskId, finished }) {
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
    const lanes = branchLanes(gateways, graph);
    return orderActivities(activities, sequences, null, graph).map((activity) => {
      const work = latest.get(activity.id);
      let state = work ? stepStateOf(work.status) : 'todo';
      if (state === 'todo' && (finished || untaken.has(activity.id))) state = 'skipped';
      return {
        id: activity.id,
        name: activity.name || activity.id,
        who: (work && whoOf ? whoOf(work) : '') || activity.role || '',
        state,
        status: work ? work.status : null,
        taskId: work ? work.taskId : null,
        mine: !!(work && mineTaskId && work.taskId === mineTaskId),
        branch: lanes.get(activity.id) || null
      };
    });
  }

  /** 화면에 그릴 줄 — 가지 밖의 단계는 한 줄, 한 게이트웨이의 가지들은 한 묶음. */
  function groupSteps(steps) {
    const out = [];
    const groups = new Map();
    (steps || []).forEach((step) => {
      const b = step.branch;
      if (!b) { out.push({ type: 'step', step }); return; }
      let group = groups.get(b.id);
      if (!group) {
        group = { type: 'branch', id: b.id, name: b.name, lanes: Array.from({ length: b.lanes }, (_, lane) => ({ lane, state: 'open', steps: [] })) };
        groups.set(b.id, group);
        out.push(group);
      }
      group.lanes[b.lane].steps.push(step);
    });
    groups.forEach((group) => {
      group.lanes = group.lanes.filter((l) => l.steps.length > 0);
      group.lanes.forEach((l) => {
        if (l.steps.some((s) => s.state === 'done' || s.state === 'current')) l.state = 'taken';
        else if (l.steps.every((s) => s.state === 'skipped')) l.state = 'skipped';
      });
      group.decided = group.lanes.some((l) => l.state === 'taken');
    });
    return out;
  }

  /** 한 줄 요약 — 지금 단계, 끝난 수, 전체 수(건너뛴 단계는 세지 않고, 고르기 전 분기는 가장 긴 가지만큼만). */
  function summarizeSteps(steps) {
    const list = steps || [];
    const items = groupSteps(list);
    let total = 0;
    let next = null;
    items.forEach((item) => {
      if (item.type === 'step') {
        if (item.step.state !== 'skipped') total += 1;
        if (!next && item.step.state === 'todo') next = item.step;
        return;
      }
      const live = item.lanes.filter((l) => l.state !== 'skipped');
      const counted = item.decided ? live.filter((l) => l.state === 'taken') : live;
      const size = (l) => l.steps.filter((s) => s.state !== 'skipped').length;
      total += item.decided ? counted.reduce((n, l) => n + size(l), 0) : Math.max(0, ...counted.map(size));
      if (next) return;
      if (!item.decided && live.length > 1) { next = { name: item.name || `${live.length}갈래 중 하나`, branch: true }; return; }
      const todo = counted.flatMap((l) => l.steps).find((s) => s.state === 'todo');
      if (todo) next = todo;
    });
    const done = list.filter((s) => s.state === 'done').length;
    const current = list.find((s) => s.state === 'current') || null;
    if (current) next = null;
    return { total, done, current, next, finished: list.length > 0 && !current && !next };
  }

  window.hydSteps = { LIVE_STATUSES, stepStateOf, orderActivities, untakenBranches, buildSteps, groupSteps, summarizeSteps };
})();
