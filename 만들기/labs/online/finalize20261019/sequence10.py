from helpers import *
edits=json.loads((EV/'finish10-edits.json').read_text('utf8'))
for root,course,day,practical in [(C,'통합반',10,False),(D,'실전반',7,True)]:
 folder=root/f'산출물/교재/대본/{course}_온라인/{day:02}회차';p=folder/'01_이론_프로세스설계재사용.md'
 a='재고 보충은 그림부터 남아 있습니다.';b='이어서 재고 보충의 그림부터 만들어 보겠습니다.'
 s=p.read_text('utf8');assert a in s;write(p,s.replace(a,b));edits.append(dict(path=str(p),before=a,after=b,reason='실습2 시점에 아직 하지 않은 실습3의 그림을 이미 만들었다고 말하지 않음'))
 patch_notes(folder,61,root/f'만들기/decks/{"practical" if practical else "integrated"}/day{day:02}/{course}_{day:02}일차.md',root/f'산출물/교재/PPTX/{course}_온라인/{course}_{day:02}일차.pptx')
 merge(root,folder,practical)
 merged=folder.parent/f'{course}_{day:02}일차_대본.md';write(merged,re.sub(r'\]\((\d{2}_[^/)]+\.md)\)',rf']({day:02}회차/\1)',merged.read_text('utf8')))
 pdf((folder.parent/f'낭독본/{course}_{day:02}일차_낭독본.md').read_text('utf8'),folder.parent/f'{course}_{day:02}일차_대본.pdf')
write(EV/'finish10-edits.json',json.dumps(edits,ensure_ascii=False,indent=2))
prior=json.loads((EV/'finish10-pdf-check.json').read_text('utf8'));updated={x['file']:x for x in checks};write(EV/'finish10-pdf-check.json',json.dumps([updated.get(x['file'],x) for x in prior],ensure_ascii=False,indent=2))
