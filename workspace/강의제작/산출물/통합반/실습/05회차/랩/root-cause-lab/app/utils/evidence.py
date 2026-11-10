"""원문·그래프·기간 관측의 읽기 전용 도구. 업무 판정은 하지 않는다."""
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
import csv
import gzip
import hashlib
import json
import re
import sqlite3
import time


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        lines = [line for line in stream if not line.startswith('#')]
    return list(csv.DictReader(lines))


def moment(text):
    value = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('시각에는 +09:00 또는 Z를 붙입니다.')
    return value


def graph_errors(graph, schema, shape):
    errors, ids = [], {}
    for number, node in enumerate(graph.get('nodes', []), 1):
        identity = node.get('props', {}).get('id')
        if not identity or not isinstance(node.get('labels'), list):
            errors.append(f'nodes {number}: id 또는 labels 꼴 없음'); continue
        if identity in ids:
            errors.append(f'nodes {number}: 중복 ID {identity}')
        ids[identity] = node
    seen = set()
    for number, rel in enumerate(graph.get('rels', []), 1):
        a, b, kind = rel.get('a'), rel.get('b'), rel.get('type')
        if a not in ids or b not in ids:
            errors.append(f'rels {number}: 없는 끝점 {a} → {b}'); continue
        key = (a, kind, b)
        if key in seen:
            errors.append(f'rels {number}: 중복 관계 {key}')
        seen.add(key)
        contract = schema.get('relations', {}).get(kind, {})
        for side, identity in [('from', a), ('to', b)]:
            label = contract.get(side)
            if label and label != '기존 ID' and label not in ids[identity]['labels']:
                errors.append(f'rels {number}: {kind} {side} 방향/레이블 불일치 {identity}')
    names = shape.get('이름', {})
    for name in ['문서', '절', '지식', '지식의_출처']:
        if not names.get(name):
            errors.append(f'shape.json: 뜻 대응 {name} 없음')
    label = names.get('지식')
    for node in graph.get('nodes', []):
        if label in node.get('labels', []):
            props = node['props']
            missing = [name for name in ['doc_id', 'rev', 'section', 'line_start', 'line_end', 'quote'] if name not in props]
            if missing:
                errors.append(f"{props['id']}: 이 조회기의 출처 계약 미지원({', '.join(missing)})")
    return errors


