"""Inspect recorded host evidence without calling a model or grading semantics."""
from pathlib import Path
import argparse, hashlib, json, re

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def normalized(text):
    return text.replace('\r\n', '\n').strip()

def command_path_text(text):
    # CLI traces can retain doubled Windows separators after JSON decoding.
    # Normalize only for recognition; never execute or resolve this command text.
    return re.sub(r'/+', '/', text.replace('\\', '/'))

def inspect(run, workspace, skill):
    run, workspace = Path(run), Path(workspace).resolve()
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', skill):
        raise ValueError('invalid skill name')
    meta = json.loads((run/'metadata.json').read_text(encoding='utf-8'))
    events = [json.loads(line) for line in (run/'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    entry = workspace/'.claude/skills'/skill/'SKILL.md'
    content = entry.read_text(encoding='utf-8-sig')
    body = normalized(re.sub(r'\A---\r?\n.*?\r?\n---\r?\n', '', content, count=1, flags=re.S))
    if not body:
        raise ValueError('empty skill body cannot be evidence')
    hashes = {name.replace('\\','/'):digest for name,digest in meta.get('source_sha256', {}).items()}
    changed, missing = [], []
    for rel, digest in hashes.items():
        p = workspace/rel
        if not p.resolve().is_relative_to(workspace):
            raise ValueError('source path escapes workspace')
        if not p.is_file(): missing.append(rel)
        elif sha(p) != digest: changed.append(rel)
    listing = '.claude/skills/lecture-common/workflow-skills.json'
    if not (workspace/listing).is_file():
        listing = '.claude/workflow-skills.json'
    required = ['CLAUDE.md', listing, f'.claude/skills/{skill}/SKILL.md']
    absent = [rel for rel in required if rel not in hashes]
    current = not (changed or missing or absent)
    seals = meta.get('artifact_sha256', {})
    integrity = 'unsealed'
    if seals:
        integrity = 'verified'
        for filename in ('prompt.txt', 'events.jsonl', 'stderr.txt'):
            p = run/filename
            if filename not in seals or not p.is_file() or sha(p) != seals[filename]:
                integrity = 'failed'
    terminal, failed, candidates, observed, texts = False, False, {}, [], []
    read_attempts=[]
    successful_tool_ids = set()
    for event in events:
        if event.get('type') == 'turn.completed': terminal = True
        if event.get('type') == 'turn.failed': failed = True
        if event.get('type') == 'result':
            terminal = event.get('subtype') == 'success' and event.get('is_error') is False
            failed = not terminal
        item = event.get('item', {})
        if event.get('type') == 'item.completed' and item.get('type') == 'command_execution':
            command=command_path_text(item.get('command',''))
            if f'/{skill}/SKILL.md' in command and ('Get-Content' in command or 'cat ' in command):
                read_attempts.append({'id':item.get('id'),'exit_code':item.get('exit_code'),
                                      'output_present':bool(item.get('aggregated_output'))})
            if item.get('exit_code') == 0 and body in normalized(item.get('aggregated_output', '')):
                observed.append({'kind':'command_body_delivery', 'id':item.get('id')})
        message = event.get('message') or {}
        if not isinstance(message,dict): continue
        blocks = message.get('content') or []
        if not isinstance(blocks, list): continue
        for block in blocks:
            if block.get('type') == 'tool_use':
                inputs = block.get('input') or {}
                if block.get('name') == 'Skill' and inputs.get('skill') == skill:
                    candidates[block['id']] = 'Skill'
                if block.get('name') == 'Read':
                    name = command_path_text(str(inputs.get('file_path', '')))
                    if name.endswith(f'/{skill}/SKILL.md'):
                        candidates[block['id']] = 'Read'
            if event.get('type') == 'user' and block.get('type') == 'text':
                texts.append(normalized(block.get('text','')))
            if block.get('type') == 'tool_result':
                tool_id = block.get('tool_use_id')
                value = block.get('content', '')
                if not isinstance(value,str):
                    value = '\n'.join(x.get('text','') for x in value or [] if isinstance(x,dict))
                if not block.get('is_error'):
                    successful_tool_ids.add(tool_id)
                    if candidates.get(tool_id) == 'Read' and body in normalized(value):
                        observed.append({'kind':'read_body_delivery','id':tool_id})
    for tool_id, kind in candidates.items():
        if kind == 'Skill' and tool_id in successful_tool_ids and any(body in t for t in texts):
            observed.append({'kind':'skill_body_delivery','id':tool_id})
    complete = terminal and not failed and meta.get('exit_code') == 0 and not meta.get('timed_out')
    mode = meta.get('invocation_mode', 'unknown')
    # Older records lack an explicit mode. Do not infer an automatic trial from a label.
    status = 'unverified'
    if complete and current and integrity == 'verified':
        status = 'verified' if observed else ('unverified' if read_attempts or candidates else 'not_observed')
    return {'host':meta.get('host'), 'skill':skill, 'mode':mode, 'terminal_success':complete,
            'read_attempts':read_attempts,
            'body_delivery':status, 'evidence':observed,
            'automatic_selection':status if mode == 'implicit' else 'not_tested',
            'current_sources':current, 'changed_sources':changed, 'missing_sources':missing,
            'unrecorded_sources':absent, 'artifact_integrity':integrity,
            'semantic_quality':'requires source and output review',
            'scope':'Recorded body delivery only; does not prove instruction adherence, UI, hooks, or full workflow quality'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--skill',required=True)
    args = p.parse_args()
    try:
        result = inspect(args.run,args.workspace,args.skill)
    except (OSError,ValueError,TypeError,KeyError) as error:
        print(json.dumps({'inspection_error':str(error),'body_delivery':'unverified'}))
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['body_delivery'] == 'verified' else 1

if __name__ == '__main__':
    raise SystemExit(main())
