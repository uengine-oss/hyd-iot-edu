from helpers import *
import subprocess
soffice='C:/Program Files/LibreOffice/program/soffice.exe'
for p,out in [(EV/'before/산출물/교재/PPTX/통합반_온라인/통합반_09일차.pptx',EV/'source-render'),(C/'산출물/교재/PPTX/통합반_온라인/통합반_09일차.pptx',EV/'final-render')]:
 out.mkdir(parents=True,exist_ok=True)
 r=subprocess.run([soffice,'-env:UserInstallation='+(EV/'lo-profile').as_uri(),'--headless','--convert-to','pdf','--outdir',str(out),str(p)],capture_output=True,timeout=120)
 assert r.returncode==0,(r.stdout,r.stderr)
 f=out/(p.stem+'.pdf');assert len(PdfReader(f).pages)==74;print(str(f),flush=True)
render(EV/'final-render/통합반_09일차.pdf',EV/'final-render/pages')
out=C/'산출물/교재/PDF/통합반_온라인/통합반_09일차.pdf';out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(EV/'final-render/통합반_09일차.pdf',out)
# 대본은 전체를4쪽씩 묶어 읽는다.
pages=[]
for d in sorted((EV/'renders').iterdir()):
 for p in sorted(d.glob('[0-9][0-9][0-9].png')):pages.append((d.name,p))
folder=EV/'document-review';folder.mkdir(exist_ok=True)
font=__import__('PIL.ImageFont',fromlist=['truetype']).truetype('C:/Windows/Fonts/malgun.ttf',16)
for start in range(0,len(pages),4):
 sheet=Image.new('RGB',(1260,1810),'#dce1e6');draw=ImageDraw.Draw(sheet)
 for j,(name,p) in enumerate(pages[start:start+4]):
  im=Image.open(p).convert('RGB');im.thumbnail((610,860));x=10+(j%2)*630;y=35+(j//2)*900;sheet.paste(im,(x,y));draw.text((x,y-25),name+' '+p.stem,font=font,fill='black')
 sheet.save(folder/f'contact-{start//4+1:02}.png')
write(EV/'document-review-index.json',json.dumps([dict(folder=n,page=p.name) for n,p in pages],ensure_ascii=False,indent=2))
print('document pages',len(pages),flush=True)
