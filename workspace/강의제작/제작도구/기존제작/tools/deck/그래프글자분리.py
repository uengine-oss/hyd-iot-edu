"""기존 matplotlib 생성기의 데이터·도형을 보존하고 글자를 별도 좌표로 내보낸다.

python 그래프글자분리.py <원생성기.py> <글자없는그림.png> <글자좌표.json>
원 생성기의 savefig는 차단한다. 입력 파일은 읽기 전용이며 원 그림은 덮어쓰지 않는다.
내보낸 좌표는 그림 왼쪽 위 기준 인치이다. 원 그래프와 같은 크기로 PPTX에 놓으면
각 글자를 같은 중심·글꼴·회전으로 고칠 수 있는 글상자에 옮길 수 있다.
"""
from pathlib import Path
import argparse,hashlib,json,sys
def separate(source,png,labels):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.figure import Figure
 from matplotlib.text import Text
 source=Path(source).resolve();png=Path(png).resolve();labels=Path(labels).resolve()
 if source in [png,labels] or png==labels:raise ValueError('입력/출력 경로가 같음')
 code=source.read_text('utf8')
 # The original generators use the macOS font directory. Resolve only those
 # two font files locally without changing source, chart data or geometry.
 for name in ['malgun.ttf','malgunbd.ttf']:
  original='str(Path.home() / "Library/Fonts/'+name+'")'
  windows=Path('C:/Windows/Fonts')/name
  if windows.exists():code=code.replace(original,repr(str(windows)))
 saved=Figure.savefig;captured=[];old_argv=sys.argv
 try:
  Figure.savefig=lambda fig,*a,**kw:captured.append((fig,a[0] if a else kw.get('fname')))
  sys.argv=[str(source)]
  scope={'__file__':str(source),'__name__':'__chart_layer__'};exec(compile(code,str(source),'exec'),scope)
 finally:Figure.savefig=saved;sys.argv=old_argv
 original_targets={Path(target).resolve() for fig,target in captured if isinstance(target,(str,Path))}
 if original_targets & {png,labels}:raise ValueError('원 생성기의 그림 경로를 출력으로 사용할 수 없음')
 fig=scope.get('fig') or captured[-1][0];fig.canvas.draw();renderer=fig.canvas.get_renderer();w,h=map(float,fig.get_size_inches());dpi=fig.dpi;items=[]
 tick_labels=set();drawn_tick_labels=set()
 for ax in fig.axes:
  for axis in (ax.xaxis,ax.yaxis):
   for tick in axis.get_major_ticks()+axis.get_minor_ticks():tick_labels.update([id(tick.label1),id(tick.label2)])
   for tick in axis._update_ticks():drawn_tick_labels.update([id(tick.label1),id(tick.label2)])
 for artist in fig.findobj(match=Text):
  if not artist.get_visible() or not artist.get_text():continue
  if id(artist) in tick_labels and id(artist) not in drawn_tick_labels:continue
  bb=artist.get_window_extent(renderer);rot=float(artist.get_rotation());color=matplotlib.colors.to_hex(artist.get_color());items.append({'text':artist.get_text(),'center_x_in':(bb.x0+bb.x1)/2/dpi,'center_y_in':h-(bb.y0+bb.y1)/2/dpi,'bbox_w_in':bb.width/dpi,'bbox_h_in':bb.height/dpi,'font_pt':float(artist.get_fontsize()),'font_weight':str(artist.get_fontweight()),'color':color,'rotation_ccw':rot})
 for artist in fig.findobj(match=Text):artist.set_visible(False)
 png.parent.mkdir(parents=True,exist_ok=True);fig.savefig(png,facecolor='white')
 source_name=str(source.relative_to(Path.cwd())) if source.is_relative_to(Path.cwd()) else source.name
 csv_inputs={(str(p.relative_to(Path.cwd())) if p.is_relative_to(Path.cwd()) else p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.parent.glob('*.csv')}
 data={'source':source_name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'csv_inputs':csv_inputs,'width_in':w,'height_in':h,'dpi':dpi,'labels':items,'method':'같은 Figure의 Text만 숨김;Line2D·Path·데이터·축lim·spine·눈금선·위치 불변','background_sha256':hashlib.sha256(png.read_bytes()).hexdigest()};labels.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8');plt.close(fig);return data
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('png');p.add_argument('labels');a=p.parse_args();r=separate(a.source,a.png,a.labels);print(f"text layers {len(r['labels'])}, graph {r['width_in']}×{r['height_in']} in")
