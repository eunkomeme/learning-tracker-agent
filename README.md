# Learning Tracker Agent

> 아티클·PDF·텍스트를 저장하면 AI가 PM 관점으로 요약해 Notion 지식 베이스에 자동으로 쌓아 줍니다.
> 서버 비용 0원. GitHub Actions로 매일 자동 실행.

---

## 왜 만들었나

매일 좋은 아티클, 논문, PDF를 발견하지만 수동 정리는 시간이 너무 많이 들고, 단순 북마크는 나중에 검색이 불가능하다. Readwise 같은 유료 서비스는 내 Notion 구조와 맞지 않는다.

**목표**: 발견하는 즉시 AI가 요약·태그·인사이트를 생성해 Notion에 검색 가능한 형태로 저장하는 제로 인프라 시스템.

---

## 시스템 구성

```
입력 경로
├── inputs/ 폴더  ─────────────→  repo_ingest.py / batch_ingest.py
│   (URL·텍스트·PDF 파일)               ↓
├── Claude Code 채팅창 ─────────→  mcp_server.py (MCP 툴)
│   (URL·본문 붙여넣기)                  ↓
├── Telegram 봇 ────────────────→  telegram_bot.py
│   (URL·PDF 전송)                       ↓
└── RSS·이메일 뉴스레터 ─────────→  newsletter.py ← scheduler.py (데몬)
                                         ↓
                                    notion_db.py
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
| `GEMINI_API_KEY` | ✅ | Google AI Studio 무료 키 |
| `OPENAI_API_KEY` | 선택 | batch_ingest.py OpenAI 모드 |
| `ANTHROPIC_API_KEY` | 선택 | batch_ingest.py Anthropic 모드 |
| `TELEGRAM_BOT_TOKEN` | 선택 | telegram_bot.py 전용 |
| `RSS_FEEDS` | 선택 | newsletter.py RSS (콤마 구분 URL) |
| `EMAIL_IMAP_SERVER` | 선택 | newsletter.py 이메일 |
| `EMAIL_ADDRESS` | 선택 | newsletter.py 이메일 |
| `EMAIL_APP_PASSWORD` | 선택 | newsletter.py 이메일 |
| `NEWSLETTER_SENDERS` | 선택 | newsletter.py 이메일 발신자 필터 |

**GitHub Actions 워크플로는 Claude Code 환경 변수를 공유하지 않습니다.**
레포 → Settings → Secrets에 `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `GEMINI_API_KEY`를 별도 등록하세요.

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
GEMINI_API_KEY=AIzaXXXXXX
```

### 3. GitHub Actions 활성화

레포 → Settings → Secrets → Actions에 동일 변수 등록.
`.github/workflows/notion-ingest.yml`이 매일 07:00 KST에 자동 실행됩니다.

---

## 사용 방법

### A. Claude Code 채팅창 (가장 빠름)

`.mcp.json`으로 MCP 서버가 자동 등록됩니다.
채팅창에 URL 또는 아티클 본문을 붙여넣으면 Claude가 `save_article` 툴로 즉시 저장합니다.

### B. inputs/ 폴더

```
inputs/
  article.txt     # URL 한 줄 → 크롤링 후 요약
  notes.txt       # 120자 이상 텍스트 → 그대로 요약
  paper.pdf       # PDF 텍스트 추출 후 요약
```

파일을 커밋하면 GitHub Actions가 다음 스케줄(매일 07:00 KST)에 자동 처리합니다.
즉시 실행하려면: GitHub → Actions → `notion-ingest` → `Run workflow`.

```bash
# 로컬에서 직접 실행
python repo_ingest.py --input-dir inputs --provider gemini
```

### C. Telegram 봇

URL, 텍스트, PDF 파일을 봇에게 보내면 즉시 Notion에 저장됩니다.
별도 서버(Railway 등) 필요. → [`TELEGRAM_BOT.md`](TELEGRAM_BOT.md) 참고

### D. RSS·뉴스레터 자동화

```bash
python newsletter.py          # RSS + 이메일 일괄 처리
python newsletter.py --rss    # RSS만
python newsletter.py --email  # 이메일만
python newsletter.py --url https://... # 단일 URL

# 매일 09:00에 자동 실행 (데몬)
python scheduler.py &
```

### E. 인터랙티브 CLI 에이전트

```bash
python agent.py
```

Gemini Tool Calling 기반. 자연어로 아티클 저장·검색·상태 변경이 가능합니다.

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `notion_db.py` | Notion API CRUD 래퍼. 모든 모듈이 공유하는 데이터 레이어 |
| `mcp_server.py` | Claude Code MCP 서버. 채팅창 → Notion 직접 저장 |
| `repo_ingest.py` | inputs/ → Gemini Map-Reduce 요약 → Notion. GitHub Actions 진입점 |
| `batch_ingest.py` | inputs/ → Gemini/OpenAI/Anthropic 선택 → Notion. 로컬 수동용 |
| `agent.py` | Gemini Tool Calling 인터랙티브 CLI 에이전트 |
| `newsletter.py` | RSS 피드 + 이메일 뉴스레터 자동 수집·요약 |
| `scheduler.py` | newsletter.py 일별 자동 실행 데몬 |
| `telegram_bot.py` | Telegram 실시간 저장 봇 |
| `setup_notion.py` | 최초 1회: Notion DB 스키마 생성 및 ID 발급 |
| `.mcp.json` | MCP 서버 등록 설정 (Claude Code 자동 로드) |
| `.github/workflows/notion-ingest.yml` | 매일 07:00 KST 자동 실행 워크플로 |

---

## 핵심 설계 결정

### 1. 폴더 기반 입력 (UI 없음)

Git 커밋 자체가 인풋 트리거. 별도 웹 UI나 API 없이 GitHub 레포가 곧 인터페이스.
포기한 것: 실시간성 / 얻은 것: 인프라 복잡도 0.

### 2. Gemini 기본 + Map-Reduce 구조

무료 Gemini API 하나로 CI 환경에서 동작. 긴 문서는 6,000자 단위로 청크 → 개별 요약(Map) → 통합(Reduce). 무료 RPM 한도를 고려한 지수 백오프 재시도 포함.

### 3. Summary/Key Insights를 페이지 본문 블록으로 저장

DB 속성(필터 대상)에서 페이지 블록으로 이동 → Notion에서 가독성 향상. Tags, Status, URL은 검색·필터링에 필요해 DB 속성으로 유지.

### 4. URL 중복 방지

저장 전 `notion.url_exists(url)`로 DB 쿼리. 같은 URL이 inputs/에 반복 입력돼도 중복 저장 없음.

---

## 한계

- **스캔 PDF**: 텍스트 기반만 지원, OCR 미지원
- **GitHub Actions 한도**: 무료 플랜 월 2,000분 (대량 처리 시 주의)
- **batch_ingest.py**: OpenAI 호출 코드 버그 있음 (Gemini는 정상)
- **newsletter.py**: Gemini 전용, 다른 프로바이더 미지원
