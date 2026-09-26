#!/bin/sh
# 컨테이너 시작: (root) 마운트 소유 uid 감지 → gosu 권한 드롭 → migrate(+선택적 관리자 생성) → 본 명령.
# fcmanager docker-entrypoint.sh 동형 (devdocs guides/web/deployment.md §7 — migrate 는 컨테이너가 유일한 writer 일 때).
set -e
umask 002

HOSTDB=/app/hostdb
FILES=/app/hostfiles

# --- 비-root 실행(권한 드롭) ---
# DB 는 $HOSTDB 디렉터리 바인드(-wal/-shm 형제 파일을 호스트와 공유). 서비스 프로세스는 그 디렉터리 소유 uid 로
# 돌아야 저널을 만들 수 있다. 호스트마다 uid 가 달라 Dockerfile USER 고정 대신 런타임 감지 + gosu 드롭.
if [ "$(id -u)" = "0" ] && [ -d "$HOSTDB" ]; then
  UID_T=$(stat -c %u "$HOSTDB"); GID_T=$(stat -c %g "$HOSTDB")
  if [ "$UID_T" != "0" ]; then
    chown "${UID_T}:${GID_T}" "$HOSTDB"/db.sqlite3* 2>/dev/null || true
    echo "[entrypoint] drop -> uid ${UID_T}:${GID_T} (owner of ${HOSTDB})"
    exec gosu "${UID_T}:${GID_T}" env HOME=/tmp "$0" "$@"
  fi
  echo "[entrypoint] ${HOSTDB} is root-owned -> staying root"
fi

# 파일 저장소는 DB 와 같은 uid 가 써야 한다 (올리기 · 썸네일)
if [ -d "$FILES" ] && [ ! -w "$FILES" ]; then
  echo "[entrypoint] FATAL: ${FILES} is not writable by uid $(id -u) — chown the host files/ to the owner of db/" >&2
  exit 1
fi

echo "[entrypoint] migrate..."
python manage.py migrate --noinput

# DJANGO_SUPERUSER_{EMAIL,USERNAME,PASSWORD} 가 있으면 관리자 계정을 만든다 — **없을 때만**. 기존 비밀번호를 바꾸지 않는다.
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "[entrypoint] ensure superuser '$DJANGO_SUPERUSER_EMAIL'..."
  python manage.py createsuperuser --noinput \
    --email "$DJANGO_SUPERUSER_EMAIL" \
    --username "${DJANGO_SUPERUSER_USERNAME:-admin}" 2>/dev/null \
    || echo "[entrypoint] superuser already exists, skip."
fi

exec "$@"
