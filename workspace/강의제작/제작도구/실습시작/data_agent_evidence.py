"""5회차 원인·점검 계획 자료. 기존 3회차 물리 궤적과 4회차 검증판을 잇는다.

원자료 바이트는 보존한다. 목록 해시는 원래 인코딩의 LF 바이트로 확인한다.
긴 관측은 10초 간격 표본이고 평균이 아니다. 사건 구간은 같은 궤적의 1초 표본이다.
모델 호출 없음. 생성 시간·개수·원본 해시는 --report에 남긴다.
"""
from pathlib import Path
import argparse
import bisect
import csv
import gzip
import hashlib
import io
import json
import math
import shutil
import time

import data_conditions as dc

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
GRAPH = HERE / 'reference/session3_docs/갈래/그래프_통합반_가'
DOCS = ROOT / 'workspace/강의제작/산출물/통합반/실습/04회차/랩/04일차_실습3_그래프반영과검증/자료'
NOTICE = '가상 사례: 공개된 현업 문제 유형을 따라 만든 자료이며 실제 회사·제조사·설비의 기록이 아니다.'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        stream.write('# ' + NOTICE + '\n')
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(fields)
        writer.writerows(rows)


def copy_sources(lab):
    target = lab / '입력/ontology'
    target.mkdir(parents=True, exist_ok=True)
    graph_names = {'지식_내보내기.json': 'graph.json', 'schema_ext.json': 'schema.json', '그래프_모양.json': 'shape.json'}
    sources = []
    for old, new in graph_names.items():
        raw = (GRAPH / old).read_bytes()
        (target / new).write_bytes(raw)
        sources.append({'path': f'입력/ontology/{new}', 'origin': '4회차 그래프 반영과 검증의 제공 입력', 'sha256': digest(raw)})
    doc_target = lab / '자료/documents'
    doc_target.mkdir(parents=True, exist_ok=True)
    raw_list = (DOCS / '문서_목록.csv').read_bytes()
    (doc_target / '문서_목록.csv').write_bytes(raw_list)
    entries = list(csv.DictReader(line for line in raw_list.decode('utf-8-sig').splitlines() if not line.startswith('#')))
    manifest = []
    for row in entries:
        item = {'doc_id': row['문서 식별자'], 'revision': row['판'], 'status': row['상태'], 'effective': row['시행일'],
                'file': row['파일'], 'catalog_sha256': row['SHA-256'], 'catalog_line': len(manifest) + 3}
        if row['파일']:
            raw = (DOCS / row['파일']).read_bytes()
            try:
                text = raw.decode('utf-8-sig'); encoding = 'utf-8-sig'
            except UnicodeDecodeError:
                text = raw.decode('cp949'); encoding = 'cp949'
            normalized = text.replace('\r\n', '\n').replace('\r', '\n')
            lf_hash = digest(normalized.encode('utf-8'))
            source_lf_hash = digest(raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n'))
            if source_lf_hash != row['SHA-256']:
                raise ValueError(f"목록과 원문의 LF 해시 불일치: {row['파일']}")
            (doc_target / row['파일']).write_bytes(raw)
            item.update(encoding=encoding, bytes_sha256=digest(raw), source_encoding_lf_sha256=source_lf_hash, normalized_utf8_lf_sha256=lf_hash, lines=len(text.splitlines()))
        manifest.append(item)
    graph = json.loads((target / 'graph.json').read_text(encoding='utf-8-sig'))
    provenance = {'version': 'agent-evidence-2026-11-10', 'graph_sources': sources,
                  'catalog': {'path': '자료/documents/문서_목록.csv', 'sha256': digest(raw_list)},
                  'graph_counts': {key: len(value) for key, value in graph.items()}, 'documents': manifest}
    dump(lab / '입력/source_manifest.json', provenance)
    return provenance


def merged_windows(windows):
    out = []
    for start, end in sorted(windows):
        start, end = max(0, start), min(dc.N_S - 1, end)
        if out and start <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def values(unit, second, change):
    # 같은 시점은 두 자료에서 같은 값. 호출 순서와 무관한 결정론적 측정 잡음.
    minute = second // 60
    noise = math.sin(second * 1.61803398875 + dc.ASSETS.index(unit.asset) * 3.1)
    running = change[2] == 'RUN'
    wear = min(.2, max(0.0, (second - dc.sec(dc.kst(2026, 10, 17))) / (7 * 86400) * .2)) if unit.asset == 'HYD-03' else 0.0
    vibration = dc.M.vibration(unit.log[second], wear, change[4] if running else 0.0) + .02 * abs(noise)
    if vibration >= dc.M.TRIP_VS1:
        raise ValueError('팬 진동 인터록을 재계산해야 하는 외란입니다.')
    return [round(unit.log[second], 3), round(dc.ce_of(unit.health[minute], change[4]), 3),
            round(vibration, 4),
            round(unit.amb[minute] + 3.0 + .1 * noise, 3)]


def observations(path, unit, seconds):
    count = bad_count = 0
    changes = [x[0] for x in unit.changes]
    outage = unit.faults['outage']; bad = unit.faults['bad']
    outage_starts = [x[0] for x in outage]; bad_starts = [x[0] for x in bad]
    def contains(spans, starts, second):
        pos = bisect.bisect_right(starts, second) - 1
        return pos >= 0 and spans[pos][0] <= second < spans[pos][1]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
        with io.TextIOWrapper(compressed, encoding='utf-8', newline='') as stream:
            stream.write('# ' + NOTICE + '\n')
            writer = csv.writer(stream, lineterminator='\n')
            writer.writerow(['observation_id', 'asset', 'observed_at', 'received_at', 'quality', 'TS1', 'CE', 'VS1', 'TS4', 'state', 'mode', 'fan_pct', 'load_pct'])
            for second in seconds:
                if contains(outage, outage_starts, second):
                    continue
                change = unit.changes[max(0, bisect.bisect_right(changes, second) - 1)]
                quality = 'bad' if contains(bad, bad_starts, second) else 'good'
                vals = values(unit, second, change) if quality == 'good' else ['', '', '', '']
                writer.writerow([f'{unit.asset}:{second}', unit.asset, dc.iso_kst(second), dc.iso_utc(second + 1), quality,
                                 *vals, change[2], change[1], change[4], change[5]])
                count += 1; bad_count += quality == 'bad'
    return {'rows': count, 'bad_rows': bad_count, 'observation_cells': count * 4, 'bytes': path.stat().st_size, 'sha256': digest(path.read_bytes())}


def build(lab, report=None):
    started = time.perf_counter()
    lab = Path(lab).resolve()
    provenance = copy_sources(lab)
    units = {}
    for asset in dc.ASSETS:
        unit = dc.Unit(asset)
        if asset == 'HYD-03':
            # 원본 생성기를 바꾸지 않고 한 설비의 외기 입력을 보완한다.
            # 온도 관측만 올리지 않는다: 같은 입력으로 열평형·경보·조치·복귀가 모두 다시 계산된다.
            begin, end = dc.sec(dc.kst(2026,10,12)), dc.sec(dc.kst(2026,10,17))
            for minute in range(begin//60, end//60):
                hour = (minute % 1440) / 60
                unit.amb[minute] += 12 * max(0, math.sin(math.pi * (hour-8)/12)) if 8 <= hour <= 20 else 0
        units[asset] = unit.simulate()
    simulated = time.perf_counter()
    records = dc.Records(units)
    requests, events, maintenance, states = [], [], [], []
    files = {}
    for asset, unit in units.items():
        request_times = []
        for alarm in unit.alarms:
            if alarm.get('judge') is None or alarm['judge'] > records.end:
                continue
            second = alarm['judge']
            request_times.append(second)
            requests.append([alarm['id'], asset, dc.iso_kst(second), alarm['id'], '설비보전팀', '원인 후보와 다음 점검 항목을 근거·미확인과 함께 검토'])
            events.append([alarm['id'], asset, dc.iso_utc(alarm['raise_s']), 'RAISE', 'COOLER_DEGRADATION', dc.iso_kst(second)])
            if alarm.get('clear_s') is not None:
                events.append([alarm['id'], asset, dc.iso_utc(alarm['clear_s']), 'CLEAR', 'COOLER_DEGRADATION', ''])
        # 수집 장애가 시작/끝난 시점도 실제 기록 조회 요청의 대상이다. 값은 새로 만들지 않는다.
        for number, (begin, end) in enumerate(unit.faults['outage']):
            if number % 50 == 0 and end < records.end:
                second = end + 10
                request_times.append(second)
                requests.append([f'OBS-{asset}-{number:03d}', asset, dc.iso_kst(second), '', '설비보전팀', '관측 재개 뒤 점검 근거의 유효 범위를 검토'])
        spans = merged_windows([(t - 240, t + 20) for t in request_times])
        relative = f'자료/observations/{asset}_10s.csv.gz'
        files[relative] = observations(lab / relative, unit, range(0, records.end + 1, 10)) | {'interval_s': 10, 'kind': 'individual_samples'}
        relative = f'자료/observations/{asset}_1s.csv.gz'
        files[relative] = observations(lab / relative, unit, (s for a, b in spans for s in range(a, b + 1))) | {'interval_s': 1, 'kind': 'incident_source', 'coverage_windows': [[dc.iso_kst(a), dc.iso_kst(b)] for a, b in spans]}
        for second, mode, state, trip, fan, load in unit.changes:
            if second <= records.end:
                states.append([f'ST-{asset}-{second}', asset, dc.iso_kst(second), mode, state, trip, fan, load])
        # 2교대 순회 기록은 각 교대의 실제 관측과 작업 상태를 가리킨다. 원인 확정 값을 넣지 않는다.
        for day in range((records.end // 86400) + 1):
            for hour in (6, 18):
                second = day * 86400 + hour * 3600
                if second > records.end:
                    continue
                change = unit.setting_at(second)
                recent = [a['id'] for a in unit.alarms if a.get('id') and max(0, second - 12 * 3600) <= a['raise_s'] <= second]
                maintenance.append([f'ROUND-{asset}-{day:02d}-{hour}', asset, dc.iso_kst(second), dc.iso_kst(second + 300), '',
                                    '순회 기록', '운전원', ';'.join(recent), f'상태 {change[2]}, 팬 지시 {change[4]:.0f} %. 현장 벨트·핀 내부 점검은 이 순회 기록의 확인 항목에 포함되지 않음.'])
        for number, clean in enumerate(dc.SCENARIO[asset]['cleanings']):
            begin, duration = clean; second = dc.sec(begin); end = second + int(duration * 3600)
            work = f'WO-{asset}-{number + 1:03d}'
            maintenance.extend([[work + '-start', asset, dc.iso_kst(second), dc.iso_kst(second + 60), work, '작업 중', '설비보전팀', '', '쿨러 핀 세척 시작.'],
                                [work + '-done', asset, dc.iso_kst(end), dc.iso_kst(end + 300), work, '작업 완료', '설비보전팀', '', '핀 세척 작업 종료. 운전 복귀 뒤 관측은 별도 기록에서 확인.']])
    requests.sort(key=lambda x: (x[2], x[1])); maintenance.sort(key=lambda x: (x[2], x[1]))
    write_csv(lab / '자료/requests.csv', ['request_id', 'asset', 'as_of', 'event_id', 'recipient', 'question'], requests)
    write_csv(lab / '자료/events.csv', ['event_id', 'asset', 'event_at', 'event_type', 'pattern', 'requested_at'], sorted(events, key=lambda x: x[2]))
    write_csv(lab / '자료/maintenance.csv', ['record_id', 'asset', 'performed_at', 'reported_at', 'work_id', 'status', 'role', 'event_ids', 'note'], maintenance)
    write_csv(lab / '자료/state_changes.csv', ['record_id', 'asset', 'observed_at', 'mode', 'state', 'trip', 'fan_pct', 'load_pct'], sorted(states, key=lambda x: x[2]))
    incident = next(c for c in records.cases if c['incident'])
    metadata = {'version': provenance['version'], 'from': dc.iso_kst(0), 'through': dc.iso_kst(records.end),
                'simulation_through': dc.iso_kst(dc.N_S-1), 'export_reason': '사건 판정 요청 후 20초까지의 기록 내보내기', 'assets': list(units),
                'default_request': incident['id'], 'tags': {'TS1': '℃', 'CE': '%', 'VS1': 'mm/s', 'TS4': '℃'},
                'files': files, 'request_count': len(requests), 'event_rows': len(events), 'maintenance_rows': len(maintenance), 'state_rows': len(states),
                'source_code': {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in [Path(dc.__file__), ROOT / 'common/hydcommon/plant_model.py', ROOT / 'ot/plant-sim/plantsim/thermal.py', Path(__file__)]}}
    dump(lab / '자료/data_manifest.json', metadata)
    measured = {'lab': lab.relative_to(ROOT).as_posix() if lab.is_relative_to(ROOT) else str(lab), 'simulation_seconds': round(simulated - started, 3),
                'total_seconds': round(time.perf_counter() - started, 3), 'graph': provenance['graph_counts'], 'documents': len([d for d in provenance['documents'] if d['file']]),
                **metadata, 'graph_origin_files': [str((GRAPH/name).relative_to(ROOT)) for name in ['지식_내보내기.json','schema_ext.json','그래프_모양.json']],
                'physical_extensions': {'HYD-03_ambient': '10/12~16, 08~20시 반사인 외기 변화 최대12℃를 Unit.amb에 넣어 같은 열식과 운전 로직으로 전체 궤적 재계산',
                                        'HYD-03_fan_wear': '10/17부터7일간0→0.2 완만한 증가. plant_model.vibration에 적용. 열식에 없는 마찰열을 추가하지 않으며 모든 내보낸 관측이 진동 인터록2.0 미만임을 검사',
                                        'export_policy': '원인 참값·마모 상태는 학생 자료에 없음. 관측과 실제 궤적이 낸 사건·상태만 내보냄'}}
    if report:
        dump(Path(report), measured)
    return measured


def project_data(source, target, report):
    """검증된 기존 입력을 영문 경로로 복사한다. 원문·관측 바이트는 바꾸지 않는다."""
    source, target = Path(source), Path(target)
    mappings = []
    def copy(old, new):
        raw = (source / old).read_bytes(); destination = target / new
        destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(raw)
        mappings.append({'from': old, 'to': new, 'sha256': digest(raw), 'bytes': len(raw)})
    sources = json.loads((source / '입력/source_manifest.json').read_text(encoding='utf-8-sig'))
    metadata = json.loads((source / '자료/data_manifest.json').read_text(encoding='utf-8-sig'))
    for item in sources['graph_sources']:
        destination = 'data/model/' + Path(item['path']).name
        copy(item['path'], destination); item['path'] = destination
    copy(sources['catalog']['path'], 'data/documents/catalog.csv')
    sources['catalog']['path'] = 'data/documents/catalog.csv'
    sources['catalog']['file_mapping'] = 'documents의 catalog_file은 목록 원래 이름, file은 이 폴더에서 읽는 파일 이름이다. 내용과 해시는 같다.'
    for item in sources['documents']:
        if not item['file']: continue
        original = item['file']
        filename = item['doc_id'].lower().replace('-', '_') + '_' + item['revision'].lower().replace('.', '_') + Path(original).suffix
        copy('자료/documents/' + original, 'data/documents/' + filename)
        item['catalog_file'] = original; item['file'] = filename
    files = {}
    for original, item in metadata['files'].items():
        destination = 'data/observations/' + Path(original).name.lower().replace('-', '_')
        copy(original, destination); files[destination] = item
    metadata['files'] = files
    # 제작 경로는 판정 근거에만 남긴다. 학생에게는 생성 원천 종류와 해시를 제공한다.
    generation_sources = metadata.pop('source_code', {})
    metadata['generation_sources'] = {Path(k).name: v for k, v in generation_sources.items()}
    for name in ['requests.csv', 'events.csv', 'maintenance.csv', 'state_changes.csv']:
        copy('자료/' + name, 'data/' + name)
    dump(target / 'data/data_manifest.json', metadata)
    dump(target / 'data/source_manifest.json', sources)
    result = {'raw_files': mappings, 'all_raw_bytes_equal': all((source / x['from']).read_bytes() == (target / x['to']).read_bytes() for x in mappings),
              'original_manifests': {name: digest((source / name).read_bytes()) for name in ['입력/source_manifest.json', '자료/data_manifest.json']},
              'generation_sources': generation_sources, 'model_calls': 0}
    dump(report, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('lab', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.lab, args.report)
    print(json.dumps({k: result[k] for k in ['simulation_seconds', 'total_seconds', 'graph', 'documents', 'request_count', 'maintenance_rows', 'default_request']}, ensure_ascii=False, indent=2))
