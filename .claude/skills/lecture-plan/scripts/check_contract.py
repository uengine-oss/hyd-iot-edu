"""Check traceability and stale files, not semantics. Paths are relative to project_root."""
import argparse
import hashlib
import json
from pathlib import Path


def check(path, complete=False):
    errors = []
    doc = json.loads(path.read_text(encoding='utf-8-sig'))
    root = (path.parent / doc['project_root']).resolve(strict=True)
    if doc.get('version') != 1:
        errors.append('unsupported version')

    def file_ref(ref, label):
        p = (root / ref['path']).resolve()
        if not p.is_relative_to(root):
            errors.append(f'{label}: path outside project')
            return
        if not p.is_file():
            errors.append(f'{label}: missing file {ref["path"]}')
            return
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != ref.get('sha256'):
            errors.append(f'{label}: stale or missing SHA256')

    sources = doc.get('sources', [])
    requirements = doc.get('requirements', [])
    if not sources or not requirements:
        errors.append('sources and requirements must be nonempty')
    source_ids = set()
    for source in sources:
        sid = source['id']
        if not sid or sid in source_ids:
            errors.append(f'duplicate or empty source id: {sid}')
        source_ids.add(sid)
        file_ref(source, f'source {sid}')
        if not source.get('read_scope'):
            errors.append(f'source {sid}: missing read scope')
        if complete and source.get('reviewed') is not True:
            errors.append(f'source {sid}: source review unverified')
    ids = set()
    for req in requirements:
        rid = req['id']
        if not rid or rid in ids:
            errors.append(f'duplicate or empty requirement id: {rid}')
        ids.add(rid)
        if req.get('source_id') not in source_ids:
            errors.append(f'{rid}: unknown source')
        for field in ('text', 'source_anchor', 'acceptance'):
            if not isinstance(req.get(field), str) or not req[field].strip():
                errors.append(f'{rid}: missing {field}')
        if type(req.get('required')) is not bool:
            errors.append(f'{rid}: required must be boolean')
        if req.get('status') not in ('verified', 'failed', 'unverified', 'not_applicable'):
            errors.append(f'{rid}: invalid status')
        for target in req.get('targets', []):
            file_ref(target, f'{rid} target')
            if not target.get('anchor'):
                errors.append(f'{rid}: missing target anchor')
        for evidence in req.get('evidence', []):
            file_ref(evidence, f'{rid} evidence')
        if req.get('status') == 'verified':
            if not req.get('targets') or not req.get('evidence') or not req.get('review_note'):
                errors.append(f'{rid}: verified needs targets, evidence and direct review note')
        if complete and req.get('required') is True and req.get('status') != 'verified':
            errors.append(f'{rid}: required requirement is not verified')
        if req.get('status') == 'not_applicable' and not req.get('review_note'):
            errors.append(f'{rid}: not_applicable needs reason')
    return {'errors': errors, 'source_count': len(sources), 'requirement_count': len(requirements),
            'semantic_review': 'not measured; human/agent source-to-artifact review required'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger', type=Path)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    try:
        result = check(args.ledger.resolve(), args.require_complete)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
