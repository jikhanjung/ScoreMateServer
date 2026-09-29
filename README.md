# ScoreMate Server 모노레포

ScoreMate Server 는 악보 PDF 를 올리고 관리하고, 연결한 Google TV · 태블릿(MrgqPdfViewer 앱)으로 내려보내는 서버입니다.
Django 한 컨테이너가 웹(템플릿) · REST API · 기기 동기화를 맡고, 운영 호스트의 cron 이 악보 인식(PDF → MusicXML)과
보표 · 마디 분석을 채웁니다.

2026-09부터 목적은 **앙상블 안에서 악보 공유**입니다 — 리더가 올린 곡·파트보가 멤버의 Google TV(MrgqPdfViewer)로 배포됩니다. 개인 악보는 비공개, 앙상블 악보는 그 멤버에게만 보이며 공개 공유는 하지 않습니다. 계획: `devlog/20260926_054_악보공유_및_TV클라이언트_계획.md`, 개요: `ARCHITECTURE.md`.

운영: https://scoremate.noematica.kr (웹 + API, dolfinid) — 배포 절차 `deploy/README.md`, 릴리스 기록 `DEPLOY.md`, 지금 상태 `HANDOFF.md`.
웹은 Django 템플릿(`backend/web/`)입니다. `frontend/`(Next.js)는 예전 것으로 배포하지 않습니다.

## 할 수 있는 것
- 악보 올리기(끌어다 놓기, 여러 파일) · 판(수정판) · 곡 정보(작곡 · 편곡 — PDF 문서 제목과 인식 결과에서 제안)
- 쪽 보기(너비/높이 맞춤, 1쪽/2쪽) · MusicXML 로 **들어보기**(마디를 따라 쪽 넘기기)
- 세트리스트 · 앙상블(초대 전용 가입, 웹 메뉴는 지금 숨김) · Google 로그인(설정 시)
- 연결 기기(TV · 태블릿, 코드 + QR) — 기기마다 고른 세트리스트의 곡만 받는다
- 기기 동기화: PDF + **MusicXML**(악보 인식) + **보표 · 마디 분석 파일**(앱 분석과 같은 결과) + 곡 정보
- 악보 인식(OMR): 운영 호스트 cron 이 Codex CLI(`gpt-6-astra`)로 한 쪽씩 옮긴다 — devlog 064 · 069
- 사용자 관리(관리자만, 웹 "사용자 관리"): 사용자 추가 · 등급(기본 200 · 프로 1000 · 단체 5000MB) · 저장 공간 한도 · 관리자 권한 · 비밀번호 다시 정하기 · 사용 중지 — devlog 075

## 스택
- 백엔드: Django 5.2, DRF, SQLite(기본; `DATABASE_URL`로 PostgreSQL 가능), PyMuPDF, Celery(선택 — `REDIS_URL`이 없으면 요청 안에서 바로 실행)
- 웹: Django 템플릿 + 작은 JS(쪽 보기 · 들어보기는 Web Audio, 외부 라이브러리 없음)
- 운영: dolfinid VM 에 컨테이너 하나(Gunicorn) · 로컬 디스크 파일 · nginx X-Accel · 호스트 cron(백업 · 악보 인식 · 보표 분석)
- 예전 것: Next.js 프런트엔드 · Docker Compose 전체 스택(Postgres · Redis · MinIO) — 개발용으로만 남아 있다

## 저장소 구조
```
backend/    # Django: core · ensembles · devices · scores · setlists · files · tasks · web, 설정 scoremateserver/, 호스트 스크립트 scripts/
deploy/     # 이미지 빌드 · 운영 호스트 스크립트(배포 · 되돌리기 · 인식/분석 레인)
devlog/     # 계획 · 진행 기록(YYYYMMDD_###_제목.md, 계획은 P##)
frontend/   # Next.js — 예전 것, 배포하지 않음
nginx/      # 리버스 프록시 설정(선택)
docker-compose.yml
AGENTS.md          # 레포지토리 가이드(코딩/테스트/명령어)
ARCHITECTURE.md    # 상세 아키텍처 설명
HANDOFF.md         # 지금 상태 · 운영 · 다음 할 일
CONTRIBUTING.md    # 기여 방법
```

## 빠른 시작 (백엔드만, Docker 없이)
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate      # backend/data/db.sqlite3
python manage.py createsuperuser   # 첫 관리자 — 그다음 사용자는 웹 "사용자 관리"에서 추가
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
- 백엔드: pytest(`backend/pytest.ini`), 476개 — `cd backend && python -m pytest tests/`.
  보표 · 마디 분석은 TV 앱의 골든 테스트 · 단위 테스트를 옮겨 온 것(`tests/test_score_layout*.py`, 픽스처 `tests/fixtures/score/`).
- 프런트엔드: Playwright E2E `frontend/tests/e2e/`. `npm run test:frontend` 또는 `npm --workspace frontend run test:headed`.

## 환경설정
- `.env.example`를 참고하세요. 주요 변수: `DATA_DIR`(SQLite 위치), `DATABASE_URL`(선택), `REDIS_URL`(선택), `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `JWT_SIGNING_KEY`, `NEXT_PUBLIC_API_URL`.

## 기여 & 문서
- 가이드라인: `AGENTS.md`
- 기여 방법: `CONTRIBUTING.md`
- 아키텍처: `ARCHITECTURE.md` · 지금 상태: `HANDOFF.md` · 배포: `deploy/README.md` · 릴리스: `DEPLOY.md`
