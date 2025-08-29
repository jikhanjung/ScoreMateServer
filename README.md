# ScoreMate Server 모노레포

ScoreMate Server는 Django REST API와 Celery 워커, Next.js 웹 클라이언트를 포함한 모노레포입니다. PDF 업로드(S3/MinIO), 악보 메타데이터/세트리스트 관리, 페이지/썸네일 생성 등 비동기 작업을 제공합니다.

## 스택
- 백엔드: Django 5, DRF, Celery, PostgreSQL, Redis, boto3
- 프런트엔드: Next.js(TypeScript), Playwright E2E
- 인프라: Docker Compose, MinIO(dev S3), Nginx(선택)

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

## 빠른 시작
1) 요구사항: Docker, Docker Compose, Node 18+, npm
2) 환경변수: `.env.example`를 `.env`로 복사 후 값 설정(DB/Redis/MinIO/JWT). 비밀정보는 커밋 금지.
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
- `.env.example`를 참고하세요. 주요 변수: `DATABASE_URL`, `REDIS_URL`, `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `JWT_SIGNING_KEY`, `NEXT_PUBLIC_API_URL`.

## 기여 & 문서
- 가이드라인: `AGENTS.md`
- 기여 방법: `CONTRIBUTING.md`
- 아키텍처: `ARCHITECTURE.md`
