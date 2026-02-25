# Learning Tracker Agent

최신 기술 트렌드에 대한 소스(url/텍스트/PDF)를 수집·요약해서 Notion DB에 업로드하는 자동화 프로젝트

## 개요

* 입력: Telegram(모바일 공유)
* 처리:

  * URL: `trafilatura`로 본문 추출
  * PDF: `pypdf`로 텍스트 추출
  * TEXT: 원문 사용
* 요약: Gemini, JSON 스키마 기반 구조화 출력
* 저장: Notion DB에 `title / summary / key_insights / tags / source` 형태로 저장, 링크 반환
* 중복 방지: URL 기준 중복 저장(`url_exists`)

## 구조

```text
Telegram Bot → Input Router(url/text/pdf)
→ (trafilatura / pypdf / raw text)
→ Gemini Summarizer(JSON)
→ NotionDB.add_article()
→ Notion Learning Database
```

## 구성 파일

* `telegram_bot.py`: `/start`, URL/텍스트/PDF 처리, 실패 안내, Notion 저장
* `notion_db.py`: Notion CRUD, 아티클/이슈 저장, URL 중복 검사
* `agent.py`: CLI 기반 워크플로우
* `newsletter.py`: RSS/이메일 기반 자동 수집 파이프라인
* `TELEGRAM_BOT.md`, `.env.example`, `requirements.txt`

## 실행

```bash
pip install -r requirements.txt
```

`.env`

```env
GEMINI_API_KEY=...
NOTION_TOKEN=...
NOTION_DATABASE_ID=...
TELEGRAM_BOT_TOKEN=...
```

```bash
python telegram_bot.py
```

## 배포(Railway)

Telegram 봇만 운영 시 변수 4개:
`GEMINI_API_KEY`, `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `TELEGRAM_BOT_TOKEN`
Start Command: `python telegram_bot.py`

## 한계

* 스캔 PDF는 텍스트 추출 실패 가능
* 로그인/권한 필요한 페이지는 본문 추출 실패 가능
* polling 방식이라 상시 프로세스 운영 필요
* API quota 소진 시 요약 지연/실패 가능

## 로드맵

* OCR fallback
* 입력 실패 재시도/대체 경로 안내 강화
* 태그 정규화 + 유사 문서 클러스터링
* 주간 학습 리포트 자동 생성
* 학습량/주제/완료율 대시보드

## Codex/Claude Code 연동 아이디어

Gemini API 대신, 현재 작업 중인 리포지토리에서 URL/PDF를 바로 처리하고 결과를 Notion DB로 적재하는 방식도 가능합니다.

### 추천 아키텍처

1. **입력 수집(리포 기반)**
   * `inputs/` 폴더에 URL 목록(`.md`/`.txt`) 또는 PDF 파일을 추가
   * 또는 GitHub Issue/PR 코멘트로 URL/PDF 경로를 전달

2. **실행 트리거**
   * Codex/Claude Code를 로컬에서 실행하거나 CI(GitHub Actions)에서 실행
   * 예: `python agent.py --source inputs/ --llm_provider anthropic`

3. **요약 생성(LLM Provider 교체)**
   * 기존 `summarize_with_gemini()`를 provider 인터페이스로 분리
   * `GeminiProvider`, `OpenAIProvider(Codex)`, `AnthropicProvider(Claude)` 구현
   * 동일 JSON 스키마를 강제해 Notion 스키마와 호환 유지

4. **Notion 적재**
   * 현재 `notion_db.py`의 `add_article()`를 재사용
   * URL 중복 검사(`url_exists`)는 그대로 유지

### 장점

* 리포지토리 중심 워크플로우(문서 버전관리 + 자동화) 가능
* 특정 모델에 락인되지 않고 공급자 교체 가능
* CI에서 정기 실행 시 주간/일간 배치 처리에 유리

### 구현 시 체크포인트

* PDF는 스캔본 대비 OCR fallback 필요
* LLM별 응답 포맷 차이를 provider 레이어에서 흡수
* Notion API rate limit 대비 재시도(backoff) 적용 권장


## 리포지토리 입력 기반 실행 (Codex/Claude Code)

`repo_ingest.py`를 사용하면, 리포지토리에 URL/PDF를 추가한 뒤 한 번에 요약해서 Notion DB로 저장할 수 있습니다.

### 1) 입력 준비

- `inputs/*.md`, `inputs/*.txt`: URL 또는 원문 텍스트
- `inputs/*.pdf`: PDF 원문

`.md/.txt` 파일에 URL이 여러 개 있으면 모두 처리합니다.

### 2) 환경 변수

공통:
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`

Provider별:
- Gemini: `GEMINI_API_KEY`
- Codex(OpenAI): `OPENAI_API_KEY`
- Claude(Anthropic): `ANTHROPIC_API_KEY`

(선택) 모델 지정:
- `GEMINI_MODEL`
- `OPENAI_MODEL`
- `ANTHROPIC_MODEL`

### 3) 실행

```bash
python repo_ingest.py --source inputs --provider gemini
python repo_ingest.py --source inputs --provider openai
python repo_ingest.py --source inputs --provider anthropic
```



### 동작 요약

1. 입력 폴더 스캔(`.txt/.md/.pdf`)
2. URL 본문 추출(`trafilatura`) / PDF 텍스트 추출(`pypdf`)
3. Provider별 구조화 요약(JSON)
4. Notion DB 저장(`notion_db.py`의 `add_article()` 사용)
5. URL 중복 시 자동 skip(`url_exists`)
