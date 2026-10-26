"""Windows 실습 시작. Python 표준 라이브러리만 사용한다."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import urllib.error
import uuid
import webbrowser
import zipfile

HERE = Path(__file__).resolve().parent
MAX_BYTES = 50 * 1024 * 1024

def download(url, target):
    if not (url.startswith('https://') or url.startswith('http://127.0.0.1:')):
        raise ValueError('다운로드 주소를 확인할 수 없습니다.')
    try:
        response = urllib.request.urlopen(url, timeout=30)
    except urllib.error.HTTPError as e:
        status = e.code
        e.close()
        raise RuntimeError(f'자료 다운로드 실패 (HTTP {status}). 다시 시도하거나 수동 ZIP을 이용하세요.') from None
    with response, target.open('wb') as out:
        size = 0
        while block := response.read(65536):
            size += len(block)
            if size > MAX_BYTES:
                raise ValueError('자료 크기가 허용 범위를 넘었습니다.')
            out.write(block)

def acquire(item, root, reopen=False):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    index = root / (item['id'] + '.json')
    if reopen and index.exists():
        record = json.loads(index.read_text(encoding='utf-8'))
        folder = Path(record['folder']).resolve()
        if not folder.is_relative_to(root) or not (folder/'guide.html').is_file():
            raise ValueError('기존 폴더를 찾을 수 없습니다. 새로 시작을 선택하세요.')
        return folder
    # 쓰기 권한 확인 + 기존 학생 폴더와 절대로 겹치지 않는 새 위치.
    with tempfile.TemporaryDirectory(prefix='.practice-', dir=root) as temp:
        temp = Path(temp)
        archive = temp/'package.zip'
        download(item['url'], archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('자료 판본이 일치하지 않습니다. 재시도하거나 수동 ZIP을 받으세요.')
        extracted = temp/'unpacked'; extracted.mkdir()
        with zipfile.ZipFile(archive) as z:
            if sum(info.file_size for info in z.infolist()) > MAX_BYTES:
                raise ValueError('압축 해제 크기가 허용 범위를 넘었습니다.')
            for info in z.infolist():
                name = PurePosixPath(info.filename)
                if name.is_absolute() or '..' in name.parts or '\\' in info.filename or ':' in info.filename or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ValueError('자료의 폴더 구조가 올바르지 않습니다.')
                dest = (extracted/Path(*name.parts)).resolve()
                if not dest.is_relative_to(extracted.resolve()):
                    raise ValueError('자료 경로 오류')
            z.extractall(extracted)
        folder = (extracted/item['folder']).resolve()
        if not folder.is_relative_to(extracted) or not (folder/'guide.html').is_file():
            raise ValueError('실습 가이드를 찾을 수 없습니다.')
        target = root/(item['id']+'-'+uuid.uuid4().hex[:8])
        shutil.move(str(folder), str(target))
    pending = index.with_suffix('.tmp')
    pending.write_text(json.dumps({'folder':str(target),'version':item['version']},ensure_ascii=False),encoding='utf-8')
    pending.replace(index)
    return target

def code_executable():
    cmd = shutil.which('code')
    if cmd:
        candidate = Path(cmd).resolve().parent.parent/'Code.exe'
        if candidate.is_file(): return candidate
    for candidate in [Path(os.environ.get('LOCALAPPDATA',''))/'Programs/Microsoft VS Code/Code.exe',Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Microsoft VS Code/Code.exe']:
        if candidate.is_file(): return candidate
    raise FileNotFoundError('VS Code를 찾지 못했습니다. VS Code의 파일 → 폴더 열기로 아래 폴더를 여세요.')

def open_document(target):
    if os.name == 'nt':
        # 기본 브라우저의 ShellExecute/DDE 응답이 멈춰도 시작 도구는 복구 가능해야 한다.
        try:
            subprocess.run([sys.executable,'-c','import os,sys; os.startfile(sys.argv[1])',str(target)],
                           timeout=10,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired:
            raise RuntimeError('기본 앱의 열기 응답이 늦습니다. 아래 파일 또는 주소를 직접 여세요.\n'+str(target)) from None
    else:
        webbrowser.open(str(target))

def open_lab(folder):
    folder = Path(folder).resolve()
    exe = code_executable()
    subprocess.Popen([str(exe),'--new-window',str(folder),str(folder/'START.md')],shell=False)
    open_document(folder/'guide.html')

def main():
    import tkinter as tk
    from tkinter import ttk
    manifest=json.loads((HERE/'catalog.json').read_text(encoding='utf-8'))
    items=manifest['labs']
    root=Path(json.loads((HERE/'settings.json').read_text(encoding='utf-8'))['practice_root'])
    window=tk.Tk();window.title('HYD 실습 시작');window.geometry('640x510');window.configure(bg='#f4f6f2')
    style=ttk.Style();style.theme_use('clam');style.configure('TLabel',background='#f4f6f2',font=('맑은 고딕',11));style.configure('TButton',font=('맑은 고딕',11),padding=10)
    panel=ttk.Frame(window,padding=28);panel.pack(fill='both',expand=True)
    ttk.Label(panel,text='오늘의 실습 시작',font=('맑은 고딕',21,'bold')).pack(anchor='w',pady=(0,20))
    course=tk.StringVar();session=tk.StringVar();lab=tk.StringVar()
    boxes=[]
    for title,var in [('과정',course),('회차',session),('실습',lab)]:
        ttk.Label(panel,text=title).pack(anchor='w')
        box=ttk.Combobox(panel,textvariable=var,state='readonly',font=('맑은 고딕',11));box.pack(fill='x',pady=(4,10));boxes.append(box)
    def update_session(*_):
        values=list(dict.fromkeys(x['session'] for x in items if x['course']==course.get()));boxes[1]['values']=values;session.set(values[0]);update_lab()
    def update_lab(*_):
        values=[x['title'] for x in items if x['course']==course.get() and x['session']==session.get()];boxes[2]['values']=values;lab.set(values[0])
    boxes[0]['values']=list(dict.fromkeys(x['course'] for x in items));course.set(boxes[0]['values'][0]);update_session()
    boxes[0].bind('<<ComboboxSelected>>',update_session);boxes[1].bind('<<ComboboxSelected>>',update_lab)
    def selected():return next(x for x in items if x['course']==course.get() and x['session']==session.get() and x['title']==lab.get())
    message=tk.StringVar(value='새로 시작하면 별도 폴더에 자료를 받습니다.\n저장 위치: '+str(root))
    buttons=ttk.Frame(panel);buttons.pack(fill='x',pady=10)
    controls=[]
    def launch(reopen=False):
        item=selected()
        for b in controls:b.configure(state='disabled')
        message.set('자료를 준비하고 있습니다…')
        def work():
            folder=None
            try:
                folder=acquire(item,root,reopen);open_lab(folder)
                text='VS Code와 가이드 열기를 요청했습니다. 열린 폴더와 START.md를 확인하세요.\n'+str(folder)
            except Exception as e:
                text=str(e)+(('\n'+str(folder)) if folder else '')+'\n다시 시도하거나 수동 ZIP을 이용하세요.'
            window.after(0,lambda:done(text))
        threading.Thread(target=work,daemon=True).start()
    def done(text):
        message.set(text)
        for b in controls:b.configure(state='normal')
    def manual():
        url=selected()['url']
        for b in controls:b.configure(state='disabled')
        def work():
            try:
                open_document(url);text='브라우저에서 ZIP 다운로드를 확인하세요.\n'+url
            except Exception as e:text=str(e)
            window.after(0,lambda:done(text))
        threading.Thread(target=work,daemon=True).start()
    for label,command in [('새로 시작',lambda:launch(False)),('이전 작업 열기',lambda:launch(True)),('수동 ZIP',manual)]:
        b=ttk.Button(buttons,text=label,command=command);b.pack(side='left',padx=(0,8));controls.append(b)
    ttk.Label(panel,textvariable=message,wraplength=560).pack(anchor='w',pady=12)
    ttk.Label(panel,text='재부팅 전, 보관할 결과는 USB 또는 개인 클라우드에 복사하세요.',wraplength=560).pack(anchor='w',side='bottom')
    window.mainloop()

if __name__=='__main__':main()
