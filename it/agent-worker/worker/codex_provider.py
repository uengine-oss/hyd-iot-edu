"""Small compatibility adapter for cliagents with Codex CLI 0.151.

The upstream parser/stream/process teardown are retained. Resume accepts fewer
flags than exec, so exec-only flags must precede its resume subcommand.
"""
from dataclasses import replace

from cliagents.providers.codex import CodexProvider


class WorkerCodexProvider(CodexProvider):
    def exec_argv(self, request):
        argv = super().exec_argv(replace(request, resume_session=None))
        if request.resume_session:
            argv[-1:-1] = ["resume", request.resume_session]
        return argv
