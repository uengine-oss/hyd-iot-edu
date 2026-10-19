"""문서 변환만 실행한다. 실습 또는 브라우저 실행 없음."""
from helpers import *
import subprocess
soffice='C:/Program Files/LibreOffice/program/soffice.exe'
jobs=[(EV/'before/산출물/교재/PPTX/통합반_온라인/통합반_08일차.pptx',EV/'source-render'),(EV/'before/산출물/교재/PPTX/통합반_온라인/통합반_11일차.pptx',EV/'source-render'),(C/'산출물/교재/PPTX/통합반_온라인/통합반_08일차.pptx',EV/'final-render'),(D/'산출물/교재/PPTX/실전반_온라인/실전반_08일차.pptx',EV/'final-render')]
for p,out in jobs:
 out.mkdir(parents=True,exist_ok=True)
 r=subprocess.run([soffice,'-env:UserInstallation='+ (EV/'lo-profile').as_uri(),'--headless','--convert-to','pdf','--outdir',str(out),str(p)],capture_output=True,timeout=120)
 assert r.returncode==0,(p,r.stderr)
 f=out/(p.stem+'.pdf');assert f.exists(),(p,r.stdout,r.stderr)
 print(str(f),len(PdfReader(f).pages),flush=True)
