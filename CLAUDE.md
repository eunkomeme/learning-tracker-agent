# Learning Tracker Agent — Claude 세션 컨텍스트

이 파일은 Claude Code 세션마다 자동으로 읽혀, 처음 만나는 세션에서도 컨텍스트 설명 없이 바로 작업할 수 있도록 유지합니다.

---

## 프로젝트 개요

AI/테크 아티클을 자동 수집·요약하여 Notion 데이터베이스에 저장하는 PM 개인 지식 관리 시스템.
**핵심 철학**: 인프라 비용 0, GitHub Actions 기반 자동화, Notion 네이티브.

---

## 환경 변수 설정 방식

> **중요**: `.env` 파일이 없습니다. 환경 변수는 **Claude Code 클라우드 환경 UI**에서 설정됩니다.
>
> 설정 위치: Claude Code → 새 클라우드 환경 → 환경 변수 (.env 형식 입력)

| 변수 | 용도 | 필수 여부 |
|------|------|---------|
| `NOTION_TOKEN` | Notion Integration 토큰 | 필수 |
| `NOTION_DATABASE_ID` | 32자리 hex (하이픈 없음) | 필수 |
| `GEMINI_API_KEY` | Google AI Studio (무료) | 필수 |
| `OPENAI_API_KEY` | batch_ingest.py 선택 사용 | 선택 |
| `ANTHROPIC_API_KEY` | batch_ingest.py 선택 사용 | 선택 |
| `TELEGRAM_BOT_TOKEN` | telegram_bot.py 전용 | 선택 |

**GitHub Actions 워크플로**는 별도로 Repository Secrets에 동일 변수들을 설정해야 합니다.
(Claude Code 클라우드 환경 변수는 로컬 실행에만 적용됨)

---

## 파일별 역할

| 파일 | 역할 |
|------|------|
| `notion_db.py` | Notion API CRUD 래퍼. 모든 모듈이 공유하는 데이터 레이어 |
| `mcp_server.py` | Claude Code용 MCP 서버. 채팅창에서 바로 Notion 저장 가능 |
| `repo_ingest.py` | inputs/ 폴더 → Gemini Map-Reduce → Notion. GitHub Actions 진입점 |
| `batch_ingest.py` | inputs/ 폴더 → 멀티 프로바이더(Gemini/OpenAI/Anthropic) → Notion. 로컬 수동 실행용 |
| `agent.py` | Gemini Tool Calling 기반 인터랙티브 CLI 에이전트 |
| `newsletter.py` | RSS + 이메일 뉴스레터 자동 수집·요약 |
| `scheduler.py` | newsletter.py 일별 실행 데몬 |
| `telegram_bot.py` | 텔레그램으로 URL/텍스트/PDF 실시간 저장 |
| `setup_notion.py` | 최초 1회: Notion DB 스키마 생성 및 NOTION_DATABASE_ID 발급 |
| `.mcp.json` | MCP 서버 등록 (Claude Code 자동 읽음) |

---

## 채팅창 텍스트 → Notion 저장 방법

MCP 서버(`mcp_server.py`)가 `.mcp.json`으로 Claude Code에 등록되어 있습니다.
채팅창에 아티클 본문이나 URL을 붙여넣으면 Claude가 `save_article` MCP 툴로 자동 저장합니다.

**MCP 툴 목록:**
- `fetch_article_content(url)` — URL에서 본문 추출
- `save_article(title, summary, key_insights, tags, url, source, status)` — 아티클 저장
- `save_issue(title, description, suggested_actions, tags, priority, status)` — 이슈 저장
- `search_entries(query, ...)` — 검색
- `list_recent_entries(...)` — 최근 항목 조회
- `update_entry_status(page_id, status, notes)` — 상태 변경

---

## Notion DB 스키마

| 속성 | 타입 | 값 목록 |
|------|------|---------|
| Name | title | — |
| Type | select | 아티클, 이슈 |
| Status | select | 읽을 예정, 읽는 중, 완료, 대기 중, 진행 중, 해결됨 |
| Priority | select | 높음, 중간, 낮음 (이슈 전용) |
| Tags | multi_select | AI, LLM, RAG, Agent, Multimodal, Embedding, VectorDB, Prompt Engineering, Product, Engineering, Research, Tool Use |
| URL | url | — |
| Source | rich_text | — |
| Notes | rich_text | — |

Summary와 Key Insights는 DB 속성이 아니라 **페이지 본문 블록**으로 저장됩니다 (Callout + Heading2 + 불릿).

---

## 알려진 이슈 및 히스토리

### notion-client v3.0.0 API 변경 (2026-02-28 수정 완료)
- **증상**: `list_recent()`, `search()`, `url_exists()` 모두 실패. MCP 저장 불가. GitHub Actions 빨간 X.
- **원인**: notion-client v3.0.0이 Notion API 버전 `2025-09-03`을 기본으로 사용하는데, 이 버전에서 `POST /v1/databases/{id}/query` 엔드포인트가 제거됨.
- **수정**: `notion_db.py` `NotionDB.__init__`에서 `Client(auth=token, notion_version="2022-06-28")` 고정. `databases.query()` → `client.request()` 교체.
- **관련 파일**: `notion_db.py:133`, `requirements.txt`

### batch_ingest.py OpenAI 호출 버그
- `responses.create()` 메서드가 존재하지 않음. 올바른 호출은 `chat.completions.create()`.
- 현재 미수정 (로컬 수동 실행 시 OpenAI 프로바이더 사용 불가).

---

## GitHub Actions 워크플로

| 워크플로 | 파일 | 스케줄 | 스크립트 |
|---------|------|--------|---------|
| notion-ingest | `.github/workflows/notion-ingest.yml` | 매일 07:00 KST | `repo_ingest.py` |

워크플로가 실패하면:
1. GitHub → Actions 탭에서 로그 확인
2. Repository Secrets 설정 확인 (NOTION_TOKEN, NOTION_DATABASE_ID, GEMINI_API_KEY)
3. Gemini API 할당량 확인 (무료 RPM 한도)

---

## inputs/ 폴더 사용법

```
inputs/
  article_url.txt     ← URL 한 줄 적으면 크롤링 후 요약
  long_article.txt    ← 120자 이상 텍스트면 그대로 요약
  paper.pdf           ← PDF 텍스트 추출 후 요약
```

`repo_ingest.py`와 `batch_ingest.py` 모두 이 폴더를 스캔합니다.
URL 중복 시 자동 스킵 (Notion DB에 이미 있는 URL은 건너뜀).

---

## 로컬 실행 명령어

```bash
# inputs/ 폴더 수동 처리
python repo_ingest.py --input-dir inputs --provider gemini

# 인터랙티브 CLI 에이전트
python agent.py

# 뉴스레터 수동 실행
python newsletter.py

# 텔레그램 봇 실행
python telegram_bot.py
```
