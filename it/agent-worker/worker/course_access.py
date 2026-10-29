"""The worker checks the course boundary itself right before an AI run; a status flag is not authority."""
from hydcommon import course_access as rules


class CourseAccess:
    def __call__(self, definition, activity_id, inputs):
        rules.authorize_task(definition, activity_id, inputs)
