"""A124 — prune processed case-projection outbox rows from the process service's SQLite file.

    .venv314/Scripts/python.exe scripts/prune_projection_outbox.py --older-than-days 1                      # dry-run (count only)
    .venv314/Scripts/python.exe scripts/prune_projection_outbox.py --older-than-days 1 --apply              # delete
    .venv314/Scripts/python.exe scripts/prune_projection_outbox.py --older-than-days 1 --apply --vacuum     # + VACUUM (process container must be stopped)
    options: --container hyd-iot-edu-process-1  --db /data/process.sqlite3  --chunk 500  --no-checkpoint-guard  --out <json file>

Why: HANDOFF §9 A115 — process.sqlite3 (254 MB on 10-07) was mostly 8,615 processed `case_projection_outbox` rows (188 MB) that
nothing deletes; pending was 0, so the rows only occupy disk. The table (case_projection_store.py:13-16) has
id, kind, source_id, body, created_at, processed_at, attempts, last_error, retry_at.

Target rows
  processed_at IS NOT NULL AND processed_at < now - N days
  AND created_at < latest knowledge_projection_checkpoint.queued_at   (guard; lift with --no-checkpoint-guard)
Unprocessed rows (processed_at IS NULL) are never touched, whatever their age.

Why deleting processed rows is safe — nothing reads them back (checked 2026-10-07):
  - case_projection_store.py:55-68  case_projection_batch: `where processed_at is null` only; delivers the newest unprocessed body per (kind,source_id).
  - case_projection_store.py:70-74  finish_case_projection: `where id=? and processed_at is null`.
  - case_projection_store.py:76-81  case_projection_status: pending rows only.
  - case_projection_store.py:26-40  _enqueue_case_snapshot: change detection compares digests in `case_projection_source`, not outbox rows.
  - case_projection_store.py:23-24  startup re-enqueue uses the snapshot + the digest table, not the outbox.
  - projection_repair.py:59         inspect_case lists pending rows only (`processed_at is null`).
  - projection_repair.py:122-125    repair floor = max(sqlite_sequence.seq, Neo4j fence revision). The table is AUTOINCREMENT
                                    (case_projection_store.py:14), so `sqlite_sequence` keeps the highest id ever issued across DELETE and
                                    VACUUM — revisions stay monotonic and old ids are never reused.
  - case_projection.py:76-103       deliver: revision = the job's own (unprocessed) outbox id; the fence lives in Neo4j (projection_receipt), it is
                                    never re-read from processed rows.
  Checkpoint guard: knowledge_projection_checkpoint (case_projection_store.py:42-53) records the last forced full re-enqueue. Rows created at or
  after it are kept so the latest full re-projection stays inspectable in the table. The code does not need them — it is a conservative margin.

Execution model and locking (judgement)
  - Everything runs *inside* the process container's filesystem: `docker exec hyd-iot-edu-process-1 python -` (running) or, when the container
    is stopped, a throwaway `docker run --rm -v hyd-iot-edu_process-data:/data <process image> python -` on the same volume. SQLite's file
    locks and the WAL index (-shm) are then shared correctly with the service. Never `docker cp` the DB out, edit, and copy back: the service
    keeps writing (store.py:51-60) and the copy would silently drop those writes.
  - dry-run: SELECT only. The DB is in WAL mode (store.py:24) so a reader never blocks the service's writer → safe while running.
  - --apply: DELETE in chunks (--chunk, default 500 rows) with one short transaction each and busy_timeout 15 s on our side. The service's
    connection is `sqlite3.connect(path, check_same_thread=False)` (store.py:22) → default 5 s busy timeout; a chunk that held the write lock
    longer would make the service's save() raise "database is locked". Chunks keep each lock well under that, so --apply is allowed while the
    container runs, but run it between regressions, not during one. DELETE does not shrink the file (freed pages go to the freelist and are
    reused by new rows); the WAL is checkpointed passively afterwards.
  - --vacuum: VACUUM rewrites the whole file under an exclusive lock for seconds to tens of seconds on a 250 MB file — longer than the
    service's 5 s timeout — so it is REFUSED while the container is running (exit 2) and only runs through the throwaway container on the
    stopped volume. Stop the service first (`docker compose stop process`), vacuum, then `docker compose up -d process`.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

INNER = r'''
import json, os, sqlite3, sys, time
cfg = json.loads(sys.argv[1])
db_path = cfg["db"]
def size(p):
    return os.path.getsize(p) if os.path.exists(p) else 0
def sizes():
    return {"db": size(db_path), "wal": size(db_path + "-wal"), "shm": size(db_path + "-shm")}
if not os.path.exists(db_path):
    print(json.dumps({"error": "db not found: " + db_path})); sys.exit(3)
db = sqlite3.connect(db_path, timeout=15)
db.execute("pragma busy_timeout=15000")
now = time.time()
cutoff = now - cfg["days"] * 86400
ckpt = db.execute("select max(queued_at) from knowledge_projection_checkpoint").fetchone()[0]
guard = ckpt if (cfg["guard"] and ckpt) else None
cond = "processed_at is not null and processed_at < ?" + (" and created_at < ?" if guard else "")
params = (cutoff, guard) if guard else (cutoff,)
def stats():
    total, processed, pending = db.execute(
        "select count(*), sum(processed_at is not null), sum(processed_at is null) from case_projection_outbox").fetchone()
    c = db.execute("select count(*), coalesce(sum(length(cast(body as blob))),0), min(processed_at), max(processed_at), min(id), max(id) "
                   "from case_projection_outbox where " + cond, params).fetchone()
    pend = db.execute("select min(created_at), max(attempts) from case_projection_outbox where processed_at is null").fetchone()
    seq = db.execute("select seq from sqlite_sequence where name='case_projection_outbox'").fetchone()
    ps = db.execute("pragma page_size").fetchone()[0]; pc = db.execute("pragma page_count").fetchone()[0]
    fl = db.execute("pragma freelist_count").fetchone()[0]
    return {"rows_total": total or 0, "rows_processed": processed or 0, "rows_pending": pending or 0,
            "candidates": c[0], "candidate_body_bytes": c[1], "candidate_processed_at_min": c[2], "candidate_processed_at_max": c[3],
            "candidate_id_min": c[4], "candidate_id_max": c[5], "pending_oldest_created_at": pend[0], "pending_max_attempts": pend[1],
            "sqlite_sequence_seq": seq[0] if seq else None, "page_size": ps, "page_count": pc, "freelist_pages": fl,
            "page_bytes": ps * pc, "files": sizes()}
res = {"db": db_path, "now": now, "cutoff": cutoff, "older_than_days": cfg["days"], "checkpoint_queued_at": ckpt,
       "checkpoint_guard_active": guard is not None, "sqlite_version": sqlite3.sqlite_version, "mode": cfg["mode"], "before": stats()}
if cfg["apply"]:
    deleted = 0; chunks = 0; t0 = time.time()
    while True:
        with db:
            cur = db.execute("delete from case_projection_outbox where id in (select id from case_projection_outbox where " + cond +
                             " order by id limit ?)", (*params, cfg["chunk"]))
        n = cur.rowcount; deleted += n; chunks += 1
        if n < cfg["chunk"]:
            break
    db.execute("pragma wal_checkpoint(PASSIVE)")
    res["deleted"] = deleted; res["chunks"] = chunks; res["delete_seconds"] = round(time.time() - t0, 3)
    if cfg["vacuum"]:
        t1 = time.time()
        db.isolation_level = None
        db.execute("VACUUM")
        db.execute("pragma wal_checkpoint(TRUNCATE)")
        res["vacuum_seconds"] = round(time.time() - t1, 3)
    res["after"] = stats()
db.close()
print(json.dumps(res))
'''


def docker(*args, check=True):
    return subprocess.run(['docker', *args], capture_output=True, text=True, encoding='utf-8', errors='replace', check=check)


def container_info(name):
    p = docker('inspect', '-f', '{{.State.Status}}|{{.Config.Image}}|{{json .Mounts}}', name, check=False)
    if p.returncode:
        sys.exit(f'container {name!r} not found: {p.stderr.strip()}')
    status, image, mounts = p.stdout.strip().split('|', 2)
    vol = next((m['Name'] for m in json.loads(mounts) if m.get('Destination') == '/data' and m.get('Type') == 'volume'), None)
    return status, image, vol


def mb(n):
    return f'{n / 1048576:.1f} MB'


def main():
    ap = argparse.ArgumentParser(description='prune processed case_projection_outbox rows (dry-run unless --apply)')
    ap.add_argument('--older-than-days', type=float, required=True, help='delete rows whose processed_at is older than N days')
    ap.add_argument('--apply', action='store_true', help='actually delete (default: count only)')
    ap.add_argument('--vacuum', action='store_true', help='VACUUM after delete; refused while the container is running')
    ap.add_argument('--container', default='hyd-iot-edu-process-1')
    ap.add_argument('--db', default='/data/process.sqlite3')
    ap.add_argument('--chunk', type=int, default=500, help='rows per delete transaction (keeps each write lock short)')
    ap.add_argument('--no-checkpoint-guard', action='store_true', help='also delete rows created after the latest knowledge checkpoint')
    ap.add_argument('--out', type=Path, help='write the JSON result here as well')
    a = ap.parse_args()
    if a.older_than_days < 0 or a.chunk < 1:
        ap.error('--older-than-days must be >= 0 and --chunk >= 1')
    if a.vacuum and not a.apply:
        ap.error('--vacuum needs --apply')
    status, image, vol = container_info(a.container)
    running = status == 'running'
    if a.vacuum and running:
        sys.exit(f'refused: --vacuum needs the process container stopped (it is {status}); VACUUM holds an exclusive lock longer than the '
                 f'service\'s 5 s busy timeout (store.py:22). Stop it first: docker compose stop process')
    cfg = {'db': a.db, 'days': a.older_than_days, 'apply': a.apply, 'vacuum': a.vacuum, 'chunk': a.chunk,
           'guard': not a.no_checkpoint_guard, 'mode': 'exec' if running else 'run'}
    if running:
        cmd = ['exec', '-i', a.container, 'python', '-', json.dumps(cfg)]
    else:
        if not vol:
            sys.exit('container is stopped and no /data volume was found on it; cannot reach the DB')
        cmd = ['run', '--rm', '-i', '-v', f'{vol}:/data', image, 'python', '-', json.dumps(cfg)]
    p = subprocess.run(['docker', *cmd], input=INNER, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode or not p.stdout.strip():
        sys.exit(f'inner script failed (rc={p.returncode}):\n{p.stderr}')
    res = json.loads(p.stdout.strip().splitlines()[-1])
    if 'error' in res:
        sys.exit(res['error'])
    res['container'] = {'name': a.container, 'status': status, 'image': image, 'volume': vol}
    b = res['before']
    print(f"container {a.container} {status} ({res['mode']}), sqlite {res['sqlite_version']}, db {a.db}")
    print(f"file: db {mb(b['files']['db'])} + wal {mb(b['files']['wal'])}; pages {b['page_count']}x{b['page_size']} = {mb(b['page_bytes'])}, "
          f"free pages {b['freelist_pages']}")
    print(f"outbox rows: total {b['rows_total']}, processed {b['rows_processed']}, pending {b['rows_pending']}"
          f" (pending oldest created_at {b['pending_oldest_created_at']}, max attempts {b['pending_max_attempts']}); "
          f"sqlite_sequence {b['sqlite_sequence_seq']}")
    print(f"cutoff processed_at < {res['cutoff']:.0f} (now - {a.older_than_days} d); checkpoint guard "
          f"{'created_at < %.0f' % res['checkpoint_queued_at'] if res['checkpoint_guard_active'] else 'off'}")
    print(f"candidates: {b['candidates']} rows, body {mb(b['candidate_body_bytes'])}, id {b['candidate_id_min']}..{b['candidate_id_max']}, "
          f"processed_at {b['candidate_processed_at_min']}..{b['candidate_processed_at_max']}")
    if a.apply:
        af = res['after']
        print(f"applied: deleted {res['deleted']} rows in {res['chunks']} chunk(s), {res['delete_seconds']} s"
              + (f"; VACUUM {res['vacuum_seconds']} s" if a.vacuum else ''))
        print(f"after: rows total {af['rows_total']} (pending {af['rows_pending']}), file db {mb(af['files']['db'])} + wal "
              f"{mb(af['files']['wal'])}, free pages {af['freelist_pages']}, sqlite_sequence {af['sqlite_sequence_seq']}")
        if not a.vacuum:
            print('note: DELETE does not shrink the file; run with --vacuum (container stopped) to reclaim disk')
    else:
        print('dry run — nothing changed')
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
        print('json written to', a.out)


if __name__ == '__main__':
    main()
