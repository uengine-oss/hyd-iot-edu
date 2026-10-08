"""A155 (A148 item 68) — residue cleanup: definition versions registered under older rules that today's registry rejects.

    .venv/bin/python scripts/cleanup_invalid_definitions.py --out <dir> [--apply]          (Linux)
    . scripts/host_libpq.sh; .venv314/Scripts/python scripts/cleanup_invalid_definitions.py --out <dir> [--apply]

Residue is decided by the current contract, not by a list of names: every `proc_def_version` row of the tenant is run through
`definition_registry.validate_definition`; a row it rejects could not be registered today (e.g. A115 A6 gateway-less splits in
the old test definitions independent-reviews-* and friends). Rows that pass are never touched.

Without --apply it only lists and writes backup.json. With --apply, after the backup:
  1. a rejected version still used by a live instance (bpm_proc_inst, is_deleted = false) stops the run with its coordinates —
     clean those instances first (scripts/cleanup_residue_instances.py); nothing is deleted.
  2. DELETE the rejected proc_def_version rows; a proc_def head left with no version is deleted too, a head whose current
     definition was rejected but still has a valid version is reported (not rewritten).
"""
import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'it/process'), str(ROOT / 'common')]
from procsvc.definition_registry import validate_definition  # noqa: E402

DSN = os.environ.get('SUPABASE_DSN', 'postgresql://postgres:postgres@127.0.0.1:54322/postgres')


def rejected_versions(rows):
    out = []
    for r in rows:
        try:
            validate_definition(r['definition'])
        except Exception as exc:  # the registry's own refusal is the residue criterion
            out.append(r | {'reason': f'{type(exc).__name__}: {exc}'})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--tenant', default='hyd')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(DSN, row_factory=dict_row) as c:
        versions = c.execute('select arcv_id, proc_def_id, version, version_tag, definition, message from proc_def_version '
                             'where tenant_id = %s order by proc_def_id, version', (args.tenant,)).fetchall()
        heads = c.execute('select id, prod_version, definition, isdeleted from proc_def where tenant_id = %s',
                          (args.tenant,)).fetchall()
        bad = rejected_versions(versions)
        keys = [(b['proc_def_id'], b['version']) for b in bad]
        live = c.execute('select proc_inst_id, proc_def_id, proc_def_version from bpm_proc_inst where tenant_id = %s '
                         'and coalesce(is_deleted, false) = false and (proc_def_id, proc_def_version) in '
                         '(select * from unnest(%s::text[], %s::text[]))',
                         (args.tenant, [k[0] for k in keys], [k[1] for k in keys])).fetchall() if keys else []
        report = dict(tenant=args.tenant, versions=len(versions), rejected=[{k: b[k] for k in ('proc_def_id', 'version', 'reason')}
                                                                            for b in bad], live_instances=live, applied=False)
        (out / 'backup.json').write_text(json.dumps(dict(versions=bad, heads=[h for h in heads if h['id'] in {k[0] for k in keys}]),
                                                    ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        if args.apply and bad:
            if live:
                (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
                raise SystemExit(f'{len(live)} live instance(s) still use a rejected version, e.g. {live[0]} — run '
                                 'cleanup_residue_instances.py first; nothing deleted')
            with c.transaction():
                for def_id, version in keys:
                    c.execute('delete from proc_def_version where tenant_id = %s and proc_def_id = %s and version = %s',
                              (args.tenant, def_id, version))
                emptied = c.execute('delete from proc_def d where tenant_id = %s and id = any(%s) and not exists '
                                    '(select 1 from proc_def_version v where v.tenant_id = d.tenant_id and v.proc_def_id = d.id) '
                                    'returning id', (args.tenant, sorted({k[0] for k in keys}))).fetchall()
            report.update(applied=True, deleted_versions=len(keys), deleted_heads=[e['id'] for e in emptied])
        stale_heads = []
        for h in heads:
            try:
                validate_definition(h['definition'])
            except Exception as exc:
                stale_heads.append(dict(id=h['id'], prod_version=h['prod_version'], reason=str(exc)[:200]))
        report['heads_rejected_after'] = [s for s in stale_heads if s['id'] not in report.get('deleted_heads', [])]
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
