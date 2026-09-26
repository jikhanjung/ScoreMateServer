# ScoreMate Server 모노레포

ScoreMate Server는 Django REST API와 Next.js 웹 클라이언트를 포함한 모노레포입니다. PDF 업로드(S3/MinIO), 악보 메타데이터/세트리스트 관리, 페이지 수/썸네일 생성을 제공합니다.

2026-09부터 목적은 **앙상블 안에서 악보 공유**입니다 — 리더가 올린 곡·파트보가 멤버의 Google TV(MrgqPdfViewer)로 배포됩니다. 개인 악보는 비공개, 앙상블 악보는 그 멤버에게만 보이며 공개 공유는 하지 않습니다. 계획: `devlog/20260926_054_악보공유_및_TV클라이언트_계획.md`, 개요: `ARCHITECTURE.md`.

## 스택
- 백엔드: Django 5, DRF, SQLite(기본; `DATABASE_URL`로 PostgreSQL 가능), boto3, Celery(선택 — `REDIS_URL`이 없으면 작업을 요청 안에서 바로 실행)
- 프런트엔드: Next.js(TypeScript), Playwright E2E
- 인프라: Docker Compose(개발용 전체 스택), MinIO(dev S3). 운영은 dolfinid VM에 컨테이너 하나로 배포 예정(S5)

## 저장소 구조
```
backend/    # Django 앱: scores, setlists, tasks, 프로젝트 설정 scoremateserver/
frontend/   # Next.js 앱(App Router), E2E 테스트 tests/e2e/
nginx/      # 리버스 프록시 설정(선택)
docker-compose.yml
AGENTS.md          # 레포지토리 가이드(코딩/테스트/명령어)
ARCHITECTURE.md    # 상세 아키텍처 설명
CONTRIBUTING.md    # 기여 방법
```

## 빠른 시작 (백엔드만, Docker 없이)
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate      # backend/data/db.sqlite3
python manage.py runserver
python -m pytest tests/
```

## 빠른 시작 (Docker Compose 전체 스택)
1) 요구사항: Docker, Docker Compose, Node 18+, npm
2) 환경변수: `.env.example`를 `.env`로 복사 후 값 설정(DB/Redis/MinIO/JWT). 비밀정보는 커밋 금지.
   - `scores` 0001 마이그레이션이 SQLite 전환 때 바뀌었으므로 예전 로컬 Postgres DB는 다시 만들어야 합니다.
3) 실행: `npm run dev` (백그라운드 실행: `npm run dev:detached`)
4) 초기화:
   - 마이그레이션: `docker-compose exec web python manage.py migrate`
   - 슈퍼유저: `docker-compose exec web python manage.py createsuperuser`
5) 접속: API `http://localhost:8000`, Frontend `http://localhost:3000`, MinIO 콘솔 `http://localhost:9001`

## 주요 스크립트
- 개발: `npm run dev`, `npm run dev:backend`, `npm run dev:frontend`
- 빌드: `npm run build:frontend`, `npm run build:backend`
- 테스트: `npm test`, `npm run test:backend`, `npm run test:backend:coverage`, `npm run test:frontend`
- 린트: `npm run lint:backend`(ruff), `npm run lint:frontend`(next lint)
- 운영: `npm run logs`, `npm run stop`, `npm run clean`

## 테스트
- 백엔드: pytest(`backend/pytest.ini`). `npm run test:backend` 실행, 커버리지는 `npm run test:backend:coverage`.
- 프런트엔드: Playwright E2E `frontend/tests/e2e/`. `npm run test:frontend` 또는 `npm --workspace frontend run test:headed`.

## 환경설정
- `.env.example`를 참고하세요. 주요 변수: `DATA_DIR`(SQLite 위치), `DATABASE_URL`(선택), `REDIS_URL`(선택), `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `JWT_SIGNING_KEY`, `NEXT_PUBLIC_API_URL`.

## 기여 & 문서
- 가이드라인: `AGENTS.md`
- 기여 방법: `CONTRIBUTING.md`
- 아키텍처: `ARCHITECTURE.md`
