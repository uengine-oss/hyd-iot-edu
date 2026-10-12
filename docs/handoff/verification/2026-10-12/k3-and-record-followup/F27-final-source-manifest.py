"""Freeze final source bytes separately from the previous whole-suite proof."""
import hashlib,json,subprocess,sys
from pathlib import Path
T=Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
H=Path(__file__).parent
TARGET=H/'F27-final-source-manifest.json'
def names(*args):
    return subprocess.check_output(['git','-C',str(T),*args],encoding='utf-8').splitlines()
def source(p):
    return p.startswith(('common/','it/','scripts/','tests/','students/','docs/samples/','docs/ontology/')) or ('/' not in p and p.endswith(('.py','.toml','.yml','.yaml','.json','.txt')) and not p.startswith('.env'))
paths=sorted(p for p in set(names('ls-files')+names('ls-files','--others','--exclude-standard')) if source(p))
actual={p:hashlib.sha256((T/p).read_bytes()).hexdigest() for p in paths if (T/p).is_file()}
if sys.argv[1]=='snapshot':
    prior=json.loads((H.parent/'delegated-review-20261012/whole-final-source-manifest.json').read_text(encoding='utf-8'))
    changed=sorted(p for p in set(actual)|{p for p in prior if source(p)} if actual.get(p)!=prior.get(p))
    owned=set(names('diff','HEAD','--name-only')+names('ls-files','--others','--exclude-standard'))
    protected=[p for p in owned if p.startswith(('docs/교재/','.claude/skills/lecture-deck/'))]
    assert not protected,protected
    result={'scope':'Final followup source freeze; previous whole-suite result does not cover changed bytes','source_sha256':actual,'source_files':len(actual),'changed_since_previous_whole_manifest':changed,'protected_changes':protected,'whole_reruns':0,'llm_reruns':0}
    TARGET.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'},ensure_ascii=False))
elif sys.argv[1]=='verify':
    expected=json.loads(TARGET.read_text(encoding='utf-8'))['source_sha256']
    changed=[p for p in set(actual)|set(expected) if actual.get(p)!=expected.get(p)]
    result={'passed':not changed,'source_files':len(actual),'changed_after_freeze':sorted(changed)}
    (H/'F27-final-source-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    sys.exit(0 if not changed else 1)
