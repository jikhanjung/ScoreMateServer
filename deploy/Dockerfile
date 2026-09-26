# ScoreMateServer — Django API 이미지 (dolfinid 운영)
# 빌드는 저장소 루트를 컨텍스트로:  docker build -f deploy/Dockerfile -t honestjung/scoremateserver:X.Y.Z .
# 이미지 안에 운영 호스트 파일(deploy/host/*)과 backup_db.py 를 싣는다 — 운영 서버는 git-free, 배포 때 이미지에서 꺼낸다.
FROM python:3.12-slim

# 릴리스 버전 단일 소스는 backend/scoremateserver/version.py. build.sh 가 그 값을 넘긴다.
ARG APP_VERSION=
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="ScoreMateServer" \
      org.opencontainers.image.description="ScoreMate — 앙상블 악보 공유 API (Django)" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/jikhanjung/ScoreMateServer"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_DEBUG=false \
    STATIC_ROOT=/app/staticfiles \
    DATA_DIR=/app/hostdb \
    FILES_ROOT=/app/hostfiles

WORKDIR /app

# gosu: entrypoint 가 root 로 시작해 마운트(/app/hostdb) 소유 uid 로 권한을 드롭한다 (fcmanager · cdGTS 동형).
RUN apt-get update && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* && gosu nobody true

COPY backend/requirements-prod.txt ./
RUN pip install -r requirements-prod.txt

COPY deploy/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

COPY backend/ /app/
# 운영 호스트 파일 — _extract_and_deploy.sh 가 /app/deploy/host/* 를 /srv/scoremate 로 꺼낸다
COPY deploy/host/ /app/deploy/host/

# 정적 파일은 빌드 때 모은다 — 실행 컨테이너는 루트가 읽기 전용이다
RUN DJANGO_SECRET_KEY=build-only-not-a-runtime-secret python manage.py collectstatic --noinput \
    && mkdir -p /app/hostdb /app/hostfiles

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "scoremateserver.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "2", "--worker-class", "gthread", "--threads", "4", "--timeout", "120", \
     "--max-requests", "1000", "--max-requests-jitter", "100", \
     "--worker-tmp-dir", "/tmp", "--access-logfile", "-", "--error-logfile", "-"]
