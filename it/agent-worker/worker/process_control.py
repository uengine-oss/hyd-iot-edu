"""Cancellable synchronous adapter of process-gpt-cli-agent/core/runner.py.

The pump retains cliagents' parser and teardown. The caller checks its deadline
and database state independently of stdout. Each run owns its process tree.
Windows job lifetime: https://learn.microsoft.com/windows/win32/procthread/job-objects

POSIX has no job object. The worker's stop signals (SIGTERM · SIGHUP, main.install_stop_signals) unwind into the
`finally` below, which kills the run's process group. A worker that dies without unwinding (SIGKILL, OOM) leaves the
group's id in the workspace (GROUP_FILE); the next run in that workspace kills that group before it starts
(reap_stale_group), so an orphaned CLI cannot keep calling tools or write output/result.json under the new run.
"""
import json
import logging
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
from .diagnostics import excerpt


class _WindowsJob:
    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w
        class Basic(c.Structure):
            _fields_=[('process_time',c.c_int64),('job_time',c.c_int64),('flags',w.DWORD),
                      ('min_working',c.c_size_t),('max_working',c.c_size_t),('active',w.DWORD),
                      ('affinity',c.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(c.Structure):
            _fields_=[(name,c.c_uint64) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class Extended(c.Structure):
            _fields_=[('basic',Basic),('io',IO),('process_memory',c.c_size_t),('job_memory',c.c_size_t),
                      ('peak_process_memory',c.c_size_t),('peak_job_memory',c.c_size_t)]
        self.api=c.WinDLL('kernel32',use_last_error=True)
        self.api.CreateJobObjectW.argtypes=[c.c_void_p,w.LPCWSTR];self.api.CreateJobObjectW.restype=w.HANDLE
        self.api.SetInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD]
        self.api.SetInformationJobObject.restype=w.BOOL
        self.api.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];self.api.AssignProcessToJobObject.restype=w.BOOL
        self.api.CloseHandle.argtypes=[w.HANDLE];self.api.CloseHandle.restype=w.BOOL
        self.handle=self.api.CreateJobObjectW(None,None)
        if not self.handle:raise c.WinError(c.get_last_error())
        limits=Extended();limits.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle,9,c.byref(limits),c.sizeof(limits)):
            error=c.WinError(c.get_last_error());self.close();raise error

    def assign(self,process):
        import ctypes as c
        if not self.api.AssignProcessToJobObject(self.handle,int(process._handle)):
            raise c.WinError(c.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle);self.handle=None


#: W1 (2026-10-23 검수): the CLI process group a run started, kept in its workspace until the group is killed.
GROUP_FILE='.cli-process-group.json'


def _start_mark(pid):
    """Something that tells this process apart from a later one with the same pid: /proc start time on Linux, `ps` start
    time elsewhere (macOS). None when neither is available (then nothing is recorded and nothing is reaped)."""
    try:
        stat=Path(f'/proc/{pid}/stat').read_text()
        return 'proc:'+stat.rsplit(')',1)[1].split()[19]
    except (OSError,IndexError):
        pass
    try:
        out=subprocess.run(['ps','-o','lstart=','-p',str(pid)],capture_output=True,text=True,timeout=5).stdout.strip()
    except (OSError,subprocess.SubprocessError):
        return None
    return 'ps:'+out if out else None


def _remember_group(path,pid):
    mark=_start_mark(pid)
    if path is None or mark is None:return
    try:Path(path).write_text(json.dumps({'pgid':pid,'start':mark}),encoding='utf-8')
    except OSError as e:logging.getLogger('worker.process').warning('process group file not written (%s): %s',path,e)


def _forget_group(path):
    if path is not None:
        try:Path(path).unlink(missing_ok=True)
        except OSError:pass


