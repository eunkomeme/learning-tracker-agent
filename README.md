# Learning Tracker Agent

공부한 아티클/이슈를 **Notion DB 하나에서 통합 관리**하기 위한 AI 에이전트 프로젝트입니다.  
개인 학습 기록을 자동화하고, 나중에 회고/포트폴리오 자료로 재활용할 수 있도록 설계했습니다.

---

## 1) 프로젝트 목적

- 모바일/웹에서 발견한 학습 링크를 빠르게 수집
- Gemini로 핵심 내용을 요약하고 인사이트를 정리
- Notion 데이터베이스에 구조화된 형태로 축적
- 축적된 로그를 기반으로 학습 히스토리/성과를 포트폴리오화

---

## 2) 현재까지 완료된 기능

### Core
- `agent.py`
  - Gemini 기반 CLI 에이전트
  - 아티클 입력 시 요약/인사이트/태그 생성 및 저장 흐름 지원

- `notion_db.py`
  - Notion CRUD 래퍼
  - 아티클 저장, 중복 URL 확인 등 데이터베이스 연동 로직 담당

- `newsletter.py`
  - RSS/이메일 소스 기반 자동 수집 파이프라인

### Telegram 확장
- `telegram_bot.py`
  - 텔레그램 메시지에서 URL 자동 추출
  - 본문 추출(trafilatura) → Gemini 구조화 요약 → Notion 저장 자동화
  - `/start` 명령 및 중복 URL 저장 방지 처리 포함

- `TELEGRAM_BOT.md`
  - BotFather 봇 생성부터 실행/문제해결까지의 운영 가이드 문서

### 환경/의존성
- `requirements.txt`
  - Telegram 봇 실행을 위한 `python-telegram-bot` 포함
- `.env.example`
  - Gemini / Notion / Telegram 필수 환경변수 템플릿 정리

---

## 3) 아키텍처 개요

```text
[Mobile/Web Link Share]
        ↓
   Telegram Bot
        ↓ (URL 추출)
  Content Extractor (trafilatura)
        ↓ (본문/제목)
     Gemini Summarizer
        ↓ (JSON: summary, insights, tags)
      Notion DB Writer
        ↓
  Learning Log / Portfolio Data
```

---

## 4) 실행 방법

1. 의존성 설치

```bash
pip install -r requirements.txt
```

2. 환경변수 설정 (`.env`)

```env
GEMINI_API_KEY=...
NOTION_TOKEN=...
NOTION_DATABASE_ID=...
TELEGRAM_BOT_TOKEN=...
```

3. Telegram 봇 실행

```bash
python telegram_bot.py
```

---

## 5) 프로젝트 진행 타임라인 (요약)

1. Notion DB 중심의 학습 트래커 구조 설계
2. Gemini 기반 요약/인사이트 생성 로직 구현
3. RSS/이메일 자동 수집 모듈 연결
4. 텔레그램 링크 공유 기반 자동 저장 봇 추가
5. BotFather/환경변수/운영 가이드 문서화

---

## 6) 포트폴리오 관점에서의 강점

- **문제 정의 명확성**: "학습 기록 분산" 문제를 Notion 단일 DB로 해결
- **실사용성**: 모바일 공유 UX 기반으로 입력 마찰 최소화
- **자동화 파이프라인**: 수집 → 요약 → 구조화 저장의 end-to-end 구축
- **확장 가능성**: 배포 전략(polling/webhook), 분석 대시보드, 주간 리포트로 확장 가능

---

## 7) 다음 단계 로드맵

- 무료/모바일 친화 배포(Render 등)로 상시 운영
- 실패 케이스(동적 페이지, 파싱 실패)에 대한 fallback 개선
- 태그 정규화 및 중복 아티클 클러스터링
- Notion 데이터 기반 주간 학습 리포트 자동 생성
- webhook 전환(필요 시) 및 운영 모니터링 강화

---

## 8) 운영 메모

- 민감 정보(API 키/토큰)는 `.env`에만 저장하고 커밋 금지
- 토큰 노출 시 즉시 재발급(rotate)
- 개인용에서 시작하되, 협업/공개 데모를 고려해 로그/에러 핸들링을 지속 보강
