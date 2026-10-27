"""The worker verifies the offline proof itself; a status boolean is not authority."""
import httpx
from hydcommon import course_access as rules


class CourseAccess:
    def __init__(self, *, transport=None):
        self.transport = transport

    def __call__(self, definition, activity_id, inputs):
        try:
            with httpx.Client(transport=self.transport, trust_env=False, timeout=5) as client:
                response = client.get('http://process:8080/internal/course-access')
                response.raise_for_status()
                if len(response.content)>2048:raise ValueError()
                proof = response.json()
                if not isinstance(proof,dict) or set(proof)!={'grant'}:raise ValueError()
            rules.authorize_task(proof['grant'], definition, activity_id, inputs)
        except rules.AccessDenied:raise
        except Exception:
            raise rules.AccessDenied('수업 권한을 확인하지 못했습니다. 프로세스 서비스 연결을 확인하세요.') from None
