"""Small compatibility adapter for cliagents with Codex CLI 0.151.

The upstream parser/stream/process teardown are retained. Resume accepts fewer
flags than exec, so exec-only flags must precede its resume subcommand.
"""
from dataclasses import replace
import sys
import tempfile

from cliagents import Permission
from cliagents.providers.codex import CodexProvider


class WorkerCodexProvider(CodexProvider):
    def exec_argv(self, request):
        extra_args = list(request.extra_args)
        if sys.platform == 'win32' and request.permission is Permission.WORKSPACE_WRITE:
            # --ignore-user-config also removes the Windows sandbox backend
            # selection. Select the installed bounded backend for this run;
            # --sandbox stays workspace-write, with no approval/config bypass.
            extra_args += ['-c', 'windows.sandbox="elevated"']
        argv = super().exec_argv(replace(request, resume_session=None, extra_args=extra_args))
        if request.resume_session:
            argv[-1:-1] = ["resume", request.resume_session]
        return argv


def stream_with_prompt_stdin(stream, provider, request, **kwargs):
    """Retain cliagents' parser/lifecycle, delivering the entire prompt via stdin.

    A seekable temporary input avoids both Windows argv limits and pipe writes
    blocking before the cancellable output pump starts. No model file-read tool
    is needed. The file closes on exhaustion, launch failure, or cancellation.
    """
    spawn = kwargs.pop("popen")
    with tempfile.TemporaryFile(mode="w+b") as source:
        source.write(request.prompt.encode("utf-8"))
        source.seek(0)

        def with_stdin(*args, **options):
            options["stdin"] = source
            return spawn(*args, **options)

        yield from stream(provider, replace(request, prompt="-"), popen=with_stdin, **kwargs)
