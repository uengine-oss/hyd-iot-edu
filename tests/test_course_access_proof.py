import httpx
from hydcommon import course_access as rules
from procsvc import course_access_proof
from test_course_access import instructor,setup


def test_published_api_never_returns_the_unlock_grant(tmp_path,instructor):
    _,client,store,sign,_=setup(tmp_path,instructor)
    code=sign()
    client.post('/api/course-access/unlock',json={'code':code})
    assert store.grant()==code
    for path in ('/internal/course-access','/internal/course-access?proof=1','/api/course-access'):
        response=client.get(path)
        assert code not in response.text
        if path.startswith('/internal/'):assert response.status_code==404


def test_private_listener_and_real_worker_share_the_verified_proof(tmp_path,instructor):
    from worker.course_access import CourseAccess
    _,_,store,sign,_=setup(tmp_path,instructor)
    server,thread=course_access_proof.start(store,host='127.0.0.1',port=0)
    base=f'http://127.0.0.1:{server.server_port}'
    seen=[]
    def transport(request):
        assert str(request.url)==rules.PROOF_URL
        seen.append(request.url.port)
        return httpx.get(base+rules.PROOF_PATH,trust_env=False)
    worker=CourseAccess(transport=httpx.MockTransport(transport))
    try:
        worker({'processDefinitionId':'c3_cooling'},'T_agent',{})
        store.unlock(sign())
        worker({'processDefinitionId':'ShiftHandover'},'task_draft_r2',{})
        assert seen==[rules.PROOF_PORT,rules.PROOF_PORT]
        assert httpx.get(base+'/api/course-access',trust_env=False).status_code==404
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
    assert not thread.is_alive()