def reap_stale_group(workdir):
    """Kill the CLI process group an earlier worker process left running in `workdir` (it died without unwinding).
    Returns the killed group id, or None. A recorded leader that is still alive but started at another time is a reused
    pid, not ours — it is left alone. Windows needs none of this: the job object dies with the worker."""
    if os.name=='nt':return None
    from . import managed_isolation
    path=managed_isolation.group_file(workdir) if managed_isolation.enabled() else Path(workdir)/GROUP_FILE
    try:
        record=json.loads(path.read_text(encoding='utf-8'))
        pgid=int(record['pgid']);start=record['start']
    except FileNotFoundError:
        return None
    except (OSError,ValueError,KeyError,TypeError):
        _forget_group(path);return None
    if pgid<=1 or pgid==os.getpgid(0):
        _forget_group(path);return None
    mark=_start_mark(pgid)
    if mark is not None and mark!=start:      # the pid now belongs to another process
        _forget_group(path);return None
    try:
        os.killpg(pgid,signal.SIGKILL)
        killed=pgid
    except (ProcessLookupError,PermissionError):
        killed=None
    _forget_group(path)
    return killed


class _ProcessTree:
    def __init__(self,group_file=None):
        self.process=None;self.job=None;self.closed=False;self.lock=threading.Lock();self.group_file=group_file

    def spawn(self,*args,**kwargs):
        with self.lock:
            if self.closed:raise RuntimeError('execution stopped before process creation')
            if os.name=='nt':
                self.job=_WindowsJob()
                kwargs['creationflags']=kwargs.get('creationflags',0)|subprocess.CREATE_NO_WINDOW
            else:
                kwargs['start_new_session']=True
            from . import managed_isolation
            if managed_isolation.enabled():
                argv,kwargs=managed_isolation.prepare(args[0],kwargs)
                args=(argv,*args[1:])
            try:
                self.process=subprocess.Popen(*args,**kwargs)
                if self.job:self.job.assign(self.process)
                else:_remember_group(self.group_file,self.process.pid)
                return self.process
            except BaseException:
                if self.process is not None:
                    self.process.kill();self.process.wait()
                    for pipe in (self.process.stdout,self.process.stderr):
                        if pipe:pipe.close()
                if self.job:self.job.close()
                raise

    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True
            if self.job:
                self.job.close()
            elif self.process is not None:
                try:os.killpg(self.process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                _forget_group(self.group_file)


def controlled_stream(stream,provider,request,env,check_stop,failed):
    """Pump stdout while checking cancellation even if the child never emits a line.

    `failed` creates the host's exception type. Thread-local CLI exit information
    must be read in the pump, not in the polling caller.
    """
    messages=queue.Queue(maxsize=128)
    workdir=getattr(request,'workdir',None)
    from . import managed_isolation
    record=(managed_isolation.group_file(workdir) if managed_isolation.enabled() else Path(workdir)/GROUP_FILE) if workdir and Path(workdir).is_dir() else None
    stop=threading.Event();tree=_ProcessTree(record)
    done=object();failure=[]
    def send(item):
        while not stop.is_set():
            try:messages.put(item,timeout=.05);return
            except queue.Full:pass
    def remember(process):
        # on_start is the upstream lifecycle contract; spawn also retains it so
        # cancellation between creation and this callback still owns the child.
        tree.process=process
    def pump():
        from cliagents.execution import _LAST_RUN
        gen=stream(provider,request,env=env,popen=tree.spawn,on_start=remember)
        try:
            for event in gen:
                if stop.is_set():break
                send(event)
            if not stop.is_set() and _LAST_RUN.returncode != 0:
                raise failed(excerpt(f'CLI exit {_LAST_RUN.returncode}: {_LAST_RUN.stderr}', 2000))
            if not stop.is_set() and (_LAST_RUN.stderr or '').strip():
                # A096 (cliagents keeps stderr only in its result slot): a run that exits 0 may still have warned
                # (deprecated flag, MCP server start-up noise); keep the tail in the worker log instead of dropping it.
                logging.getLogger('worker.process').warning('CLI exit 0 with stderr: %s', excerpt(_LAST_RUN.stderr.strip(), 1000))
        except BaseException as error:
            failure.append(error)
        finally:
            try:gen.close()
            finally:send(done)
    worker=threading.Thread(target=pump,name='hyd-cli-output',daemon=True);worker.start()
    try:
        while True:
            check_stop()
            try:item=messages.get(timeout=.025)
            except queue.Empty:continue
            if item is done:
                if failure:raise failure[0]
                break
            yield item
    finally:
        stop.set();tree.close()
        worker.join(timeout=10)
        if worker.is_alive():
            raise failed('CLI output pump did not stop after terminating its process tree')
