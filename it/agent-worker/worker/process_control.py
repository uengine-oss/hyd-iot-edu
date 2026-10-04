"""Cancellable synchronous adapter of process-gpt-cli-agent/core/runner.py.

The pump retains cliagents' parser and teardown. The caller checks its deadline
and database state independently of stdout. Each run owns its process tree.
Windows job lifetime: https://learn.microsoft.com/windows/win32/procthread/job-objects
"""
import os
import queue
import signal
import subprocess
import threading


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


class _ProcessTree:
    def __init__(self):
        self.process=None;self.job=None;self.closed=False;self.lock=threading.Lock()

    def spawn(self,*args,**kwargs):
        with self.lock:
            if self.closed:raise RuntimeError('execution stopped before process creation')
            if os.name=='nt':
                self.job=_WindowsJob()
                kwargs['creationflags']=kwargs.get('creationflags',0)|subprocess.CREATE_NO_WINDOW
            else:
                kwargs['start_new_session']=True
            try:
                self.process=subprocess.Popen(*args,**kwargs)
                if self.job:self.job.assign(self.process)
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


def controlled_stream(stream,provider,request,env,check_stop,failed):
    """Pump stdout while checking cancellation even if the child never emits a line.

    `failed` creates the host's exception type. Thread-local CLI exit information
    must be read in the pump, not in the polling caller.
    """
    messages=queue.Queue(maxsize=128)
    stop=threading.Event();tree=_ProcessTree();done=object();failure=[]
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
                raise failed(f'CLI exit {_LAST_RUN.returncode}: {_LAST_RUN.stderr[-2000:]}')
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
