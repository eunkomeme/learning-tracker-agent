# Learning Tracker Agent

> 아티클·URL·텍스트를 Claude Code 채팅창에 붙여넣으면 AI가 PM 관점으로 요약해 Notion 지식 베이스에 자동으로 쌓아 줍니다.
> 서버 비용 0원. 별도 API 키 불필요.

---

## 왜 만들었나

매일 좋은 아티클, 논문, PDF를 발견하지만 수동 정리는 시간이 너무 많이 들고, 단순 북마크는 나중에 검색이 불가능하다.

**목표**: 발견하는 즉시 Claude가 요약·태그·인사이트를 생성해 Notion에 검색 가능한 형태로 저장하는 제로 인프라 시스템.

---

## 시스템 구성

```
Claude Code 채팅창
  (URL 또는 본문 붙여넣기)
         ↓
   mcp_server.py
  (MCP 도구 제공)
         ↓
   notion_db.py
  (Notion CRUD)
         ↓
  Notion 데이터베이스
```

---

## Notion DB 스키마

| 속성 | 타입 | 옵션 |
|------|------|------|
| Name | title | — |
| Type | select | 아티클 \| 이슈 |
| Status | select | 읽을 예정 \| 읽는 중 \| 완료 \| 대기 중 \| 진행 중 \| 해결됨 |
| Priority | select | 높음 \| 중간 \| 낮음 (이슈 전용) |
| Tags | multi_select | AI, LLM, RAG, Agent, Multimodal, Embedding, VectorDB, Prompt Engineering, Product, Engineering, Research, Tool Use |
| URL | url | — |
| Source | rich_text | — |
| Notes | rich_text | — |

Summary와 Key Insights는 DB 속성이 아닌 **페이지 본문 블록**으로 저장됩니다.
(Callout 블록 = 요약 / Heading2 + 불릿 = 핵심 인사이트)

---

## 환경 변수 설정

> ⚠️ `.env` 파일을 사용하지 않습니다.
> **Claude Code → 새 클라우드 환경 → 환경 변수**에 `.env` 형식으로 입력하세요.

| 변수 | 필수 | 설명 |
|------|------|------|
| `NOTION_TOKEN` | ✅ | Notion Integration 토큰 |
| `NOTION_DATABASE_ID` | ✅ | 32자리 hex (하이픈 없음) |

---

## 초기 세팅

### 1. Notion DB 생성

```bash
pip install -r requirements.txt
python setup_notion.py
# 안내에 따라 부모 페이지 ID 입력 → NOTION_DATABASE_ID 출력
```

### 2. 환경 변수 등록

Claude Code 클라우드 환경 UI에 아래 형식으로 입력:

```
NOTION_TOKEN=secret_xxxxx
NOTION_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 사용 방법

`.mcp.json`으로 MCP 서버가 자동 등록됩니다.
채팅창에 URL 또는 아티클 본문을 붙여넣으면 Claude가 아래 순서로 자동 저장합니다.

1. URL 제공 시 `fetch_article_content(url)`로 본문 추출
2. Claude가 직접 한국어 요약 + 핵심 인사이트 + 태그 생성
3. `save_article(...)` 호출로 Notion에 저장

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `notion_db.py` | Notion API CRUD 래퍼. 모든 모듈이 공유하는 데이터 레이어 |
| `mcp_server.py` | Claude Code MCP 서버. 채팅창 → Notion 직접 저장 |
| `setup_notion.py` | 최초 1회: Notion DB 스키마 생성 및 ID 발급 |
| `.mcp.json` | MCP 서버 등록 설정 (Claude Code 자동 로드) |

---

## 핵심 설계 결정

### 1. Claude Code가 요약 수행

별도 AI API 없이 Claude Code 자체가 요약·태그·인사이트를 생성. MCP 도구는 저장/조회 역할만 담당.

### 2. Summary/Key Insights를 페이지 본문 블록으로 저장

DB 속성(필터 대상)에서 페이지 블록으로 이동 → Notion에서 가독성 향상. Tags, Status, URL은 검색·필터링에 필요해 DB 속성으로 유지.

### 3. URL 중복 방지

저장 전 `notion.url_exists(url)`로 DB 쿼리. 같은 URL이 반복 입력돼도 중복 저장 없음.

---

## 한계

- **스캔 PDF**: 텍스트 기반만 지원, OCR 미지원
- **URL 크롤링**: 일부 사이트는 본문 추출 실패 (직접 본문 붙여넣기로 대체)
