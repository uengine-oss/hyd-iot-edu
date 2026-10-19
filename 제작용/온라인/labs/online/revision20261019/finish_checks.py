"""Document checks only: never imports or runs student code."""
from pathlib import Path
import sys,json,hashlib,importlib.util
D=Path('D:/work/study/hyd-portal-latest-20261014');C=Path('D:/work/study/hyd-integrated-recovered-20261018');EV=D/'.evidence/online-revision-20261019'
sys.argv=[__file__,str(C)]
spec=importlib.util.spec_from_file_location('helpers',D/'만들기/labs/online/finalize20261019/helpers.py');H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H);H.EV=EV;sys.modules['helpers']=H
exec(compile((D/'만들기/labs/online/finalize20261019/audit.py').read_text('utf8'),'<read-only-audit>','exec'))
