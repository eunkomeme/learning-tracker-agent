# Learning Tracker Agent

리포지토리에 URL/PDF/텍스트를 넣고 배치로 요약해 Notion DB에 저장하는 자동화 프로젝트입니다.

## 현재 운영 기준 (v2)

- **입력**: `inputs/` 폴더(또는 GitHub 이슈/코멘트 기반 경로)
- **실행**: GitHub Actions 스케줄 또는 로컬 에이전트 실행
- **요약 모델**: Codex/Claude/Gemini 중 선택
- **저장**: Notion DB (`title / summary / key_insights / tags / source`)
- **중복 방지**: URL 기준 `url_exists` 검사

상세 운영 가이드:
- `docs/codex-claude-notion-automation.md`

---

## 권장 처리 흐름

```text
Repo Inputs(url/pdf/text)
→ Extractor(trafilatura / pypdf / raw text)
→ LLM Provider(Codex/Claude/Gemini)
→ Structured JSON
→ NotionDB.add_article()
→ Notion Learning Database
```

---

## 빠른 시작

```bash
pip install -r requirements.txt
```

### 환경 변수

```env
NOTION_TOKEN=...
NOTION_DATABASE_ID=...
# 모델 공급자에 따라 1개 이상 사용
GEMINI_API_KEY=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

### 실행 방식

1. `inputs/`에 URL 목록 또는 PDF 추가
2. 로컬 실행 또는 GitHub Actions 실행
3. 결과가 Notion DB에 적재되는지 확인

GitHub Actions 예시는 아래 문서의 워크플로우 섹션 참고:
- `docs/codex-claude-notion-automation.md`

---

## 주요 파일

- `agent.py`: CLI 기반 워크플로우
- `notion_db.py`: Notion CRUD, 아티클/이슈 저장, URL 중복 검사
- `newsletter.py`: RSS/이메일 기반 자동 수집 파이프라인
- `docs/codex-claude-notion-automation.md`: v2 운영/배포/비용/만료 대응 가이드

---

## 운영 체크포인트

- 스캔 PDF 대비 OCR fallback 고려
- LLM별 응답 포맷 차이는 provider 레이어에서 흡수
- Notion API rate limit 대비 retry/backoff 적용
- API 키/토큰은 GitHub Secrets로 관리

---

## 레거시(v1) 참고

Telegram Bot + Gemini 상시 실행 방식은 레거시로 남아 있으며, 필요 시 아래 문서를 참고하세요.
- `TELEGRAM_BOT.md`
