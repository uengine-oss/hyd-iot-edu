"""Build a local, keyboard-accessible viewer from an existing capture manifest.

Usage: python scripts/ui_gallery.py UIUX_캡처_2026-10-01_102354
Only index.html is regenerated; the original screenshots and manifest are kept.
"""
import html
import json
import sys
from pathlib import Path


def build(folder: Path):
    data = json.loads((folder / '목록.json').read_text(encoding='utf-8'))
    images = data['images']
    cards = ''.join(
        f'<button class="card" data-index="{i}" data-search="{html.escape(x["title"] + " " + x["group"], quote=True)}">'
        f'<img loading="lazy" alt="" src="{html.escape(x["file"], quote=True)}">'
        f'<strong>{html.escape(x["title"])}</strong><small>{html.escape(x["group"])}</small></button>'
        for i, x in enumerate(images)
    )
    page = TEMPLATE.replace('%%CARDS%%', cards).replace('%%INTRO%%', html.escape(data['description']))
    page = page.replace('%%DATA%%', json.dumps(images, ensure_ascii=False).replace('<', '\\u003c'))
    (folder / 'index.html').write_text(page, encoding='utf-8')
    print(folder / 'index.html')


TEMPLATE = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>UIUX 화면 둘러보기</title>
<style>
*{box-sizing:border-box}body{font:14px/1.6 'Segoe UI','Malgun Gothic',sans-serif;margin:0;background:#f4f6fb;color:#18243b}header,main{max-width:1600px;margin:auto;padding:28px 32px}header{padding-bottom:0}h1{font-size:30px;margin:0}p{max-width:100ch;color:#526079}button,input,select{font:inherit}button{cursor:pointer;min-height:40px;border:1px solid #d5deeb;border-radius:8px;background:white;color:#18243b;padding:8px 16px}button:disabled{opacity:.4;cursor:default}button:hover:not(:disabled){background:#edf1ff}button.primary{background:#3859d6;color:white;border-color:#3859d6}:focus-visible{outline:3px solid #7795ff;outline-offset:3px}.tools{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.tools input{border:1px solid #c8d3e3;border-radius:8px;padding:10px 14px;min-width:250px}#count{color:#61718b}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}.card{text-align:left;padding:12px;border:1px solid #dce3ed;border-radius:12px}.card[hidden]{display:none}.card img{width:100%;height:190px;object-fit:contain;background:#eef1f6}.card strong,.card small{display:block;overflow-wrap:anywhere}.card strong{padding-top:10px}.card small{color:#61718b}
dialog{padding:0;border:0;width:100vw;height:100dvh;max-width:none;max-height:none;margin:0;background:#111a29;color:#e6ecf6}dialog[open]{display:grid;grid-template-rows:auto minmax(0,1fr) auto}dialog::backdrop{background:#111a29}.viewer-head,.viewer-foot{display:flex;gap:12px;align-items:center;padding:12px 20px;background:#1b273b}.viewer-head h2{font-size:15px;margin:0;overflow-wrap:anywhere;min-width:0}.viewer-head .close{margin-left:auto;flex-shrink:0}.viewer-foot{justify-content:center;flex-wrap:wrap}.viewer-foot select{background:#fff;border:0;border-radius:6px;padding:6px}.viewer-foot button{flex-shrink:0}.viewer-foot .position{min-width:75px;text-align:center}.canvas{min-height:0;overflow:auto;display:flex;align-items:center;justify-content:center;padding:12px}.canvas img{max-width:100%;max-height:100%;object-fit:contain}.canvas.zoom{display:block}.canvas.zoom img{max-width:none;max-height:none;display:block;margin:auto}.shortcut{font-size:12px;color:#abb8ce}.viewer-foot button[aria-pressed=true]{background:#d9e3ff;color:#18243b}.error{color:#ffb8c4;padding:24px}.error[hidden]{display:none}@media(max-width:600px){header,main{padding:20px 16px}.viewer-head{padding:10px 12px}.viewer-foot{gap:8px;padding:10px}.shortcut{display:none}.viewer-foot button{padding:8px 10px}.canvas{padding:4px}.viewer-head h2{font-size:12px}}
</style></head><body>
<header><h1>UIUX 화면 둘러보기</h1><p>%%INTRO%%</p>
<div class="tools"><input id="search" type="search" placeholder="화면 이름으로 검색" aria-label="캡처 검색"><button class="primary" id="start">순서대로 보기</button><button id="startAuto">자동으로 보기</button><span id="count"></span></div><p>사진을 한 번 열면 ← → 키로 이동합니다. 자동 재생은 간격을 선택할 수 있고, Esc로 목록에 돌아옵니다.</p></header>
<main>%%CARDS%%</main>
<dialog id="viewer" aria-labelledby="pictureTitle"><div class="viewer-head"><h2 id="pictureTitle"></h2><button class="close" id="close">닫기 Esc</button></div>
<div class="canvas" id="canvas" tabindex="0" aria-label="사진 보기. 좌우 키로 이동, Space로 자동 재생"><img id="picture" alt=""><p class="error" id="loadError" hidden>이미지를 불러오지 못했습니다. 캡처 파일이 같은 폴더에 있는지 확인하세요.</p></div>
<div class="viewer-foot"><button id="prev" aria-label="이전 사진">← 이전</button><span class="position" id="position" aria-live="polite"></span><button id="next" aria-label="다음 사진">다음 →</button><button id="play" aria-pressed="false">자동 재생</button><label>간격 <select id="delay"><option value="3">3초</option><option value="6" selected>6초</option><option value="10">10초</option></select></label><button id="zoom" aria-pressed="false">원본 크기</button><span class="shortcut">← → 이동 · Space 재생/정지</span></div></dialog>
<script>
const images=%%DATA%%;
const $=id=>document.getElementById(id), cards=[...document.querySelectorAll('.card')];
let list=images.map((_,i)=>i),cursor=0,timer=null;
function pause() {clearTimeout(timer);timer=null;$('play').setAttribute('aria-pressed','false');$('play').textContent='자동 재생';}
function schedule(){clearTimeout(timer);timer=setTimeout(()=>{if(cursor<list.length-1){show(cursor+1);schedule()}else pause()},Number($('delay').value)*1000);}
function play(){if(cursor===list.length-1)show(0);$('play').setAttribute('aria-pressed','true');$('play').textContent='일시 정지';schedule();}
function fit(){ $('canvas').classList.remove('zoom');$('zoom').setAttribute('aria-pressed','false');$('zoom').textContent='원본 크기'; }
function show(at){cursor=at;const x=images[list[cursor]];fit();$('loadError').hidden=true;$('picture').hidden=false;$('picture').src=x.file;$('picture').alt=x.title;$('pictureTitle').textContent=x.title+' · '+x.group;$('position').textContent=`${cursor+1} / ${list.length}`;$('prev').disabled=cursor===0;$('next').disabled=cursor===list.length-1;$('canvas').scrollTo(0,0);}
function open(index,auto=false){if(!list.length)return;show(Math.max(0,list.indexOf(index)));$('viewer').showModal();document.body.style.overflow='hidden';$('canvas').focus();if(auto)play();}
function move(by){pause();show(Math.min(list.length-1,Math.max(0,cursor+by)));}
$('picture').addEventListener('error',()=>{pause();$('picture').hidden=true;$('loadError').hidden=false;});
cards.forEach(c=>c.addEventListener('click',()=>open(Number(c.dataset.index))));
function filter(){const q=$('search').value.toLowerCase().trim();list=[];cards.forEach(c=>{c.hidden=!c.dataset.search.toLowerCase().includes(q);if(!c.hidden)list.push(Number(c.dataset.index));});$('count').textContent=`${list.length} / ${images.length}장`;$('start').disabled=$('startAuto').disabled=!list.length;}
$('search').addEventListener('input',filter);filter();
$('start').onclick=()=>open(list[0]);$('startAuto').onclick=()=>open(list[0],true);
$('close').onclick=()=>$('viewer').close();$('viewer').addEventListener('close',()=>{pause();document.body.style.overflow='';});
$('prev').onclick=()=>move(-1);$('next').onclick=()=>move(1);$('play').onclick=()=>timer?pause():play();
$('delay').onchange=()=>{if(timer)schedule()};
$('zoom').onclick=()=>{pause();const zoom=$('canvas').classList.toggle('zoom');$('zoom').setAttribute('aria-pressed',String(zoom));$('zoom').textContent=zoom?'화면에 맞추기':'원본 크기';};
$('viewer').addEventListener('keydown',e=>{if(e.target.tagName==='SELECT')return;if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();move(e.key==='ArrowLeft'?-1:1)}if(e.code==='Space'&&e.target.tagName!=='BUTTON'){e.preventDefault();timer?pause():play();}});
let touchX=null;$('canvas').addEventListener('touchstart',e=>{touchX=e.touches[0].clientX},{passive:true});$('canvas').addEventListener('touchend',e=>{if(touchX!==null&&!$('canvas').classList.contains('zoom')){const d=e.changedTouches[0].clientX-touchX;if(Math.abs(d)>70)move(d<0?1:-1)}touchX=null;},{passive:true});
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause()});
</script></body></html>'''

if __name__ == '__main__':
    build(Path(sys.argv[1]).resolve())
