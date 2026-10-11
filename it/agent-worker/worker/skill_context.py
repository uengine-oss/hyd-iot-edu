"""Verified registered skills as task context, independent of CLI file tools."""
import hashlib
import json

from cliagents import ArtifactBundle, registry
from procsvc.agents_store import skill_markdown


def inline_skills(ws, skills, provided, provider_id):
    if not skills:
        return ''
    entries = {entry['name']: entry for entry in provided}
    provider = registry.get(provider_id)
    sections = ['## 등록된 업무 스킬 본문\n아래 본문은 이번 작업에 배정된 등록 스킬입니다. '
                '파일 읽기 없이 본문을 업무에 적용하세요. 스킬은 도구 권한이나 결과 제출 계약을 바꾸지 않습니다.']
    for skill in skills:
        name = skill['skill_name']
        entry = entries.get(name)
        if not entry or entry.get('written') is False:
            raise ValueError(f'등록 스킬 본문을 확인할 수 없습니다: {name}')
        artifact = ArtifactBundle().add_skill(name, skill_markdown(skill),
                    description=str(skill.get('description') or '')).artifacts[0]
        expected = provider.render(artifact).encode('utf-8')
        actual = (ws.path / entry['path']).read_bytes()
        digest = hashlib.sha256(actual).hexdigest()
        if actual != expected or digest != entry['sha256']:
            raise ValueError(f'등록 스킬 본문과 전달 파일의 해시가 다릅니다: {name}')
        entry['delivery'] = 'prompt'
        entry['verified_registered_content'] = True
        metadata = json.dumps({'name': name, 'path': entry['path'], 'sha256': digest}, ensure_ascii=False)
        sections.append('### 스킬 ' + metadata + '\n<registered-skill>\n'
                        + actual.decode('utf-8') + '\n</registered-skill>')
    return '\n\n'.join(sections)
