"""기존 덱 빌더의 글꼴·색·프레임으로 설명용 레이아웃을 렌더한다.

화면 구성의 `레이아웃: 관점격자 / 판단격자 / 계산기준선 / 지식변환`을 사용한다.
입력 내용은 덱 MD의 요소이며, 본문을 이 도구에 중복 저장하지 않는다.
"""
def render(m, sl, s, page, layout):
    if layout=='그래프경로':
        m.render_graph(sl,s,page)
        for shape in sl.shapes:
            if shape.has_text_frame and shape.text=='AnomalyPattern':
                shape.left-=m.Inches(.16)
                shape.width+=m.Inches(.32)
        return
    m.frame(sl, s, page)
    def text(x,y,w,h,value,size=17,color=None,bold=False):
        m.add_text(sl,x,y,w,h,value,size,color or m.NAVY,bold=bold,slide_no=s.no)
    if layout in ('관점격자','판단격자'):
        for i,it in enumerate(s.items):
            x=.6+(i%2)*6.2;y=1.85+(i//2)*2.55
            m.add_box(sl,x,y,5.93,2.3,m.WHITE,line=(m.LINE,1.25))
            text(x+.23,y+.18,5.47,.48,it.plain_title,18,bold=True)
            lines=it.lines
            text(x+.23,y+.76,5.47,.55,lines[0],17)
            if len(lines)>1:text(x+.23,y+1.36,5.47,.45,lines[1],16,m.SKY_D,True)
            if len(lines)>2:text(x+.23,y+1.88,5.47,.3,lines[2],12,m.MUTED)
    elif layout=='계산기준선':
        # 계산 → 집계 → 방향·기준 → 운영 책임 순서.
        a,b,c,d,e=s.items
        text(.85,1.95,11.7,.6,a.lines[0],27,bold=True)
        text(.85,2.65,11.7,.5,a.lines[1]+' · '+a.tag,17,m.MUTED)
        text(.85,3.24,11.7,.5,b.lines[0],18,m.SKY_D,True)
        m.add_box(sl,1.3,4.3,10.5,.035,m.NAVY,shape=m.MSO_SHAPE.RECTANGLE)
        for x,label,desc in [(2.4,d.lines[1],'한계에 닿는 수준'),(6.65,d.lines[0],'주의할 수준'),(10.9,'목표 '+c.lines[0],c.lines[1])]:
            m.add_box(sl,x,4.15,.025,.33,m.SKY_D,shape=m.MSO_SHAPE.RECTANGLE)
            text(x-1.65,4.6,3.5,.45,label,19,bold=True)
            text(x-1.65,5.14,3.5,.65,desc,14,m.MUTED)
        text(.85,6.05,11.7,.4,b.lines[1]+' · '+b.tag.replace(' / ',' '),15,m.MUTED)
        text(.85,6.57,11.7,.4,e.plain_title+': '+e.desc+' · '+e.tag,15,m.MUTED)
    elif layout=='지식변환':
        for i,it in enumerate(s.items):
            y=1.9+i*1.64
            text(.7,y,4.25,.38,it.plain_title,18,bold=True)
            text(.7,y+.49,4.25,1.02,it.lines[0],14)
            m.add_box(sl,5.15,y+.52,.55,.32,m.SKY_D,shape=m.MSO_SHAPE.RIGHT_ARROW)
            text(6.05,y,6.4,.4,it.tag.replace(' / ',' '),18,m.SKY_D,True)
            if i==0:
                import re
                category, chain = it.lines[1].removeprefix('→ ').split(': ',1)
                parts = re.split(r' -([A-Z_]+)→ ',chain)
                if len(parts)!=5:
                    raise ValueError('지식변환의 첫 결과는 세 노드와 두 관계여야 합니다')
                text(6.05,y+.46,6.4,.33,category,14,m.MUTED)
                for x,w,label in [(6.05,1.7,parts[0]),(8.55,1.7,parts[2]),(11.05,1.25,parts[4])]:
                    m.add_box(sl,x,y+1.02,w,.45,m.SKY_SOFT,line=(m.LINE,1))
                    text(x+.04,y+1.08,w-.08,.3,label,11)
                for x,label in [(7.78,parts[1]),(10.28,parts[3])]:
                    text(x-.25,y+.78,1.2,.24,label,8,m.MUTED)
                    m.add_box(sl,x,y+1.17,.7,.12,m.SKY_D,shape=m.MSO_SHAPE.RIGHT_ARROW)
            else:
                text(6.05,y+.5,6.4,1.05,it.lines[1].removeprefix('→ '),15)
    elif layout=='제안검토':
        for i,it in enumerate(s.items[:3]):
            x=.65+i*4.15
            m.add_box(sl,x,2.05,3.75,2.95,m.WHITE,line=(m.LINE,1.25))
            text(x+.2,2.3,3.35,.45,it.plain_title,21,bold=True)
            text(x+.2,3.0,3.35,1.05,it.desc.replace(' / ', '\n'),17)
            text(x+.2,4.35,3.35,.45,it.tag.replace(' / ', ' '),16,m.SKY_D,True)
            if i<2:m.add_box(sl,x+3.85,3.4,.22,.18,m.SKY_D,shape=m.MSO_SHAPE.RIGHT_ARROW)
        it=s.items[3]
        m.add_box(sl,.65,5.5,12.05,1.25,m.SKY_SOFT,line=(m.LINE,1))
        text(.9,5.78,3.0,.45,it.plain_title,20,bold=True)
        text(4.0,5.75,5.9,.75,it.desc.replace(' / ',' '),17)
        text(10.1,5.78,2.35,.7,it.tag.replace(' / ',' '),16,m.SKY_D,True)
    elif layout=='승인기록':
        for i,it in enumerate(s.items):
            x=.65+(i%2)*6.2;y=2.0+(i//2)*2.55
            m.add_box(sl,x,y,5.7,2.15,m.SKY_SOFT if it.strong else m.WHITE,line=(m.LINE,1.25))
            text(x+.2,y+.18,5.3,.4,it.plain_title,19,bold=True)
            text(x+.2,y+.75,5.3,.75,it.desc.replace(' / ','\n'),17)
            text(x+.2,y+1.62,5.3,.35,it.tag.replace(' / ',' · '),15,m.SKY_D,True)
        m.add_box(sl,6.43,5.45,.35,.22,m.SKY_D,shape=m.MSO_SHAPE.RIGHT_ARROW)
    elif layout=='출처연결':
        for i,it in enumerate(s.items[:3]):
            x=.65+i*4.15
            m.add_box(sl,x,2.05,3.75,3.25,m.SKY_SOFT if it.strong else m.WHITE,line=(m.LINE,1.25))
            text(x+.18,2.25,3.39,.8,it.plain_title,18,bold=True)
            text(x+.18,3.2,3.39,1.5,it.desc.replace(' / ','\n'),16)
            text(x+.18,4.88,3.39,.3,it.tag,14,m.SKY_D,True)
            if i<2:m.add_box(sl,x+3.85,3.55,.22,.18,m.SKY_D,shape=m.MSO_SHAPE.RIGHT_ARROW)
        it=s.items[3]
        m.add_box(sl,.65,5.65,12.05,1.05,m.SKY_SOFT,line=(m.LINE,1))
        text(.9,5.85,2.0,.4,it.plain_title,19,bold=True)
        text(3.15,5.8,9.2,.8,it.desc.replace(' / ','\n'),17)
    elif layout=='검증연결':
        # 변경 검증의 네 단계와 추천안마다 작동하는 실행 중 장치를 분리한다.
        for i,it in enumerate(s.items[:4]):
            x=.65+i*3.1
            m.add_box(sl,x,2.05,2.75,3.05,m.WHITE,line=(m.LINE,1.25))
            text(x+.18,2.27,2.39,.45,it.plain_title,21,bold=True)
            text(x+.18,3.0,2.39,1.35,it.desc.replace(' / ', '\n'),15)
            text(x+.18,4.52,2.39,.36,it.tag,14,m.SKY_D,True)
            if i<3:m.add_box(sl,x+2.82,3.45,.22,.18,m.SKY_D,shape=m.MSO_SHAPE.RIGHT_ARROW)
        it=s.items[4]
        m.add_box(sl,.65,5.65,12.05,1.05,m.SKY_SOFT,line=(m.LINE,1))
        text(.9,5.85,2.2,.4,it.plain_title,20,bold=True)
        text(3.15,5.82,9.2 if not it.tag else 7.0,.65,it.desc.replace(' / ', ' · '),17)
        text(10.2,5.91,2.2,.4,it.tag,14,m.SKY_D,True)
    else:
        raise ValueError(layout)
