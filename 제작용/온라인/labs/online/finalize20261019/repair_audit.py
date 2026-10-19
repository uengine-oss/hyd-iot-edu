from helpers import *
import subprocess
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
back=EV/'audit-before';changes=[]
def backup(p,root,kind):
 target=back/kind/p.relative_to(root)
 assert not target.exists(),('Do not rerun',target)
 target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
 changes.append(dict(file=str(p),before_sha256=sha(p),backup=str(target)))
folder=D/'산출물/교재/대본/실전반_온라인/01회차';ppt=D/'산출물/교재/PPTX/실전반_온라인/실전반_01일차.pptx';deck=D/'만들기/decks/practical/day01/실전반_01일차.md'
for p in [ppt,deck,folder/'구성.json']:backup(p,D,'practical')
patch_notes(folder,78,deck,ppt)
for item in json.loads((EV/'duplicate-pdf-review.json').read_text('utf8')):
 p=Path(item['file']);backup(p,C,'integrated');shutil.copy2(item['current'],p)
for root,kind,course in [(C,'integrated','통합반'),(D,'practical','실전반')]:
 ppt=root/f'산출물/교재/PPTX/{course}_온라인/{course}_01일차.pptx';out=EV/f'final-render/{kind}01';out.mkdir(parents=True,exist_ok=True)
 r=subprocess.run(['C:/Program Files/LibreOffice/program/soffice.exe','-env:UserInstallation='+(EV/f'lo-audit-{kind}').as_uri(),'--headless','--convert-to','pdf','--outdir',str(out),str(ppt)],capture_output=True,timeout=120);assert r.returncode==0
 pf=out/(ppt.stem+'.pdf');target=root/f'산출물/교재/PDF/{course}_온라인/{ppt.stem}.pdf';assert not target.exists();target.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(pf,target);render(pf,out)
 # Keep legacy session2 location; add the current standard delivery location.
 old=root/f'산출물/교재/PPTX/{course}_온라인/{course}_02일차.pdf';new=root/f'산출물/교재/PDF/{course}_온라인/{course}_02일차.pdf';assert not new.exists();shutil.copy2(old,new)
for item in changes:item['after_sha256']=sha(Path(item['file']))
write(EV/'audit-repairs.json',json.dumps(changes,ensure_ascii=False,indent=2));print('Audit repairs and first-session rendering done')
