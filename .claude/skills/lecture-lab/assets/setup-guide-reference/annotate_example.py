# 빨간 네모 그리기 / 관련 영역 크롭 예시. 좌표는 원본 픽셀 기준.
from PIL import Image, ImageDraw
def box(src, dst, b, w=5):
    im = Image.open(src).convert('RGB'); d = ImageDraw.Draw(im)
    for _ in range(w):
        d.rectangle(b, outline=(230, 30, 30)); b = (b[0]-1, b[1]-1, b[2]+1, b[3]+1)
    im.save(dst)
# print(Image.open('img/xxx.png').size)  # 반드시 원본 크기부터 확인
# box('img/xxx.png', 'img/a_xxx.png', (x1, y1, x2, y2))
# Image.open('img/xxx.png').crop((x1, y1, x2, y2)).save('img/c_xxx.png')  # 관련 영역만
