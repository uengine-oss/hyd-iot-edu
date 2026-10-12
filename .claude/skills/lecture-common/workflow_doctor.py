"""Read-only structural checks for the supported skills. Requires PyYAML.

The supported list is .claude/skills/lecture-common/workflow-skills.json
(falls back to .claude/workflow-skills.json).
"""
import argparse
import json
from pathlib import Path
import re
import sys

try:
    import yaml
except ImportError:
    raise SystemExit('PyYAML is required; no checks performed')


class UniqueLoader(yaml.SafeLoader):
    pass


def mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f'duplicate YAML key: {key}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)


def check(root):
    errors, skills = [], []
    listing = root / '.claude/skills/lecture-common/workflow-skills.json'
    if not listing.is_file():
        listing = root / '.claude/workflow-skills.json'
    names = json.loads(listing.read_text(encoding='utf-8-sig'))
    if not isinstance(names, list) or not names or len(names) != len(set(names)):
        raise ValueError('supported skill list must be nonempty and unique')
    for name in names:
        if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
            errors.append(f'invalid name: {name}')
            continue
        canonical = root / '.claude/skills' / name
        entry = canonical / 'SKILL.md'
        try:
            content = entry.read_text(encoding='utf-8-sig')
            match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', content, re.S)
            if not match:
                raise ValueError('missing YAML frontmatter')
            meta = yaml.load(match[1], Loader=UniqueLoader)
            if not isinstance(meta, dict):
                raise ValueError('frontmatter must be a mapping')
            if meta.get('name') != name:
                errors.append(f'{name}: metadata name differs')
            description = meta.get('description')
            if not isinstance(description, str) or not description.strip() or len(description) > 1024:
                errors.append(f'{name}: invalid description (nonempty string, <=1024 characters)')
            if meta.get('disable-model-invocation') is True:
                errors.append(f'{name}: implicit invocation disabled')
            if len(content.splitlines()) > 500:
                errors.append(f'{name}: SKILL.md over 500 lines')
            # Only explicit relative Markdown links are structural assertions here.
            prose = re.sub(r'```.*?```', '', content, flags=re.S)
            prose = re.sub(r'`[^`]*`', '', prose)
            for target in re.findall(r'\]\(([^)]+)\)', prose):
                if target.startswith(('https:', 'http:', '#', 'app:')):
                    continue
                local = target.split('#', 1)[0].strip('<>')
                if local and not (canonical / local).exists():
                    errors.append(f'{name}: broken Markdown resource link {local}')
            # Inline-code paths that are plainly relative to the skill folder are checked too.
            unfenced = re.sub(r'```.*?```', '', content, flags=re.S)
            for local in re.findall(r'`((?:\.\./|references/|scripts/|templates/|assets/)[^`\s<>*]+\.(?:md|py|json))`', unfenced):
                if not (canonical / local).exists():
                    errors.append(f'{name}: broken inline path {local}')
            skills.append({'name': name, 'description_chars': len(description or ''),
                           'lines': len(content.splitlines())})
        except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
            errors.append(f'{name}: {exc}')
    # A SKILL.md outside the supported list would still be discovered by the host.
    for entry in sorted((root / '.claude/skills').glob('*/SKILL.md')):
        if entry.parent.name not in names:
            errors.append(f'unlisted skill folder: {entry.parent.name}')
    if not (root / 'CLAUDE.md').is_file():
        errors.append('missing workspace entrypoint: CLAUDE.md')
    return {'errors': errors, 'skills': skills,
            'not_measured': ['host fresh-session selection', 'semantic correctness',
                             'task execution quality', 'host hook execution',
                             'non-Markdown or dynamic resource references']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    args = parser.parse_args()
    try:
        result = check(args.workspace.resolve(strict=True))
    except (OSError, ValueError, TypeError) as exc:
        result = {'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
