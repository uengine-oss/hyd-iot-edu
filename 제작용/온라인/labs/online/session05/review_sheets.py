"""이미 렌더한 대본 PDF를 전쪽 배치 확인용 4쪽 묶음으로 만든다."""
from helpers import *
pages=[]
for d in sorted((EV/'renders').iterdir()):
 for p in sorted(d.glob('[0-9][0-9][0-9].png')):pages.append((d.name,p))
folder=EV/'document-review';folder.mkdir(exist_ok=True)
font=__import__('PIL.ImageFont',fromlist=['truetype']).truetype('C:/Windows/Fonts/malgun.ttf',16)
for start in range(0,len(pages),4):
 sheet=Image.new('RGB',(1260,1810),'#dce1e6');draw=ImageDraw.Draw(sheet)
 for j,(name,p) in enumerate(pages[start:start+4]):
  im=Image.open(p).convert('RGB');im.thumbnail((610,860));x=10+(j%2)*630;y=35+(j//2)*900;sheet.paste(im,(x,y));draw.text((x,y-25),name.replace('강사대본','')+' '+p.stem,font=font,fill='black')
 sheet.save(folder/f'contact-{start//4+1:02}.png')
write(EV/'document-review-index.json',json.dumps([dict(folder=n,page=p.name) for n,p in pages],ensure_ascii=False,indent=2))
print(len(pages),'pages', (len(pages)+3)//4,'sheets')
