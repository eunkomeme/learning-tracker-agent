# Learning Tracker Agent

공부하면서 발견한 링크/텍스트/PDF를 **한 번에 수집·요약·저장**하는 개인 학습 자동화 프로젝트입니다.  
핵심 목표는 "흩어진 학습 기록"을 Notion DB 하나로 통합하고, 이 데이터를 장기적으로 **회고/포트폴리오 자산**으로 전환하는 것입니다.

---

## 1) 프로젝트 한 줄 소개

> 모바일에서 공유한 자료를 Gemini가 요약하고, Notion에 구조화 저장해 학습 히스토리를 자동으로 쌓는 에이전트

---

## 2) 문제 정의 (Why)

기존 학습 방식의 문제:
- 브라우저 북마크, 메모앱, 채팅, 이메일에 자료가 분산됨
- "읽긴 읽었는데 무엇을 배웠는지" 기록이 남지 않음
- 시간이 지나면 다시 찾기/복습이 어려움

이 프로젝트가 해결하는 지점:
- 입력 채널을 Telegram으로 단순화 (모바일 중심)
- 요약/핵심 인사이트/태그를 자동 생성
- Notion DB에 일관된 스키마로 저장

---

## 3) 프로젝트 목표 (What)

- 학습 입력 마찰 최소화: 링크 공유 or 텍스트 붙여넣기 or PDF 업로드
- 요약 품질 표준화: Gemini 기반 구조화 출력(JSON)
- 검색/회고 가능성 강화: 태그·상태·출처 중심으로 Notion 축적
- 포트폴리오 활용성 확보: 개발 의도/구현/운영 기록 문서화

---

## 4) 시스템 아키텍처 (How)

```text
[User Input on Mobile]
  ├─ URL
  ├─ Plain Text
  └─ PDF File
          ↓
      Telegram Bot (python-telegram-bot)
          ↓
   Input Router (url/text/pdf)
          ↓
  - URL: trafilatura 본문 추출
  - PDF: pypdf 텍스트 추출
  - TEXT: 직접 본문 사용
          ↓
   Gemini Summarizer (JSON schema)
          ↓
      NotionDB.add_article()
          ↓
 Notion Learning Database (검색/회고/포트폴리오 데이터)
```

---

## 5) 기술 스택

- **Language**: Python
- **LLM**: Google Gemini (`google-generativeai`)
- **Chat Interface**: Telegram Bot API (`python-telegram-bot`)
- **Content Extraction**:
  - URL: `trafilatura`
  - PDF: `pypdf`
- **Knowledge Base**: Notion API (`notion-client`)
- **Config**: `.env` (`python-dotenv`)

---

## 6) 현재 구현된 기능

### 6-1. Core 모듈

- `notion_db.py`
  - Notion CRUD 래퍼
  - 아티클/이슈 저장
  - URL 중복 검사(`url_exists`)
- `agent.py`
  - CLI 기반 요약/정리 워크플로우
- `newsletter.py`
  - RSS/이메일 기반 자동 수집 파이프라인

### 6-2. Telegram Bot 기능

- `telegram_bot.py`
  - `/start` 안내 메시지
  - 입력 3종 지원:
    1. URL 포함 메시지
    2. 원문 텍스트 직접 입력
    3. PDF 문서 업로드
  - 처리 흐름:
    - URL → 본문 추출 실패 시 에러 안내
    - TEXT → 최소 길이 검증 후 요약
    - PDF → 텍스트 추출 후 요약 (스캔 PDF 예외 처리)
  - 결과 저장:
    - summary / key_insights / tags / source / title 구조화
    - Notion 페이지 생성 및 링크 반환

### 6-3. 문서/운영

- `TELEGRAM_BOT.md`: BotFather 생성부터 실행·트러블슈팅까지
- `.env.example`: 필수 환경변수 템플릿
- `requirements.txt`: 런타임 의존성 정의

---

## 7) 실행 방법 (로컬)

1. 의존성 설치

```bash
pip install -r requirements.txt
```

2. 환경변수 구성 (`.env`)

```env
GEMINI_API_KEY=...
NOTION_TOKEN=...
NOTION_DATABASE_ID=...
TELEGRAM_BOT_TOKEN=...
```

3. 실행

```bash
python telegram_bot.py
```

4. Telegram에서 테스트
- `/start`
- URL 1개 전송
- 긴 텍스트 붙여넣기
- PDF 파일 전송

---

## 8) 진행 내역 (Portfolio Timeline)

### Phase 1 — 기반 구축
- Notion 학습 DB 스키마 중심으로 데이터 모델 확정
- Notion CRUD 유틸 구현
- Gemini 요약/인사이트 생성 파이프라인 구성

### Phase 2 — 자동 수집 확장
- RSS/이메일 입력 채널 연결
- 반복 가능한 수집 작업 흐름 정리

### Phase 3 — 모바일 입력 최적화
- Telegram Bot 도입
- URL 공유 기반 저장 자동화
- URL 중복 저장 방지 적용

### Phase 4 — 입력 실패 케이스 보완
- 로그인/동적 페이지 등 URL 파싱 실패 문제 대응
- **Plain Text 직접 요약 추가**
- **PDF 업로드 요약 추가**
- 사용자 피드백 메시지 개선

### Phase 5 — 문서화/포트폴리오 정리
- README/가이드 문서 업데이트
- 기능/의도/운영 포인트를 재사용 가능한 형태로 정리

---

## 9) 이 프로젝트의 포트폴리오 포인트

- **문제 해결 중심 설계**: 단순 챗봇이 아니라 "학습 기록 분산" 문제를 명확히 타겟팅
- **실사용 UX**: 모바일 공유 흐름을 기준으로 입력 마찰 최소화
- **견고성 개선 과정**: URL-only 한계를 텍스트/PDF로 확장하며 실패 케이스 대응
- **End-to-End 구현**: 수집 → 추출 → 요약 → 구조화 저장까지 완결된 파이프라인
- **확장 가능성**: webhook, 운영 모니터링, 주간 리포트, 태그 정규화 등 후속 개발 여지

---

## 10) 알려진 한계

- 스캔(이미지) 기반 PDF는 텍스트 추출 실패 가능
- 로그인/권한 필요한 웹페이지는 본문 추출 실패 가능
- 현재 polling 방식이라 상시 프로세스 운영 필요
- API quota 소진 시 요약 요청 지연/실패 가능

---

## 11) 다음 로드맵

- [ ] 무료 티어 기반 상시 배포 안정화 (Render/Koyeb 등)
- [ ] PDF OCR fallback 추가 (스캔 PDF 대응)
- [ ] 입력 실패 자동 재시도/대체 경로 안내 강화
- [ ] 태그 정규화 + 유사 문서 클러스터링
- [ ] 주간 학습 리포트 자동 생성 (Notion 데이터 기반)
- [ ] 간단 대시보드(학습량/주제/완료율) 추가

---

## 12) 운영/보안 메모

- 민감정보(API 키/토큰)는 `.env`에만 저장 (`.gitignore` 유지)
- 토큰 노출 시 즉시 재발급(rotate)
- 외부 배포 시 로그에 민감정보가 출력되지 않도록 점검

---

## 13) 관련 문서

- Telegram 설정/사용 가이드: `TELEGRAM_BOT.md`
- 환경변수 예시: `.env.example`
- 핵심 코드:
  - `telegram_bot.py`
  - `notion_db.py`
  - `agent.py`
  - `newsletter.py`
