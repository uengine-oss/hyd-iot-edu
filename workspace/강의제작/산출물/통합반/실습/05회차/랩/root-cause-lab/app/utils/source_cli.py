"""자료 인용 행을 원문에서 그대로 표시한다. .env나 결과 파일은 열지 않는다."""
from pathlib import Path
import argparse
import gzip
from .evidence import read_json


def main(root):
    parser=argparse.ArgumentParser()
    parser.add_argument('file')
    parser.add_argument('start',type=int)
    parser.add_argument('end',type=int,nargs='?')
    args=parser.parse_args()
    return show_source(root,args.file,args.start,args.end)


def show_source(root,file,start,end=None):
    root=Path(root).resolve(); target=(root/file).resolve()
    if not any(target.is_relative_to(root/name) for name in ['data','자료','입력']):
        raise SystemExit('data/ 아래의 원문만 엽니다.')
    if start < 1 or (end or start) < start:
        raise SystemExit('줄 번호를 확인합니다.')
    encoding='utf-8-sig'
    for document in read_json(root / ('data/source_manifest.json' if (root/'data/source_manifest.json').is_file() else '입력/source_manifest.json'))['documents']:
        if document['file'] == target.name:
            encoding=document.get('encoding',encoding)
    stream=gzip.open(target,'rt',encoding=encoding) if target.suffix=='.gz' else target.open(encoding=encoding)
    with stream:
        for number,line in enumerate(stream,1):
            if number > (end or start): break
            if number >= start: print(f'{number}: {line.rstrip()}')

    return 0
