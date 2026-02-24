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