class EvidenceStore:
    def __init__(self, root, graph_folder=None):
        self.root = Path(root).resolve()
        self.project = (self.root / 'data/source_manifest.json').is_file()
        self.data_dir = self.root / ('data' if self.project else '자료')
        self.input_dir = self.root / ('data' if self.project else '입력')
        self.output_dir = self.root / ('output' if self.project else '결과')
        graph_folder = Path(graph_folder) if graph_folder else self.input_dir / ('model' if self.project else 'ontology')
        graph_folder = graph_folder.resolve()
        self.graph_path = graph_folder / 'graph.json'
        self.graph_hash = sha(self.graph_path)
        self.graph_source = self.graph_path.relative_to(self.root).as_posix() if self.graph_path.is_relative_to(self.root) else '선택한 지식 입력/graph.json'
        self.graph = read_json(self.graph_path)
        self.schema = read_json(graph_folder / 'schema.json')
        self.shape = read_json(graph_folder / 'shape.json')
        errors = graph_errors(self.graph, self.schema, self.shape)
        if errors:
            raise ValueError('지식 입력 계약을 읽을 수 없습니다. 기본 제공판을 선택하거나 뜻 대응을 확인합니다.\n' + '\n'.join(errors))
        self.nodes = {node['props']['id']: node for node in self.graph['nodes']}
        self.sources = read_json(self.input_dir / 'source_manifest.json')
        self.manifest = read_json(self.data_dir / 'data_manifest.json')
        self.connection = None

    def inventory(self):
        return {'nodes': len(self.graph['nodes']), 'rels': len(self.graph['rels']),
                'labels': dict(Counter(label for n in self.graph['nodes'] for label in n['labels'])),
                'semantic_names': self.shape['이름'], 'documents': self.sources['documents'],
                'data': self.manifest, 'tools': TOOL_CONTRACT}

    def request(self, identity):
        matches = [r for r in read_csv(self.data_dir / 'requests.csv') if r['request_id'] == identity]
        if len(matches) != 1:
            raise ValueError(f'요청 ID {identity}: {len(matches)}건. {(self.data_dir / 'requests.csv').relative_to(self.root).as_posix()}를 확인합니다.')
        return matches[0]

    def graph_query(self, labels=None, ids=None, terms=None, relations=None, direction='both', depth=0, offset=0, limit=30):
        if direction not in ['out', 'in', 'both'] or not 0 <= int(depth) <= len(self.nodes):
            raise ValueError('direction은 out/in/both, depth는 음이 아닌 수입니다.')
        chosen = set(ids or [])
        if not chosen:
            for identity, node in self.nodes.items():
                if labels and not set(labels) & set(node['labels']): continue
                text = json.dumps(node['props'], ensure_ascii=False).lower()
                if terms and not all(t.lower() in text for t in terms): continue
                chosen.add(identity)
        used = []
        frontier = set(chosen)
        for _ in range(int(depth)):
            added = set()
            for rel in self.graph['rels']:
                if relations and rel['type'] not in relations: continue
                if direction in ['out', 'both'] and rel['a'] in frontier:
                    used.append(rel); added.add(rel['b'])
                if direction in ['in', 'both'] and rel['b'] in frontier:
                    used.append(rel); added.add(rel['a'])
            frontier = added - chosen; chosen |= added
            if not frontier: break
        rows = [self.nodes[i] for i in sorted(chosen) if i in self.nodes]
        limit, offset = int(limit), int(offset)
        if limit < 1 or offset < 0: raise ValueError('limit은 1 이상, offset은 0 이상입니다.')
        page = rows[offset:offset + limit]
        return {'nodes': page, 'rels': [dict(t) for t in {json.dumps(r, sort_keys=True): r for r in used}.values()],
                'total': len(rows), 'offset': offset, 'next_offset': offset + limit if offset + limit < len(rows) else None,
                'source': self.graph_source, 'source_sha256': self.graph_hash}

    def document(self, doc_id, revision, line_start=None, line_end=None, section=None, before=0, after=0):
        items = [d for d in self.sources['documents'] if d['doc_id'] == doc_id and d['revision'] == revision]
        if len(items) != 1 or not items[0]['file']:
            raise ValueError(f'문서 원문 없음: {doc_id}@{revision}. 목록의 요청 중인 문서는 본문을 만들지 않습니다.')
        item = items[0]; path = self.data_dir / 'documents' / item['file']
        if sha(path) != item['bytes_sha256']:
            raise ValueError(f'원문 바이트가 목록 입력판과 다릅니다: {item["file"]}')
        lines = path.read_bytes().decode(item['encoding']).splitlines()
        headings = [(n, line) for n, line in enumerate(lines, 1) if line.startswith('#')]
        if section:
            found = [(n, line) for n, line in headings if re.search(r'(?<![\w.-])' + re.escape(section) + r'(?![\w.-])', line)]
            if len(found) != 1: raise ValueError(f'절 {section}: 표제 {len(found)}곳. 먼저 문서의 목차를 조회합니다.')
            line_start = found[0][0]
            level = len(found[0][1]) - len(found[0][1].lstrip('#'))
            line_end = next((n - 1 for n, line in headings if n > line_start and len(line) - len(line.lstrip('#')) <= level), len(lines))
        if line_start is None:
            return {'document': item, 'headings': [{'line': n, 'text': t} for n, t in headings], 'line_count': len(lines)}
        begin = max(1, int(line_start) - int(before)); end = min(len(lines), int(line_end or line_start) + int(after))
        if begin > end: raise ValueError('원문 시작 줄이 끝 줄보다 큽니다.')
        return {'document': item, 'source': path.relative_to(self.root).as_posix(), 'line_start': begin, 'line_end': end,
                'lines': [{'line': n, 'text': lines[n-1]} for n in range(begin, end+1)]}

    def index(self):
        if self.connection: return self.connection
        target = self.output_dir / 'observation_index.sqlite'
        target.parent.mkdir(exist_ok=True)
        db = sqlite3.connect(target)
        source_hash = sha(self.data_dir / 'data_manifest.json')
        db.execute('CREATE TABLE IF NOT EXISTS metadata (source_hash TEXT)')
        current = db.execute('SELECT source_hash FROM metadata').fetchone()
        if current is None or current[0] != source_hash:
            began = time.perf_counter()
            db.executescript('DROP TABLE IF EXISTS samples; CREATE TABLE samples (dataset TEXT, asset TEXT, t REAL, received REAL, quality TEXT, TS1 REAL, CE REAL, VS1 REAL, TS4 REAL, state TEXT, mode TEXT, fan REAL, load REAL, source TEXT, line INTEGER, observation_id TEXT); DELETE FROM metadata;')
            batch = []
            for source, item in self.manifest['files'].items():
                path = self.root / source
                if sha(path) != item['sha256']: raise ValueError(f'관측 파일의 해시 불일치: {source}')
                with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
                    next(stream); reader = csv.DictReader(stream)
                    for number, row in enumerate(reader, 3):
                        values = [float(row[k]) if row[k] else None for k in ['TS1', 'CE', 'VS1', 'TS4']]
                        batch.append((str(item['interval_s'])+'s', row['asset'], moment(row['observed_at']).timestamp(), moment(row['received_at']).timestamp(), row['quality'], *values,
                                      row['state'], row['mode'], float(row['fan_pct']), float(row['load_pct']), source, number, row['observation_id']))
                        if len(batch) >= 10000:
                            db.executemany('INSERT INTO samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', batch); batch.clear()
            if batch: db.executemany('INSERT INTO samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', batch)
            db.execute('CREATE INDEX sample_time ON samples(dataset,asset,t)')
            db.execute('INSERT INTO metadata VALUES (?)', (source_hash,)); db.commit()
            print(f'관측 색인: {time.perf_counter()-began:.3f}초 · {db.execute("SELECT COUNT(*) FROM samples").fetchone()[0]}행')
        self.connection = db
        return db

    def observations(self, asset, start, end, tags, dataset='1s', state=None, load_pct=None):
        if dataset not in ['1s', '10s']: raise ValueError('dataset은 1s 또는 10s입니다.')
        if not tags or set(tags) - set(self.manifest['tags']): raise ValueError('태그는 data_manifest.json에서 고릅니다.')
        begin, finish = moment(start).timestamp(), moment(end).timestamp()
        if begin >= finish: raise ValueError('시작은 끝 시각보다 빨라야 합니다.')
        where = 'dataset=? AND asset=? AND t>? AND t<=?'; args = [dataset, asset, begin, finish]
        if state is not None: where += ' AND state=?'; args.append(state)
        if load_pct is not None: where += ' AND load=?'; args.append(float(load_pct))
        db = self.index(); db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute('SELECT * FROM samples WHERE '+where+' ORDER BY t', args)]
        summaries = {}
        for tag in tags:
            good = [r for r in rows if r['quality'] == 'good' and r[tag] is not None]
            times = [begin] + [r['t'] for r in good] + [finish]
            values = [r[tag] for r in good]
            summaries[tag] = {'unit': self.manifest['tags'][tag], 'count': len(values), 'mean': sum(values)/len(values) if values else None,
                              'min': min(values) if values else None, 'max': max(values) if values else None,
                              'first': values[0] if values else None, 'last': values[-1] if values else None,
                              'last_observed_at': datetime.fromtimestamp(good[-1]['t'], moment(end).tzinfo).isoformat() if good else None,
                              'age_at_end_s': finish-good[-1]['t'] if good else None,
                              'max_gap_s': max(b-a for a,b in zip(times,times[1:])),
                              'source_rows': [{'file': r['source'], 'line': r['line'], 'observation_id': r['observation_id']} for r in ([good[0], good[-1]] if good else [])]}
        return {'asset': asset, 'start_exclusive': start, 'end_inclusive': end, 'dataset': dataset, 'sample_interval_s': int(dataset[:-1]),
                'filters': {'state': state, 'load_pct': load_pct}, 'row_count': len(rows), 'bad_rows': sum(r['quality']!='good' for r in rows),
                'statistics': summaries, 'source_files': sorted({r['source'] for r in rows}),
                'sample_kind': '개별 관측 표본의 질의 시 집계',
                'coverage_windows': {p:[span for span in v['coverage_windows'] if moment(span[0]).timestamp()<=finish and moment(span[1]).timestamp()>=begin] for p,v in self.manifest['files'].items() if p.endswith(f'{asset}_1s.csv.gz') or p.endswith(asset.lower().replace('-', '_') + '_1s.csv.gz')} if dataset=='1s' else {}}

    def history(self, asset, start, end, kind='maintenance'):
        fields = {'maintenance': ('maintenance.csv', 'performed_at'), 'events': ('events.csv', 'event_at'), 'states': ('state_changes.csv', 'observed_at')}
        if kind not in fields: raise ValueError('kind는 maintenance/events/states입니다.')
        name, field = fields[kind]; source = (self.data_dir / name).relative_to(self.root).as_posix()
        rows = []
        for number, row in enumerate(read_csv(self.root/source), 3):
            if row['asset'] == asset and moment(start) <= moment(row[field]) <= moment(end):
                rows.append(row | {'source': source, 'line': number})
        return {'asset': asset, 'start': start, 'end': end, 'rows': rows, 'row_count': len(rows), 'source': source, 'query_succeeded': True}

    def call(self, name, arguments):
        if name not in TOOL_CONTRACT: raise ValueError(f'도구 없음: {name}')
        return getattr(self, name)(**arguments)


TOOL_CONTRACT = {
    'graph_query': '선택한 레이블 labels, ID ids, 모든 검색어 terms, 관계 relations, 방향 direction(out/in/both), 깊이 depth로 그래프 조회. offset/limit 페이지. 일치 단어 검색이며 의미 검색이라고 주장하지 않음.',
    'document': 'doc_id와 revision 필수. 처음에는 목차. section 또는 line_start/line_end를 선택하고 before/after 줄 확장 가능. 원문·판본 상태·줄을 반환.',
    'observations': 'asset/start/end/tags 필수. 시간 범위는 (start,end]. dataset=1s 사건 원천 또는 10s 장기 개별 표본. state/load_pct 선택 필터. 각 태그 통계·표본수·최대공백·나이·원문 행 반환. 판정은 하지 않음.',
    'history': 'asset/start/end 필수. kind=maintenance/events/states. 작업 수행과 보고 시각 또는 사건/상태 이력을 원문 행과 함께 반환.'
}
