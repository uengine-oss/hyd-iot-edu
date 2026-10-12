#!/bin/bash
# usage: ./render.sh doc2   (doc2.py -> doc2.html -> doc2.pdf + _doc2_montage.png)
set -e
D=$1
python3 $D.py
python3 -c "
from weasyprint import HTML
HTML('$D.html', base_url='.').write_pdf('$D.pdf')"
pdfinfo $D.pdf | grep Pages
rm -f prev-*.png
pdftoppm -png -r 45 $D.pdf prev
python3 - <<PY
from PIL import Image; import glob
fs=sorted(glob.glob('prev-*.png')); ims=[Image.open(f) for f in fs]
w,h=ims[0].size; cols=6; rows=(len(ims)+cols-1)//cols
s=Image.new('RGB',(cols*w,rows*h),'grey')
for i,im in enumerate(ims): s.paste(im,((i%cols)*w,(i//cols)*h))
s.save('_${D}_montage.png'); print('montage: _${D}_montage.png')
PY
