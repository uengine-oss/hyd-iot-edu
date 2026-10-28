"""A saved replay must not try to discover live classroom MCP tools."""
from test_instance_mode import world  # noqa: F401
from test_b5_ask import _people, _ask, _cli, ANSWER
from test_worker import _settings
from worker import managed_model, question_tools
from worker.runner import Runner


def test_saved_question_replay_does_not_attach_live_question_proxy(world, tmp_path, monkeypatch):
    runtime=world['rt'];_people(runtime);_ask(runtime)
    monkeypatch.delenv('HYD_MANAGED_MODEL_URL',raising=False)
    monkeypatch.setattr(managed_model,'attach',lambda *args:None)
    def forbidden(*args,**kwargs):
        raise AssertionError('replay attempted live MCP discovery')
    monkeypatch.setattr(question_tools,'attach',forbidden)
    requests=[]
    runner=Runner(_settings(tmp_path),runtime.repo,exec_fn=_cli(ANSWER,requests=requests),
                  schema_prompt='# schema',resolve_provider=lambda _:object(),ai_mode='replay',course_access=lambda *args:None)
    assert runner.poll_once()==1 and len(requests)==1
