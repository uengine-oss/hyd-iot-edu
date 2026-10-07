FROM python:3.12-slim
WORKDIR /srv
COPY it/process/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common/hydcommon /srv/hydcommon
COPY it/process/procsvc /srv/procsvc
COPY it/process/definitions /srv/definitions
ENV PYTHONUNBUFFERED=1 PROCESS_DEFINITIONS=/srv/definitions
# A131 (OOM 2026-10-07, .evidence/a131): the Python heap stays flat (~76 MB traced) while RSS climbs 420→675 MB under the
# portal/worker read pattern; mallinfo2 showed 343 MB *free* inside glibc arenas against 131 MB in use. Every request thread
# gets its own arena (default 8×cores) and freed request garbage (700 KB instance views, 14 MB snapshot strings) stays there.
# Two arenas, a fixed mmap threshold (large buffers go back to the kernel on free instead of raising the threshold to 14 MB
# and then living in the heap) and a fixed trim threshold bound the retention to the live set. Allocator semantics, not a limit.
ENV MALLOC_ARENA_MAX=2 MALLOC_MMAP_THRESHOLD_=262144 MALLOC_TRIM_THRESHOLD_=1048576 MALLOC_TOP_PAD_=1048576
EXPOSE 8080
CMD ["uvicorn", "procsvc.main:app", "--host", "0.0.0.0", "--port", "8080"]
