# Learning Tracker Agent — Claude 세션 컨텍스트

이 파일은 Claude Code 세션마다 자동으로 읽혀, 처음 만나는 세션에서도 컨텍스트 설명 없이 바로 작업할 수 있도록 유지합니다.

---

## 프로젝트 개요

Claude Code가 직접 요약·태그·인사이트를 생성하고 MCP 도구로 Notion 데이터베이스에 저장하는 개인 지식 관리 시스템.
**핵심 철학**: 인프라 비용 0, 별도 AI API 불필요, Notion 네이티브.

---

## 환경 변수 설정 방식

> **중요**: `.env` 파일이 없습니다. 환경 변수는 **Claude Code 클라우드 환경 UI**에서 설정됩니다.
>
> 설정 위치: Claude Code → 새 클라우드 환경 → 환경 변수 (.env 형식 입력)

| 변수 | 용도 | 필수 여부 |
|------|------|---------|
| `NOTION_TOKEN` | Notion Integration 토큰 | 필수 |
| `NOTION_DATABASE_ID` | 32자리 hex (하이픈 없음) | 필수 |

---

## 파일별 역할

| 파일 | 역할 |
|------|------|
| `notion_db.py` | Notion API CRUD 래퍼. 모든 모듈이 공유하는 데이터 레이어 |
| `mcp_server.py` | Claude Code용 MCP 서버. 채팅창에서 바로 Notion 저장 가능 |
| `setup_notion.py` | 최초 1회: Notion DB 스키마 생성 및 NOTION_DATABASE_ID 발급 |
| `.mcp.json` | MCP 서버 등록 (Claude Code 자동 읽음) |

---

## 채팅창 텍스트 → Notion 저장 방법

MCP 서버(`mcp_server.py`)가 `.mcp.json`으로 Claude Code에 등록되어 있습니다.
채팅창에 아티클 본문이나 URL을 붙여넣으면 Claude가 직접 요약한 후 `save_article` MCP 툴로 저장합니다.

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
- **증상**: `list_recent()`, `search()`, `url_exists()` 모두 실패. MCP 저장 불가.
- **원인**: notion-client v3.0.0이 Notion API 버전 `2025-09-03`을 기본으로 사용하는데, 이 버전에서 `POST /v1/databases/{id}/query` 엔드포인트가 제거됨.
- **수정**: `notion_db.py` `NotionDB.__init__`에서 `Client(auth=token, notion_version="2022-06-28")` 고정. `databases.query()` → `client.request()` 교체.
- **관련 파일**: `notion_db.py:135`
