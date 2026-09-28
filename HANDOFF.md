# HANDOFF — ScoreMateServer 지금 상태

_Last updated: 2026-09-29 · 운영 **0.11.0** · 백엔드 테스트 485 통과_

다음 작업을 이어받을 사람(사람 · 에이전트)이 가장 먼저 읽을 문서. 자세한 설계는 `ARCHITECTURE.md`, 배포는 `deploy/README.md`,
릴리스별 변화는 `DEPLOY.md`, 과정은 `devlog/`.

## 한 줄
악보 PDF 를 올리면 웹에서 쪽마다 보고 들어볼 수 있고, 연결한 TV · 태블릿(MrgqPdfViewer)이 고른 세트리스트의 곡을
PDF + MusicXML(악보 인식) + 보표 · 마디 분석 파일과 함께 받아 간다.

## 운영 (dolfinid, `/srv/scoremate`)
| 무엇 | 어디 |
|---|---|
| 사이트 | https://scoremate.noematica.kr — 컨테이너 하나(Gunicorn), `127.0.0.1:8016` 뒤 nginx(TLS · X-Accel) |
| 데이터 | `db/db.sqlite3` · `files/`(PDF · 표지 · 쪽 이미지 · MusicXML · layout JSON) |
| 배포 | 빌드 호스트 m710q: `./deploy/build.sh X.Y.Z && ./deploy/remote-prod.sh X.Y.Z` |
| 호스트 cron | 매시 `scripts/backup_db.py` · 10분 `scripts/omr_lane.sh`(악보 인식) · 5분 `scripts/layout_lane.sh`(보표 · 마디 분석) · 10분 `scripts/model_layout_lane.sh`(모델 위치) |
| 로그 | `omr/lane.log` · `omr/work/v<판 id>/run.log` · `omr/layout.log` · `omr/model_layout.log` · `backup/backup.log` · `docker compose logs api` |
| 백업 | pre-deploy · hourly(DB) · **daily 오프사이트(m710q 05:25, DB + `files/` 전체 + NAS)** |
| manage.py | 컨테이너 안에서 DB 소유 uid 로: `docker compose exec -u "$(stat -c %u db)" api python manage.py …` |

⚠️ 악보 인식은 **호스트 사용자의 ChatGPT 로그인(Codex CLI)** 을 쓴다. 토큰이 만료되면 `lane.log` 에
"codex 로그인 필요"가 찍히고 악보는 기다린다(실패로 기록하지 않는다) → `codex logout && codex login --device-auth`.

## 데이터 (2026-09-28)
사용자 1 · 악보 4 · 연결 기기 1(`Z18TV_Test`, 앱 0.3.3, 세트리스트 "2027 연주회").

| 악보 | 쪽 | 파트 | 인식 마디 | PDF 분석 마디 |
|---|---|---|---|---|
| Piano Concerto No 23 (K 488) | 6 | 하진 · 예완 | 99 | 99 |
| Clair de Lune | 4 | Guitar 1 · Guitar 2 | 72 | 72 |
| Die Moldau (Vltava) | 42 | 진호 · 예진 · 하진 · 예완 · 은석 | 268 | 268 |
| Sonate für Pianoforte und Arpeggione | 28 | **Staff 1 · 2 · 3 — 이름을 붙여야 한다**(기타 세 대) | 278 | 278 |

## 오늘(2026-09-28) 들어온 것 — 0.8.0 → 0.10.2
- **악보 인식 레인**(devlog 064 · 069): 1쪽씩, 짧은 텍스트 형식(`scripts/omr_compact.py`) → MusicXML
  - 검산: 박 길이 · 파트 구성 · 조표 교차 확인 · 보표 분석의 보표 수
  - 결과: 분석 `astra-musicxml` + `files/…/omr/v{N}.musicxml`
- **보표 · 마디 분석 파일**(devlog 068): TV 앱 Kotlin `score/` 를 그대로 옮김(`scores/score_layout.py`, 앱 골든 + 단위 테스트 64개)
  - `analyzer_version = SERVER_REVISION + app.<커밋>`(지금 `2+app.9557497`)
- 기기 동기화에 `musicxml` · `layout` · `arranger`(TV 앱 v0.3.2 · v0.3.3 이 받아 쓴다)
- 웹
  - 쪽 보기(너비/높이 맞춤 · 1/2쪽) · 들어보기(쪽 보기 창, 마디 따라 쪽 넘김)
  - 악보 인식 결과 칸(마디 · 쪽 · 파트 · 보표, 파트 이름 고치기)
  - 곡 정보(편곡 · PDF 제목 · 제안) · 목록 카드 쪽수 · 올리기 드롭존
  - "연결 기기"(기기마다 세트리스트만)

## 2026-09-29
- 줄 · 쪽 바뀜을 MusicXML 에(0.10.3) — PDF 분석과 마디 수가 같으면 그 값으로. 네 곡에 채움
- 모델 위치 정확도 실험(devlog 070): 벡터 8쪽 개수 모두 일치 · 평균 0.1~0.4pt
- **모델 위치 레인**(0.11.0, devlog 071): 모든 악보. 벡터는 검산, 스캔은 기기 layout(`source: model`)

## 규칙 (꼭 지킬 것)
- 악보 조회는 늘 `Score.objects.readable_by(user)` / `writable_by(user)`. 규칙은 `scores/services.py` · `ensembles/services.py` 한 곳
- 파일은 Django 를 지나가지 않는다(서명 URL · X-Accel)
- 마이그레이션 파일은 ASCII 만(테스트가 막는다). SQLite 에서 도는 코드만
- `scores/score_layout.py` 는 앱 Kotlin 과 **같은 결과**여야 한다. 고치면 `scores/layouts.py` 의 `SERVER_REVISION` 을 올린다
- 악보 인식 모델은 컨테이너에 넣지 않는다(호스트 레인 · 결과 파일만 돌아온다)
- 릴리스마다 `DEPLOY.md` 에 운영 델타, 작업마다 `devlog/` 문서

## TV 앱(MrgqPdfViewer)과의 약속
- 서버 → 앱 알림은 앱 저장소 `devlog/20260927_P06_scoremate_server_requests.md`(§9~§12)
- 동기화 응답 필드(`musicxml`, `layout`, `arranger` …)는 추가만 한다. 바꾸거나 뺄 때는 P06 에 먼저 적는다(`sync_mode` 는 앱이 쓰지 않음을 확인하고 뺐다)

## 다음 할 만한 것
1. Arpeggione 파트 이름 붙이기(웹 상세 → 악보 인식 → 파트 이름 저장)
2. 새 판을 인식할 때 앞 판에서 고친 파트 이름 이어 받기
3. 음높이 검수를 돕는 화면(들어보기 + 쪽 이미지를 마디 단위로, 틀린 쪽만 다시 인식)
4. 곡(Work) 단위 합주 · 파트보 — `devlog/20260928_P01_…` §3. 마디 지도 두 벌(인식 · PDF 분석)이 판본 검사에 쓰인다
5. 스캔 악보로 인식 · 모델 위치 시험(지금까지는 모두 벡터 PDF) — 스캔본에서는 모델 위치가 유일한 위치 정보다
6. 앙상블 웹 메뉴 다시 켜기(`WEB_ENSEMBLES`) · Google 로그인 설정(클라이언트 ID)
