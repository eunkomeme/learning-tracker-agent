# Learning Tracker Agent

리포지토리에 URL / PDF / 텍스트 파일을 넣고, 배치로 요약해서 Notion DB에 저장하는 프로젝트입니다.

---

## 현재 기준(권장) 워크플로우

1. `inputs/` 폴더에 URL 목록(`.txt` / `.md`) 또는 PDF 파일을 추가
2. `repo_ingest.py` 실행
3. LLM(OpenAI / Anthropic / Gemini)으로 요약 JSON 생성
4. Notion DB에 저장 (`title / summary / key_insights / tags / source`)
5. URL은 `url_exists`로 중복 저장 방지

---

## 빠른 시작

```bash
pip install -r requirements.txt
```

### .env 예시

```env
NOTION_TOKEN=...
NOTION_DATABASE_ID=...

# 공급자 선택 (gemini / openai / anthropic)
LLM_PROVIDER=openai

# 선택한 공급자 API 키
GEMINI_API_KEY=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

### 실행

```bash
python repo_ingest.py --input-dir inputs --provider openai
```

- `--provider`를 생략하면 `LLM_PROVIDER` 값을 사용합니다.
- 둘 다 없으면 기본값은 `gemini`입니다.

---

## GitHub Actions (서버 없이 스케줄 실행)

워크플로우 파일:
```
.github/workflows/notion-ingest.yml
```

### 필수 GitHub Secrets

- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`
- `LLM_PROVIDER` (`gemini` / `openai` / `anthropic`)
- `GEMINI_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

---

## 주요 파일

- `repo_ingest.py` — 배치 요약 + Notion 적재 엔트리포인트
- `notion_db.py` — Notion CRUD 및 URL 중복 검사
- `.github/workflows/notion-ingest.yml` — 스케줄/수동 실행 워크플로우
- `docs/codex-claude-notion-automation.md` — 운영 가이드

---

## 레거시 (v1)

Telegram Bot 기반 방식은 레거시로 유지됩니다.

- `telegram_bot.py`
- `TELEGRAM_BOT.md`